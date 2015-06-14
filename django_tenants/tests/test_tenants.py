import django
from django.conf import settings
from django.contrib.auth.models import User
from django.db import connection

from dts_test_app.models import DummyModel, ModelWithFkToPublicUser
from django_tenants.test.cases import TenantTestCase
from django_tenants.tests.models import Tenant, NonAutoSyncTenant
from django_tenants.tests.testcases import BaseTestCase
from django_tenants.utils import tenant_context, schema_context, schema_exists, get_tenant_model, get_public_schema_name


class TenantDataAndSettingsTest(BaseTestCase):
    """
    Tests if the tenant model settings work properly and if data can be saved
    and persisted to different tenants.
    """

    @classmethod
    def setUpClass(cls):
        super(TenantDataAndSettingsTest, cls).setUpClass()
        settings.SHARED_APPS = ('django_tenants', )
        settings.TENANT_APPS = ('dts_test_app',
                                'django.contrib.contenttypes',
                                'django.contrib.auth', )
        settings.INSTALLED_APPS = settings.SHARED_APPS + settings.TENANT_APPS
        cls.sync_shared()
        Tenant(domain_urls=['test.com'], schema_name=get_public_schema_name()).save()

    def test_tenant_schema_is_created(self):
        """
        When saving a tenant, it's schema should be created.
        """
        tenant = Tenant(domain_urls=['something.test.com'], schema_name='test')
        tenant.save()

        self.assertTrue(schema_exists(tenant.schema_name))

    def test_non_auto_sync_tenant(self):
        """
        When saving a tenant that has the flag auto_create_schema as
        False, the schema should not be created when saving the tenant.
        """
        self.assertFalse(schema_exists('non_auto_sync_tenant'))

        tenant = NonAutoSyncTenant(domain_urls=['something.test.com'],
                                   schema_name='test')
        tenant.save()

        self.assertFalse(schema_exists(tenant.schema_name))

    def test_sync_tenant(self):
        """
        When editing an existing tenant, all data should be kept.
        """
        tenant = Tenant(domain_urls=['something.test.com'], schema_name='test')
        tenant.save()

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
        self.assertEquals(DummyModel.objects.count(), 2)

    def test_switching_search_path(self):
        tenant1 = Tenant(domain_urls=['something.test.com'],
                         schema_name='tenant1')
        tenant1.save()

        connection.set_schema_to_public()
        tenant2 = Tenant(domain_urls=['example.com'], schema_name='tenant2')
        tenant2.save()

        # go to tenant1's path
        connection.set_tenant(tenant1)

        # add some data, 2 DummyModels for tenant1
        DummyModel(name="Schemas are").save()
        DummyModel(name="awesome!").save()

        # switch temporarily to tenant2's path
        with tenant_context(tenant2):
            # add some data, 3 DummyModels for tenant2
            DummyModel(name="Man,").save()
            DummyModel(name="testing").save()
            DummyModel(name="is great!").save()

        # we should be back to tenant1's path, test what we have
        self.assertEqual(2, DummyModel.objects.count())

        # switch back to tenant2's path
        with tenant_context(tenant2):
            self.assertEqual(3, DummyModel.objects.count())

    def test_switching_tenant_without_previous_tenant(self):
        tenant = Tenant(domain_urls=['something.test.com'], schema_name='test')
        tenant.save()

        connection.tenant = None
        with tenant_context(tenant):
            DummyModel(name="No exception please").save()

        connection.tenant = None
        with schema_context(tenant.schema_name):
            DummyModel(name="Survived it!").save()


