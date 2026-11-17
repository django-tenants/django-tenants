from types import SimpleNamespace
from unittest import mock

from django.core.exceptions import ImproperlyConfigured, SuspiciousFileOperation
from django.test import RequestFactory, SimpleTestCase

from django_tenants import utils
from django_tenants.middleware import TenantMainMiddleware
from django_tenants.test.cases import TenantTestCase
from django.core.management.commands.migrate import Command as MigrateCommand
from django.test.utils import override_settings

from django_tenants.utils import get_current_tenant, get_tenant


class CustomMigrateCommand(MigrateCommand):
    pass


class ConfigStringParsingTestCase(TenantTestCase):
    def test_static_string(self):
        self.assertEqual(
            utils.parse_tenant_config_path("foo"),
            "foo/{}".format(self.tenant.schema_name),
        )

    def test_format_string(self):
        self.assertEqual(
            utils.parse_tenant_config_path("foo/%s/bar"),
            "foo/{}/bar".format(self.tenant.schema_name),
        )

        # Preserve trailing slash
        self.assertEqual(
            utils.parse_tenant_config_path("foo/%s/bar/"),
            "foo/{}/bar/".format(self.tenant.schema_name),
        )

    def test_path_traversal_schema_name_is_rejected(self):
        for schema_name in ('x/../victim', '../../app', '..', '.', 'a\\b', '', None):
            for config_path in ('foo', 'foo/%s/bar'):
                with self.subTest(schema_name=schema_name, config_path=config_path):
                    with mock.patch('django_tenants.utils.connection',
                                    SimpleNamespace(schema_name=schema_name)):
                        with self.assertRaises(SuspiciousFileOperation):
                            utils.parse_tenant_config_path(config_path)

    def test_windows_unsafe_schema_name_is_rejected_on_windows(self):
        for schema_name in ('D:x', 'victim.', 'victim '):
            with self.subTest(schema_name=schema_name):
                with mock.patch('django_tenants.utils.connection',
                                SimpleNamespace(schema_name=schema_name)), \
                        mock.patch('django_tenants.utils.os.name', 'nt'):
                    with self.assertRaises(SuspiciousFileOperation):
                        utils.parse_tenant_config_path('foo/%s')

    def test_get_tenant_base_migrate_command_class_default(self):
        self.assertEqual(
            utils.get_tenant_base_migrate_command_class(),
            MigrateCommand,
        )

    def test_get_tenant_base_migrate_command_class_custom(self):
        command_path = 'django_tenants.tests.test_utils.CustomMigrateCommand'
        with override_settings(TENANT_BASE_MIGRATE_COMMAND=command_path):
            self.assertEqual(
                utils.get_tenant_base_migrate_command_class(),
                CustomMigrateCommand,
            )

    def test_get_tenant(self):
        tenant_domain = 'tenant.test.com'
        factory = RequestFactory()
        tm = TenantMainMiddleware(lambda r: r)
        request = factory.get('/any/request/', HTTP_HOST=tenant_domain)
        tm.process_request(request)
        self.assertEqual(get_tenant(request).schema_name, 'test')

    def test_get_current_tenant(self):
        # The point of get_current_tenant (issue #1217) is that it takes no request, so it
        # works from anywhere the connection is already set -- helpers, tasks, signals.
        self.assertEqual(get_current_tenant().schema_name, self.tenant.schema_name)

    def test_get_current_tenant_follows_schema_context(self):
        with utils.schema_context(utils.get_public_schema_name()):
            self.assertEqual(
                get_current_tenant().schema_name, utils.get_public_schema_name()
            )
        # and is restored on the way out
        self.assertEqual(get_current_tenant().schema_name, self.tenant.schema_name)

    def test_get_current_tenant_returns_the_instance_under_tenant_context(self):
        with utils.tenant_context(self.tenant):
            self.assertEqual(get_current_tenant(), self.tenant)


