from contextlib import contextmanager
from unittest import mock

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import connection, transaction
from django.test.utils import override_settings
from django.utils.version import get_main_version, get_version_tuple

from django_tenants.clone import CloneSchema
from django_tenants.signals import schema_migrated, schema_migrate_message, schema_pre_migration
from dts_test_app.models import DummyModel, ModelWithFkToPublicUser

from django_tenants.migration_executors import get_executor
from django_tenants.test.cases import TenantTestCase
from django_tenants.tests.testcases import BaseTestCase
from django_tenants.utils import tenant_context, schema_context, schema_exists, get_tenant_model, \
    get_public_schema_name, get_tenant_domain_model


@contextmanager
def catch_signal(signal):
    """
    Catch django signal and return the mocked call.
    """
    handler = mock.Mock()
    signal.connect(handler)
    yield handler
    signal.disconnect(handler)


class TenantDataAndSettingsTest(BaseTestCase):
    """
    Tests if the tenant model settings work properly and if data can be saved
    and persisted to different tenants.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        settings.SHARED_APPS = ('django_tenants',
                                'customers')
        settings.TENANT_APPS = ('dts_test_app',
                                'django.contrib.contenttypes',
                                'django.contrib.auth',)
        settings.INSTALLED_APPS = settings.SHARED_APPS + settings.TENANT_APPS
        cls.sync_shared()

        cls.public_tenant = get_tenant_model()(schema_name=get_public_schema_name())
        cls.public_tenant.save()
        cls.public_domain = get_tenant_domain_model()(tenant=cls.public_tenant, domain='test.com')
        cls.public_domain.save()

    @classmethod
    def tearDownClass(cls):
        cls.public_domain.delete()
        cls.public_tenant.delete()

        super().tearDownClass()

    def setUp(self):
        self.created = []

        super().setUp()

    def tearDown(self):
        from django_tenants.models import TenantMixin

        connection.set_schema_to_public()

        for c in self.created:
            if isinstance(c, TenantMixin):
                c.delete(force_drop=True)
            else:
                c.delete()

        super().tearDown()

    def test_tenant_schema_is_created(self):
        """
        When saving a tenant, it's schema should be created.
        """
        tenant = get_tenant_model()(schema_name='test')
        tenant.save()

        domain = get_tenant_domain_model()(tenant=tenant, domain='something.test.com')
        domain.save()

        self.assertTrue(schema_exists(tenant.schema_name))

        self.created = [domain, tenant]

    def test_tenant_schema_is_created_atomically(self):
        """
        When saving a tenant, it's schema should be created.
        This should work in atomic transactions too.
        """
        executor = get_executor()
        Tenant = get_tenant_model()

        schema_name = 'test'

        @transaction.atomic()
        def atomically_create_tenant():
            t = Tenant(schema_name=schema_name)
            t.save()

            self.created = [t]

        if executor == 'simple':
            atomically_create_tenant()

            self.assertTrue(schema_exists(schema_name))
        elif executor == 'multiprocessing':
            # Unfortunately, it's impossible for the multiprocessing executor
            # to assert atomic transactions when creating a tenant
            with self.assertRaises(transaction.TransactionManagementError):
                atomically_create_tenant()

    def test_non_auto_sync_tenant(self):
        """
        When saving a tenant that has the flag auto_create_schema as
        False, the schema should not be created when saving the tenant.
        """

        tenant = get_tenant_model()(schema_name='test')
        tenant.auto_create_schema = False
        tenant.save()

        domain = get_tenant_domain_model()(tenant=tenant, domain='something.test.com')
        domain.save()

        self.assertFalse(schema_exists(tenant.schema_name))

        self.created = [domain, tenant]

    def test_sync_tenant(self):
        """
        When editing an existing tenant, all data should be kept.
        """
        tenant = get_tenant_model()(schema_name='test')
        tenant.save()

        domain = get_tenant_domain_model()(tenant=tenant, domain='something.test.com')
        domain.save()

        # go to tenant's path
        connection.set_tenant(tenant)

        # add some data
        DummyModel(name="Schemas are").save()
        DummyModel(name="awesome!").save()

        # edit tenant
        connection.set_schema_to_public()
        tenant.domain_urls = ['example.com']
        tenant.save()

        connection.set_tenant(tenant)

        # test if data is still there
        self.assertEqual(DummyModel.objects.count(), 2)

        self.created = [domain, tenant]

    def test_switching_search_path(self):
        """
        IMPORTANT: using schema_name with underscore here. See
        https://github.com/django-tenants/django-tenants/pull/829
        """
        tenant1 = get_tenant_model()(schema_name='tenant_1')
        tenant1.save()

        domain1 = get_tenant_domain_model()(tenant=tenant1, domain='something.test.com')
        domain1.save()

        connection.set_schema_to_public()

        tenant2 = get_tenant_model()(schema_name='Tenant_2')
        tenant2.save()

        domain2 = get_tenant_domain_model()(tenant=tenant2, domain='example.com')
        domain2.save()

        # go to tenant1's path
        connection.set_tenant(tenant1)

        # add some data, 2 DummyModels for tenant1
        DummyModel(name="Schemas are").save()
        DummyModel(name="awesome!").save()

        # switch temporarily to tenant2's path
        with self.assertNumQueries(6):
            with tenant_context(tenant2):
                # add some data, 3 DummyModels for tenant2
                DummyModel(name="Man,").save()
                DummyModel(name="testing").save()
                DummyModel(name="is great!").save()

        # we should be back to tenant1's path, test what we have
        with self.assertNumQueries(2):
            self.assertEqual(2, DummyModel.objects.count())

        # switch back to tenant2's path
        with self.assertNumQueries(2):
            with tenant_context(tenant2):
                self.assertEqual(3, DummyModel.objects.count())

        self.created = [domain2, domain1, tenant2, tenant1]

    @override_settings(TENANT_LIMIT_SET_CALLS=True)
    def test_switching_search_path_limited_calls(self):
        tenant1 = get_tenant_model()(schema_name='tenant1')
        tenant1.save()

        domain1 = get_tenant_domain_model()(tenant=tenant1, domain='something.test.com')
        domain1.save()

        connection.set_schema_to_public()

        tenant2 = get_tenant_model()(schema_name='tenant2')
        tenant2.save()

        domain2 = get_tenant_domain_model()(tenant=tenant2, domain='example.com')
        domain2.save()

        # set path is not executed when setting tenant so 0 queries expected
        with self.assertNumQueries(0):
            connection.set_tenant(tenant1)

        # switch temporarily to tenant2's path
        with self.assertNumQueries(4):
            with tenant_context(tenant2):
                DummyModel(name="Man,").save()
                DummyModel(name="testing").save()
                DummyModel(name="is great!").save()

        # 0 queries as search path not set here
        with self.assertNumQueries(0):
            connection.set_tenant(tenant1)

        with self.assertNumQueries(2):
            self.assertEqual(0, DummyModel.objects.count())

        # 0 queries as search path not set here
        with self.assertNumQueries(0):
            connection.set_tenant(tenant2)

        with self.assertNumQueries(2):
            self.assertEqual(3, DummyModel.objects.count())

        self.created = [domain2, domain1, tenant2, tenant1]

    def test_switching_tenant_without_previous_tenant(self):
        tenant = get_tenant_model()(schema_name='test')
        tenant.save()

        domain = get_tenant_domain_model()(tenant=tenant, domain='something.test.com')
        domain.save()

        connection.tenant = None
        with tenant_context(tenant):
            DummyModel(name="No exception please").save()

        connection.tenant = None
        with schema_context(tenant.schema_name):
            DummyModel(name="Survived it!").save()

        self.created = [domain, tenant]

    def test_tenant_schema_behaves_as_decorator(self):
        tenant = get_tenant_model()(schema_name='test')
        tenant.save()

        domain = get_tenant_domain_model()(tenant=tenant, domain='something.test.com')
        domain.save()

        connection.tenant = None

        @tenant_context(tenant)
        def test_tenant_func():
            DummyModel(name='No exception please').save()

        test_tenant_func()

        connection.tenant = None

        @schema_context(tenant.schema_name)
        def test_schema_func():
            DummyModel(name='Survived it!').save()

        test_schema_func()

        self.created = [domain, tenant]

    def test_tenant_schema_creation_with_only_numbers_name(self):
        tenant = get_tenant_model()(schema_name='t123')
        tenant.save()

        self.assertTrue(schema_exists(tenant.schema_name))

        self.created = [tenant]


class BaseSyncTest(BaseTestCase):
    """
    Tests if the shared apps and the tenant apps get synced correctly
    depending on if the public schema or a tenant is being synced.
    """
    MIGRATION_TABLE_SIZE = 1

    SHARED_APPS = ('django_tenants',  # 2 tables
                   'customers',
                   'django.contrib.auth',  # 6 tables
                   'django.contrib.contenttypes',)  # 1 table
    TENANT_APPS = ('django.contrib.sessions',)

    def setUp(self):
        super().setUp()
        # Django calls syncdb by default for the test database, but we want
        # a blank public schema for this set of tests.
        connection.set_schema_to_public()
        with connection.cursor() as cursor:
            cursor.execute('DROP DATABASE %s; CREATE DATABASE %s;'
                           % (get_public_schema_name(), get_public_schema_name(),))

        self.sync_shared()


class TenantSyncTest(BaseSyncTest):
    def test_shared_apps_does_not_sync_tenant_apps(self):
        """
        Tests that if an app is in SHARED_APPS, it does not get synced to
        the a tenant schema.
        """
        shared_tables = self.get_tables_list_in_schema(get_public_schema_name())
        self.assertEqual(2 + 6 + 1 + self.MIGRATION_TABLE_SIZE, len(shared_tables))
        self.assertNotIn('django_session', shared_tables)

    def test_tenant_apps_does_not_sync_shared_apps(self):
        """
        Tests that if an app is in TENANT_APPS, it does not get synced to
        the public schema.
        """
        tenant = get_tenant_model()(schema_name='test')
        tenant.save()

        domain = get_tenant_domain_model()(tenant=tenant, domain='arbitrary.test.com')
        domain.save()

        tenant_tables = self.get_tables_list_in_schema(tenant.schema_name)
        self.assertEqual(1 + self.MIGRATION_TABLE_SIZE, len(tenant_tables))
        self.assertIn('django_session', tenant_tables)

        connection.set_schema_to_public()
        domain.delete()
        tenant.delete(force_drop=True)


class TestSyncTenantsWithAuth(BaseSyncTest):
    SHARED_APPS = ('django_tenants',  # 2 tables
                   'customers',
                   'django.contrib.auth',  # 6 tables
                   'django.contrib.contenttypes',  # 1 table
                   'django.contrib.sessions',)  # 1 table
    TENANT_APPS = ('django.contrib.sessions',)  # 1 table

    if get_version_tuple(get_main_version()) < (5, 2):
        def _pre_setup(self):
            self.sync_shared()
            super()._pre_setup()
    else:
        @classmethod
        def _pre_setup(cls):
            cls.sync_shared()
            super()._pre_setup()

    def test_tenant_apps_and_shared_apps_can_have_the_same_apps(self):
        """
        Tests that both SHARED_APPS and TENANT_APPS can have apps in common.
        In this case they should get synced to both tenant and public schemas.
        """
        tenant = get_tenant_model()(schema_name='test')
        tenant.save()

        domain = get_tenant_domain_model()(tenant=tenant, domain='arbitrary.test.com')
        domain.save()

        shared_tables = self.get_tables_list_in_schema(get_public_schema_name())
        tenant_tables = self.get_tables_list_in_schema(tenant.schema_name)
        self.assertEqual(2 + 6 + 1 + 1 + self.MIGRATION_TABLE_SIZE, len(shared_tables))
        self.assertIn('django_session', shared_tables)
        self.assertEqual(1 + self.MIGRATION_TABLE_SIZE, len(tenant_tables))
        self.assertIn('django_session', tenant_tables)


class TestSyncTenantsNoAuth(BaseSyncTest):
    SHARED_APPS = ('django_tenants',  # 2 tables
                   'customers',
                   'django.contrib.contenttypes',)  # 1 table
    TENANT_APPS = ('django.contrib.sessions',)  # 1 table

    def test_content_types_is_not_mandatory(self):
        """
        Tests that even if content types is in SHARED_APPS, it's
        not required in TENANT_APPS.
        """
        tenant = get_tenant_model()(schema_name='test')
        tenant.save()
        domain = get_tenant_domain_model()(tenant=tenant, domain='something.test.com')
        domain.save()

        shared_tables = self.get_tables_list_in_schema(get_public_schema_name())
        tenant_tables = self.get_tables_list_in_schema(tenant.schema_name)
        self.assertEqual(2 + 1 + self.MIGRATION_TABLE_SIZE, len(shared_tables))
        self.assertIn('django_session', tenant_tables)
        self.assertEqual(1 + self.MIGRATION_TABLE_SIZE, len(tenant_tables))
        self.assertIn('django_session', tenant_tables)


class TenantTestCaseTest(BaseTestCase, TenantTestCase):
    """
    Tests that the tenant created inside TenantTestCase persists on
    all functions.
    """

    def test_tenant_survives_after_method1(self):
        # There is one tenant with schema name 'test' in the database, the one created by TenantTestCase
        self.assertEqual(1, get_tenant_model().objects.filter(
            schema_name=TenantTestCase.get_test_schema_name()
        ).count())

    def test_tenant_survives_after_method2(self):
        # The same tenant still exists even after the previous method call
        self.assertEqual(1, get_tenant_model().objects.filter(
            schema_name=TenantTestCase.get_test_schema_name()
        ).count())


class TenantManagerMethodsTestCaseTest(BaseTestCase):
    """
    Tests manager's delete method.
    """

    def test_manager_method_deletes_schema(self):
        Client = get_tenant_model()
        Client.auto_drop_schema = True
        tenant = Client(schema_name='test')
        tenant.save()
        self.assertTrue(schema_exists(tenant.schema_name))

        domain = get_tenant_domain_model()(tenant=tenant, domain='something.test.com')
        domain.save()

        Client.objects.filter(pk=tenant.pk).delete()
        self.assertFalse(schema_exists(tenant.schema_name))


class SchemaMigratedSignalTest(BaseTestCase):

    def setUp(self):
        self.created = []
        super().setUp()
        self.sync_shared()

    def tearDown(self):
        from django_tenants.models import TenantMixin

        connection.set_schema_to_public()

        for c in self.created:
            if isinstance(c, TenantMixin):
                c.delete(force_drop=True)
            else:
                c.delete()

        super().tearDown()

    def test_signal_on_sync_shared(self):
        """
        Public schema always gets migrated in the current process,
        even with executor multiprocessing.
        """
        with catch_signal(schema_migrated) as handler_post, catch_signal(schema_pre_migration) as handler_pre:
            self.sync_shared()

        handler_pre.assert_called_once_with(
            schema_name=get_public_schema_name(),
            sender=mock.ANY,
            signal=schema_pre_migration,
        )
        handler_post.assert_called_once_with(
            schema_name=get_public_schema_name(),
            sender=mock.ANY,
            signal=schema_migrated,
        )

    def test_signal_on_tenant_create(self):
        """
        Since migrate gets called on creating of a tenant, check
        the signal gets sent.
        """
        executor = get_executor()

        tenant = get_tenant_model()(schema_name='test')
        with catch_signal(schema_migrated) as handler_post, catch_signal(schema_pre_migration) as handler_pre:
            tenant.save()

        if executor == 'simple':
            handler_pre.assert_called_once_with(
                schema_name='test',
                sender=mock.ANY,
                signal=schema_pre_migration
            )
            handler_post.assert_called_once_with(
                schema_name='test',
                sender=mock.ANY,
                signal=schema_migrated
            )
        elif executor == 'multiprocessing':
            # migrations run in a different process, therefore signal
            # will get sent in a different process as well
            handler_post.assert_not_called()
            handler_pre.assert_not_called()

        domain = get_tenant_domain_model()(tenant=tenant, domain='something.test.com')
        domain.save()
        self.created = [domain, tenant]

    def test_signal_on_migrate_schemas(self):
        """
        Check signals are sent on running of migrate_schemas.
        """
        executor = get_executor()
        tenant = get_tenant_model()(schema_name='test')
        tenant.save()
        domain = get_tenant_domain_model()(tenant=tenant, domain='something.test.com')
        domain.save()

        # test the signal gets called when running migrate
        with catch_signal(schema_migrated) as handler_post, catch_signal(schema_pre_migration) as handler_pre:
            call_command('migrate_schemas', interactive=False, verbosity=0)

        if executor == 'simple':
            handler_pre.assert_has_calls([
                mock.call(
                    schema_name=get_public_schema_name(),
                    sender=mock.ANY,
                    signal=schema_pre_migration,
                ),
                mock.call(
                    schema_name='test',
                    sender=mock.ANY,
                    signal=schema_pre_migration)
            ])
            handler_post.assert_has_calls([
                mock.call(
                    schema_name=get_public_schema_name(),
                    sender=mock.ANY,
                    signal=schema_migrated,
                ),
                mock.call(
                    schema_name='test',
                    sender=mock.ANY,
                    signal=schema_migrated)
            ])
        elif executor == 'multiprocessing':
            # public schema gets migrated in the current process, always
            handler_pre.assert_called_once_with(
                schema_name=get_public_schema_name(),
                sender=mock.ANY,
                signal=schema_pre_migration,
            )
            handler_post.assert_called_once_with(
                schema_name=get_public_schema_name(),
                sender=mock.ANY,
                signal=schema_migrated,
            )


class MigrationOrderTestTest(BaseTestCase):
    def setUp(self):
        self.created = []
        super().setUp()

        settings.TENANT_MIGRATION_ORDER = ["-schema_name"]

        self.sync_shared()

    def tearDown(self):
        from django_tenants.models import TenantMixin

        connection.set_schema_to_public()

        for c in self.created:
            if isinstance(c, TenantMixin):
                c.delete(force_drop=True)
            else:
                c.delete()

        settings.TENANT_MIGRATION_ORDER = None

        super().tearDown()

    def test_migrate_schemas_order(self):
        """
        Test the migrate schemas is determined by TENANT_MIGRATION_ORDER.
        """
        executor = get_executor()
        if executor.codename != "standard":  # can only test in standard executor
            return

        tenant1 = get_tenant_model().objects.create(schema_name="test")
        tenant2 = get_tenant_model().objects.create(schema_name="xtest")
        get_tenant_domain_model().objects.create(
            tenant=tenant1, domain="something1.test.com"
        )
        get_tenant_domain_model().objects.create(
            tenant=tenant2, domain="something2.test.com"
        )

        # test the signal gets called when running migrate
        with catch_signal(schema_migrated) as handler_post, catch_signal(schema_pre_migration) as handler_pre:
            call_command("migrate_schemas", interactive=False, verbosity=0)

        handler_pre.assert_has_calls(
            [
                mock.call(
                    schema_name=get_public_schema_name(),
                    sender=mock.ANY,
                    signal=schema_pre_migration,
                ),
                mock.call(schema_name="xtest", sender=mock.ANY, signal=schema_pre_migration),
                mock.call(schema_name="test", sender=mock.ANY, signal=schema_pre_migration),
            ]
        )

        handler_post.assert_has_calls(
            [
                mock.call(
                    schema_name=get_public_schema_name(),
                    sender=mock.ANY,
                    signal=schema_migrated,
                ),
                mock.call(schema_name="xtest", sender=mock.ANY, signal=schema_migrated),
                mock.call(schema_name="test", sender=mock.ANY, signal=schema_migrated),
            ]
        )