class TenantSyncTest(BaseTestCase):
    """
    Tests if the shared apps and the tenant apps get synced correctly
    depending on if the public schema or a tenant is being synced.
    """
    MIGRATION_TABLE_SIZE = 1

    def test_shared_apps_does_not_sync_tenant_apps(self):
        """
        Tests that if an app is in SHARED_APPS, it does not get synced to
        the a tenant schema.
        """
        settings.SHARED_APPS = ('django_tenants',  # 2 tables
                                'django.contrib.auth',  # 6 tables
                                'django.contrib.contenttypes', )  # 1 table
        settings.TENANT_APPS = ('django.contrib.sessions', )
        settings.INSTALLED_APPS = settings.SHARED_APPS + settings.TENANT_APPS
        self.sync_shared()

        shared_tables = self.get_tables_list_in_schema(get_public_schema_name())
        self.assertEqual(2+6+1+self.MIGRATION_TABLE_SIZE, len(shared_tables))
        self.assertNotIn('django_session', shared_tables)

    def test_tenant_apps_does_not_sync_shared_apps(self):
        """
        Tests that if an app is in TENANT_APPS, it does not get synced to
        the public schema.
        """
        settings.SHARED_APPS = ('django_tenants',
                                'django.contrib.auth',
                                'django.contrib.contenttypes', )
        settings.TENANT_APPS = ('django.contrib.sessions', )  # 1 table
        settings.INSTALLED_APPS = settings.SHARED_APPS + settings.TENANT_APPS
        self.sync_shared()
        tenant = Tenant(domain_urls=['arbitrary.test.com'], schema_name='test')
        tenant.save()

        tenant_tables = self.get_tables_list_in_schema(tenant.schema_name)
        self.assertEqual(1+self.MIGRATION_TABLE_SIZE, len(tenant_tables))
        self.assertIn('django_session', tenant_tables)

    def test_tenant_apps_and_shared_apps_can_have_the_same_apps(self):
        """
        Tests that both SHARED_APPS and TENANT_APPS can have apps in common.
        In this case they should get synced to both tenant and public schemas.
        """
        settings.SHARED_APPS = ('django_tenants',  # 2 tables
                                'django.contrib.auth',  # 6 tables
                                'django.contrib.contenttypes',  # 1 table
                                'django.contrib.sessions', )  # 1 table
        settings.TENANT_APPS = ('django.contrib.sessions', )  # 1 table
        settings.INSTALLED_APPS = settings.SHARED_APPS + settings.TENANT_APPS
        self.sync_shared()
        tenant = Tenant(domain_urls=['arbitrary.test.com'], schema_name='test')
        tenant.save()

        shared_tables = self.get_tables_list_in_schema(get_public_schema_name())
        tenant_tables = self.get_tables_list_in_schema(tenant.schema_name)
        self.assertEqual(2+6+1+1+self.MIGRATION_TABLE_SIZE, len(shared_tables))
        self.assertIn('django_session', shared_tables)
        self.assertEqual(1+self.MIGRATION_TABLE_SIZE, len(tenant_tables))
        self.assertIn('django_session', tenant_tables)

    def test_content_types_is_not_mandatory(self):
        """
        Tests that even if content types is in SHARED_APPS, it's
        not required in TENANT_APPS.
        """
        settings.SHARED_APPS = ('django_tenants',  # 2 tables
                                'django.contrib.contenttypes', )  # 1 table
        settings.TENANT_APPS = ('django.contrib.sessions', )  # 1 table
        settings.INSTALLED_APPS = settings.SHARED_APPS + settings.TENANT_APPS
        self.sync_shared()
        tenant = Tenant(domain_urls=['something.test.com'], schema_name='test')
        tenant.save()

        shared_tables = self.get_tables_list_in_schema(get_public_schema_name())
        tenant_tables = self.get_tables_list_in_schema(tenant.schema_name)
        self.assertEqual(2+1 + self.MIGRATION_TABLE_SIZE, len(shared_tables))
        self.assertIn('django_session', tenant_tables)
        self.assertEqual(1+self.MIGRATION_TABLE_SIZE, len(tenant_tables))
        self.assertIn('django_session', tenant_tables)


class SharedAuthTest(BaseTestCase):
    @classmethod
    def setUpClass(cls):
        super(SharedAuthTest, cls).setUpClass()
        settings.SHARED_APPS = ('django_tenants',
                                'django.contrib.auth',
                                'django.contrib.contenttypes', )
        settings.TENANT_APPS = ('dts_test_app', )
        settings.INSTALLED_APPS = settings.SHARED_APPS + settings.TENANT_APPS
        cls.sync_shared()
        Tenant(domain_urls=['test.com'], schema_name=get_public_schema_name()).save()

        # Create a tenant
        cls.tenant = Tenant(domain_urls=['tenant.test.com'], schema_name='tenant')
        cls.tenant.save()

        # Create some users
        with schema_context(get_public_schema_name()):  # this could actually also be executed inside a tenant
            cls.user1 = User(username='arbitrary-1', email="arb1@test.com")
            cls.user1.save()
            cls.user2 = User(username='arbitrary-2', email="arb2@test.com")
            cls.user2.save()

        # Create instances on the tenant that point to the users on public
        with tenant_context(cls.tenant):
            cls.d1 = ModelWithFkToPublicUser(user=cls.user1)
            cls.d1.save()
            cls.d2 = ModelWithFkToPublicUser(user=cls.user2)
            cls.d2.save()

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
              ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage AS ccu
              ON ccu.constraint_name = tc.constraint_name
        WHERE constraint_type = 'FOREIGN KEY' AND tc.table_name=%s
        """
        cursor = connection.cursor()
        cursor.execute(sql, (ModelWithFkToPublicUser._meta.db_table, ))
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
        # There is one tenant in the database, the one created by TenantTestCase
        self.assertEquals(1, get_tenant_model().objects.all().count())

    def test_tenant_survives_after_method2(self):
        # The same tenant still exists even after the previous method call
        self.assertEquals(1, get_tenant_model().objects.all().count())
