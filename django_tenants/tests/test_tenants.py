from contextlib import contextmanager
from unittest import mock

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import connection, transaction
from django.test.utils import override_settings

from django_tenants.clone import CloneSchema
from django_tenants.signals import schema_migrated, schema_migrate_message
from dts_test_app.models import DummyModel, ModelWithFkToPublicUser

from django_tenants.migration_executors import get_executor
from django_tenants.test.cases import TenantTestCase
from django_tenants.tests.testcases import BaseTestCase
from django_tenants.utils import tenant_context, schema_context, schema_exists, get_tenant_model, \
    get_public_schema_name, get_tenant_domain_model, schema_rename


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
                                'django.contrib.auth', )
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
        tenant1 = get_tenant_model()(schema_name='tenant`1')
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
        # 1 query to set search path + 3 to save data
        with self.assertNumQueries(4):
            with tenant_context(tenant2):
                DummyModel(name="Man,").save()
                DummyModel(name="testing").save()
                DummyModel(name="is great!").save()

        # 0 queries as search path not set here
        with self.assertNumQueries(0):
            connection.set_tenant(tenant1)

        # 1 set search path + 1 count
        with self.assertNumQueries(2):
            self.assertEqual(0, DummyModel.objects.count())

        # 0 queries as search path not set here
        with self.assertNumQueries(0):
            connection.set_tenant(tenant2)

        # 1 set search path + 1 count
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

    def test_tenant_schema_creation_with_sql_keyword_name(self):
        tenant = get_tenant_model()(schema_name='select')
        tenant.save()

        self.assertTrue(schema_exists(tenant.schema_name))

        self.created = [tenant]

    def test_tenant_schema_creation_with_only_numbers_name(self):
        tenant = get_tenant_model()(schema_name='123')
        tenant.save()

        self.assertTrue(schema_exists(tenant.schema_name))

        self.created = [tenant]

    def test_tenant_schema_creation_with_special_chars(self):
        """Tests using special characters in schema name."""
        schema_names = ('test-hyphen', 'test@at', 'test`backtick', 'country_BD')

        Client = get_tenant_model()
        for schema_name in schema_names:
            tenant = Client(schema_name=schema_name)
            tenant.save()
            self.assertTrue(schema_exists(tenant.schema_name))


class BaseSyncTest(BaseTestCase):
    """
    Tests if the shared apps and the tenant apps get synced correctly
    depending on if the public schema or a tenant is being synced.
    """
    MIGRATION_TABLE_SIZE = 1

    SHARED_APPS = ('django_tenants',  # 2 tables
                   'customers',
                   'django.contrib.auth',  # 6 tables
                   'django.contrib.contenttypes', )  # 1 table
    TENANT_APPS = ('django.contrib.sessions', )

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.INSTALLED_APPS = cls.SHARED_APPS + cls.TENANT_APPS

        settings.SHARED_APPS = cls.SHARED_APPS
        settings.TENANT_APPS = cls.TENANT_APPS
        settings.INSTALLED_APPS = cls.INSTALLED_APPS

        cls.available_apps = cls.INSTALLED_APPS

    def setUp(self):
        super().setUp()
        # Django calls syncdb by default for the test database, but we want
        # a blank public schema for this set of tests.
        connection.set_schema_to_public()
        with connection.cursor() as cursor:
            cursor.execute('DROP SCHEMA %s CASCADE; CREATE SCHEMA %s;'
                           % (get_public_schema_name(), get_public_schema_name(), ))

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
                   'django.contrib.sessions', )  # 1 table
    TENANT_APPS = ('django.contrib.sessions', )  # 1 table

    def _pre_setup(self):
        self.sync_shared()
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
                   'django.contrib.contenttypes', )  # 1 table
    TENANT_APPS = ('django.contrib.sessions', )  # 1 table

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


