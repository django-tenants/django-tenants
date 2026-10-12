from django.core.exceptions import ImproperlyConfigured
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