MULTI_TYPE_TEMPLATES = {
    'public': {'APPS': [], 'URLCONF': ''},
    'type1': {'APPS': [], 'URLCONF': '', 'BASE_SCHEMA': 'type1_template'},
    'type2': {'APPS': [], 'URLCONF': ''},
}


@override_settings(TENANT_CREATION_FAKES_MIGRATIONS=True)
class TenantBaseSchemaTestCase(SimpleTestCase):
    """Which template schema a new tenant is cloned from. See #533."""

    @override_settings(TENANT_BASE_SCHEMA='template')
    def test_single_template(self):
        self.assertEqual(utils.get_tenant_base_schema(), 'template')

    @override_settings(HAS_MULTI_TYPE_TENANTS=True, TENANT_TYPES=MULTI_TYPE_TEMPLATES)
    def test_the_template_of_the_type_is_used(self):
        self.assertEqual(utils.get_tenant_base_schema('type1'), 'type1_template')

    @override_settings(HAS_MULTI_TYPE_TENANTS=True, TENANT_TYPES=MULTI_TYPE_TEMPLATES,
                       TENANT_BASE_SCHEMA='template')
    def test_the_template_of_the_type_wins_over_the_shared_one(self):
        self.assertEqual(utils.get_tenant_base_schema('type1'), 'type1_template')

    @override_settings(HAS_MULTI_TYPE_TENANTS=True, TENANT_TYPES=MULTI_TYPE_TEMPLATES,
                       TENANT_BASE_SCHEMA='template')
    def test_a_type_without_a_template_falls_back_to_the_shared_one(self):
        self.assertEqual(utils.get_tenant_base_schema('type2'), 'template')

    @override_settings(HAS_MULTI_TYPE_TENANTS=True, TENANT_TYPES=MULTI_TYPE_TEMPLATES)
    def test_a_type_without_a_template_and_no_shared_one_has_none(self):
        self.assertFalse(utils.get_tenant_base_schema('type2'))

    @override_settings(HAS_MULTI_TYPE_TENANTS=True, TENANT_TYPES=MULTI_TYPE_TEMPLATES)
    def test_the_types_templates_are_enough_to_fake_migrations(self):
        self.assertTrue(utils.get_creation_fakes_migrations())

    def test_faking_migrations_without_any_template_is_improperly_configured(self):
        with self.assertRaisesMessage(ImproperlyConfigured, 'TENANT_BASE_SCHEMA'):
            utils.get_creation_fakes_migrations()

    @override_settings(TENANT_CREATION_FAKES_MIGRATIONS=False, TENANT_BASE_SCHEMA='template')
    def test_a_template_without_faked_migrations_is_improperly_configured(self):
        with self.assertRaisesMessage(ImproperlyConfigured, 'TENANT_CREATION_FAKES_MIGRATIONS'):
            utils.get_tenant_base_schema()


class _FakeTenantConnection:
    def __init__(self, tenant):
        self.tenant = tenant

    def set_schema(self, schema_name):
        self.tenant = SimpleNamespace(schema_name=schema_name)

    def set_tenant(self, tenant):
        self.tenant = tenant

    def set_schema_to_public(self):
        self.tenant = 'public'