class SharedAuthTest(BaseTestCase):
    def setUp(self):
        super().setUp()

        settings.SHARED_APPS = ('django_tenants',
                                'customers',
                                'django.contrib.auth',
                                'django.contrib.contenttypes', )
        settings.TENANT_APPS = ('dts_test_app', )
        settings.INSTALLED_APPS = settings.SHARED_APPS + settings.TENANT_APPS
        self.sync_shared()
        self.public_tenant = get_tenant_model()(schema_name=get_public_schema_name())
        self.public_tenant.save()
        self.public_domain = get_tenant_domain_model()(tenant=self.public_tenant, domain='test.com')
        self.public_domain.save()

        # Create a tenant
        self.tenant = get_tenant_model()(schema_name='tenant')
        self.tenant.save()
        self.domain = get_tenant_domain_model()(tenant=self.tenant, domain='tenant.test.com')
        self.domain.save()

        # Create some users
        with schema_context(get_public_schema_name()):  # this could actually also be executed inside a tenant
            self.user1 = User(username='arbitrary-1', email="arb1@test.com")
            self.user1.save()
            self.user2 = User(username='arbitrary-2', email="arb2@test.com")
            self.user2.save()

        # Create instances on the tenant that point to the users on public
        with tenant_context(self.tenant):
            self.d1 = ModelWithFkToPublicUser(user=self.user1)
            self.d1.save()
            self.d2 = ModelWithFkToPublicUser(user=self.user2)
            self.d2.save()

    def tearDown(self):
        connection.set_schema_to_public()
        self.public_domain.delete()
        self.public_tenant.delete()
        self.domain.delete()
        self.tenant.delete(force_drop=True)

        super().tearDown()

    def test_cross_schema_constraint_gets_created(self):
        """
        Tests that a foreign key constraint gets created even for cross schema references.
        """
        sql = """
        SELECT
            tc.constraint_name, tc.table_name, kcu.column_name,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name
        FROM
            information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
              ON tc.constraint_schema = kcu.constraint_schema AND tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage AS ccu
              ON tc.constraint_schema = ccu.constraint_schema AND ccu.constraint_name = tc.constraint_name
        WHERE
            constraint_type = 'FOREIGN KEY' AND
            tc.table_name=%s AND
            ccu.table_schema=%s AND
            ccu.constraint_schema=%s
        """
        cursor = connection.cursor()
        cursor.execute(
            sql,
            (
                ModelWithFkToPublicUser._meta.db_table,
                self.public_tenant.schema_name,
                self.tenant.schema_name
            )
        )
        fk_constraints = cursor.fetchall()
        self.assertEqual(1, len(fk_constraints))

        # The foreign key should reference the primary key of the user table
        fk = fk_constraints[0]
        self.assertEqual(User._meta.db_table, fk[3])
        self.assertEqual('id', fk[4])

    def test_direct_relation_to_public(self):
        """
        Tests that a forward relationship through a foreign key to public from a model inside TENANT_APPS works.
        """
        with tenant_context(self.tenant):
            self.assertEqual(User.objects.get(pk=self.user1.id),
                             ModelWithFkToPublicUser.objects.get(pk=self.d1.id).user)
            self.assertEqual(User.objects.get(pk=self.user2.id),
                             ModelWithFkToPublicUser.objects.get(pk=self.d2.id).user)

    def test_reverse_relation_to_public(self):
        """
        Tests that a reverse relationship through a foreign keys to public from a model inside TENANT_APPS works.
        """
        with tenant_context(self.tenant):
            users = User.objects.all().select_related().order_by('id')
            self.assertEqual(ModelWithFkToPublicUser.objects.get(pk=self.d1.id),
                             users[0].modelwithfktopublicuser_set.all()[:1].get())
            self.assertEqual(ModelWithFkToPublicUser.objects.get(pk=self.d2.id),
                             users[1].modelwithfktopublicuser_set.all()[:1].get())


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