class ContextRestoresSelectedAliasTestCase(SimpleTestCase):
    """schema_context() and tenant_context() on a non-default alias restore
    that alias's own tenant, not the default connection's."""

    def _check(self, context, arg, **kwargs):
        default = _FakeTenantConnection('tenant_a')
        other = _FakeTenantConnection('tenant_z')
        fake_connections = {'default': default, 'other': other}
        with mock.patch.object(utils, 'connections', fake_connections), \
                mock.patch.object(utils, 'connection', default):
            with context(arg, **kwargs):
                self.assertNotEqual(other.tenant, 'tenant_z')
            self.assertEqual(other.tenant, 'tenant_z')
            self.assertEqual(default.tenant, 'tenant_a')

    def test_schema_context_with_database(self):
        self._check(utils.schema_context, 'tenant_b', database='other')

    def test_tenant_context_with_database(self):
        self._check(utils.tenant_context, 'tenant_b', database='other')

    @override_settings(TENANT_DB_ALIAS='other')
    def test_schema_context_with_tenant_db_alias(self):
        self._check(utils.schema_context, 'tenant_b')

    @override_settings(TENANT_DB_ALIAS='other')
    def test_tenant_context_with_tenant_db_alias(self):
        self._check(utils.tenant_context, 'tenant_b')

    def test_restores_public_when_selected_alias_had_no_tenant(self):
        default = _FakeTenantConnection('tenant_a')
        other = _FakeTenantConnection(None)
        with mock.patch.object(utils, 'connections', {'default': default, 'other': other}), \
                mock.patch.object(utils, 'connection', default):
            with utils.tenant_context('tenant_b', database='other'):
                pass
        self.assertEqual(other.tenant, 'public')
        self.assertEqual(default.tenant, 'tenant_a')


class ContextDecoratorStateTestCase(SimpleTestCase):
    """Used as decorators, schema_context() and tenant_context() keep no state
    shared between calls, so nested calls and threads restore correctly."""

    def _run(self, context):
        conn = _FakeTenantConnection('caller')
        with mock.patch.object(utils, 'connections', {'default': conn}), \
                mock.patch.object(utils, 'connection', conn):

            @context
            def recurse(depth):
                if depth:
                    conn.set_tenant('in_between')
                    recurse(depth - 1)

            recurse(2)
        self.assertEqual(conn.tenant, 'caller')

    def test_schema_context_decorator_nested_calls(self):
        self._run(utils.schema_context('x'))

    def test_tenant_context_decorator_nested_calls(self):
        self._run(utils.tenant_context('x'))

    def test_same_instance_nested_with(self):
        conn = _FakeTenantConnection('caller')
        with mock.patch.object(utils, 'connections', {'default': conn}):
            for cm in (utils.schema_context('x'), utils.tenant_context('x')):
                with cm:
                    conn.set_tenant('in_between')
                    with cm:
                        pass
                    self.assertEqual(conn.tenant, 'in_between')
                self.assertEqual(conn.tenant, 'caller')

    def test_subclass_with_its_own_init_still_works_as_decorator(self):
        class public_context(utils.schema_context):
            def __init__(self):
                super().__init__('public')

        conn = _FakeTenantConnection('caller')
        with mock.patch.object(utils, 'connections', {'default': conn}):
            @public_context()
            def f():
                return conn.tenant.schema_name
            self.assertEqual(f(), 'public')
        self.assertEqual(conn.tenant, 'caller')


class TenantMixinContextStateTestCase(SimpleTestCase):
    """with tenant: keeps the tenant to restore on the connection (one per
    thread), not on a list shared by every tenant instance and thread."""

    def test_interleaved_connections_restore_their_own_tenant(self):
        from django_tenants import models as tenant_models
        Tenant = utils.get_tenant_model()
        conn_1 = _FakeTenantConnection('request_tenant_1')
        conn_2 = _FakeTenantConnection('request_tenant_2')
        tenant_a, tenant_b = Tenant(schema_name='a'), Tenant(schema_name='b')

        def on(conn):
            return mock.patch.object(tenant_models, 'connections', {'default': conn})

        # Thread 1 enters A, thread 2 enters B, then thread 1 exits first.
        with on(conn_1):
            tenant_a.__enter__()
        with on(conn_2):
            tenant_b.__enter__()
        with on(conn_1):
            tenant_a.__exit__(None, None, None)
        with on(conn_2):
            tenant_b.__exit__(None, None, None)

        self.assertEqual(conn_1.tenant, 'request_tenant_1')
        self.assertEqual(conn_2.tenant, 'request_tenant_2')