class TenantRenameSchemaTest(BaseTestCase):

    def test_rename_schema_ok(self):
        Client = get_tenant_model()
        tenant = Client(schema_name='test')
        tenant.save()
        self.assertTrue(schema_exists(tenant.schema_name))
        domain = get_tenant_domain_model()(tenant=tenant, domain='something.test.com')
        domain.save()
        schema_rename(tenant=Client.objects.filter(pk=tenant.pk).first(), new_schema_name='new_name')
        self.assertFalse(schema_exists('test'))
        self.assertTrue(schema_exists('new_name'))

    def test_rename_schema_numbers(self):
        Client = get_tenant_model()
        tenant = Client(schema_name='1234_test')
        tenant.save()
        self.assertTrue(schema_exists(tenant.schema_name))
        domain = get_tenant_domain_model()(tenant=tenant, domain='something.test.com')
        domain.save()
        schema_rename(tenant=Client.objects.filter(pk=tenant.pk).first(), new_schema_name='4321_new_name')
        self.assertFalse(schema_exists('1234_test'))
        self.assertTrue(schema_exists('4321_new_name'))


class CloneSchemaTest(BaseTestCase):
    def test_clone_schema(self):
        Client = get_tenant_model()
        tenant = Client(schema_name='source')
        tenant.save()
        self.assertTrue(schema_exists(tenant.schema_name))

        domain = get_tenant_domain_model()(tenant=tenant, domain='source.test.com')
        domain.save()
        clone_schema = CloneSchema()
        clone_schema.clone_schema(base_schema_name='source', new_schema_name='destination')

        self.assertTrue(schema_exists('source'))
        self.assertTrue(schema_exists('destination'))

    def test_clone_schema_with_existing_records_and_add_new_records_to_resulting_schema(self):
        """
        Exercises the scenario where the source schema contains records in a shared app which
        get cloned in the destination schema but the value of the PK column remains at 1 which
        causes duplicate key errors.
        See https://github.com/django-tenants/django-tenants/issues/831
        """
        Client = get_tenant_model()
        tenant = Client(schema_name='s1')
        tenant.save()

        domain = get_tenant_domain_model()(tenant=tenant, domain='s1.test.com')
        domain.save()
        self.assertTrue(schema_exists(tenant.schema_name))

        # add some records to the source schema
        with tenant_context(tenant):
            self.assertFalse(DummyModel.objects.filter(name='Administrator').exists())
            self.assertFalse(DummyModel.objects.filter(name='Tester').exists())
            DummyModel(name='Administrator').save()
            DummyModel(name='Tester').save()

        clone_schema = CloneSchema()
        clone_schema.clone_schema(base_schema_name='s1', new_schema_name='d1')
        self.assertTrue(schema_exists('destination'))

        # add some records to the destination schema
        with schema_context('d1'):
            self.assertTrue(DummyModel.objects.filter(name='Administrator').exists())
            self.assertTrue(DummyModel.objects.filter(name='Tester').exists())

            DummyModel(name='Moderator').save()


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
        with catch_signal(schema_migrated) as handler:
            self.sync_shared()

        handler.assert_called_once_with(
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
        with catch_signal(schema_migrated) as handler:
            tenant.save()

        if executor == 'simple':
            handler.assert_called_once_with(
                schema_name='test',
                sender=mock.ANY,
                signal=schema_migrated
            )
        elif executor == 'multiprocessing':
            # migrations run in a different process, therefore signal
            # will get sent in a different process as well
            handler.assert_not_called()

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
        with catch_signal(schema_migrated) as handler:
            call_command('migrate_schemas', interactive=False, verbosity=0)

        if executor == 'simple':
            handler.assert_has_calls([
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
            handler.assert_called_once_with(
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
        with catch_signal(schema_migrated) as handler:
            call_command("migrate_schemas", interactive=False, verbosity=0)

        handler.assert_has_calls(
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
