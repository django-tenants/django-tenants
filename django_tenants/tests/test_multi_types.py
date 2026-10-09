import copy

from django.apps import apps
from django.conf import settings
from django.test.client import RequestFactory
from django.test.utils import override_settings

from django_tenants.middleware import TenantMainMiddleware
from django_tenants.tests.testcases import BaseTestCase
from django_tenants.utils import get_tenant_model, get_tenant_domain_model, get_public_schema_name, tenant_context
from dts_multi_type2.models import TypeTwoOnly
from dts_test_app.models import DummyModel


class MultiTypeBaseTestCase(BaseTestCase):
    """Sets up the multi type tenant configuration, without creating any tenant."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        delattr(settings, 'SHARED_APPS')
        delattr(settings, 'TENANT_APPS')

        settings.HAS_MULTI_TYPE_TENANTS = True
        settings.MULTI_TYPE_DATABASE_FIELD = 'type'  # needs to be a char field length depends of the max type value

        tenant_types = {
            "public": {  # this is the name of the public schema from get_public_schema_name
                "APPS": ['django_tenants',
                         'customers'],
                "URLCONF": "dts_test_project.urls",
            },
            "type1": {
                "APPS": ['dts_test_app',
                         'django.contrib.contenttypes',
                         'django.contrib.auth', ],
                "URLCONF": "dts_test_project.urls",
            },
            "type2": {
                "APPS": ['dts_multi_type2',
                         'django.contrib.contenttypes',
                         'django.contrib.auth', ],
                "URLCONF": "dts_test_project.urls",
            },

        }

        settings.TENANT_TYPES = tenant_types

        installed_apps = []
        for schema in tenant_types:
            installed_apps += [app for app in tenant_types[schema]["APPS"] if app not in installed_apps]
        settings.INSTALLED_APPS = installed_apps
        cls.available_apps = settings.INSTALLED_APPS

        # TransactionTestCase.setUpClass already restricted the app registry for the first
        # test of the class, back when available_apps still held the single type apps. Redo
        # it now the types are known, otherwise that first test runs -- and migrates its
        # tenants -- without the apps of every type.
        apps.unset_available_apps()
        apps.set_available_apps(cls.available_apps)

        cls.sync_shared()

    @classmethod
    def tearDownClass(cls):
        from django.db import connection

        connection.set_schema_to_public()
        delattr(settings, 'HAS_MULTI_TYPE_TENANTS')
        delattr(settings, 'MULTI_TYPE_DATABASE_FIELD')
        delattr(settings, 'TENANT_TYPES')
        super().tearDownClass()


class MultiTypeTestCase(MultiTypeBaseTestCase):
    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()
        self.tm = TenantMainMiddleware(lambda r: r)
        print(settings.INSTALLED_APPS)
        self.public_tenant = get_tenant_model()(schema_name=get_public_schema_name(),
                                                type='public')
        self.public_tenant.save()
        self.public_domain = get_tenant_domain_model()(domain='test.com',
                                                       tenant=self.public_tenant)
        self.public_domain.save()
        self.tenant_domain = 'tenant.test.com'
        self.tenant = get_tenant_model()(schema_name='test')
        self.tenant.save()
        self.domain = get_tenant_domain_model()(tenant=self.tenant, domain=self.tenant_domain)
        self.domain.save()

        self.tenant_domain2 = 'tenant2.test.com'
        self.tenant2 = get_tenant_model()(schema_name='test2',
                                          type='type2')
        self.tenant2.save()
        self.domain2 = get_tenant_domain_model()(tenant=self.tenant2, domain=self.tenant_domain2)
        self.domain2.save()

    def tearDown(self):
        from django.db import connection
        connection.set_schema_to_public()

        self.domain.delete()
        self.tenant.delete(force_drop=True)
        self.domain2.delete()
        self.tenant2.delete(force_drop=True)

        self.public_domain.delete()
        self.public_tenant.delete()

        super().tearDown()

    def test_multi_routing(self):
        """
        Request path should not be altered.
        """
        request_url = '/any/request/'
        request = self.factory.get('/any/request/',
                                   HTTP_HOST=self.tenant_domain)
        self.tm.process_request(request)

        self.assertEqual(request.path_info, request_url)

        # request.tenant should also have been set
        self.assertEqual(request.tenant, self.tenant)

    def test_tenant_routing(self):
        """
        Request path should not be altered.
        """
        request_url = '/any/request/'
        request = self.factory.get('/any/request/',
                                   HTTP_HOST=self.tenant_domain)
        self.tm.process_request(request)

        self.assertEqual(request.path_info, request_url)

        # request.tenant should also have been set
        self.assertEqual(request.tenant, self.tenant)

    def test_public_schema_routing(self):
        """
        Request path should not be altered.
        """
        request_url = '/any/request/'
        request = self.factory.get('/any/request/',
                                   HTTP_HOST=self.public_domain.domain)
        self.tm.process_request(request)

        self.assertEqual(request.path_info, request_url)

        # request.tenant should also have been set
        self.assertEqual(request.tenant, self.public_tenant)

    def test_type2_with_type2(self):
        """
        Writing to type2 model should be ok
        """

        with tenant_context(self.tenant2):
            TypeTwoOnly(name='hello')

    # For some reason the migrations are using the wrong settings hence I can't get this test to work
    # If someone would like to fix this I would be grateful :)
    # def test_type2_with_type1(self):
    #     """
    #     Writing to type2 model shouldn't work
    #     """
    #     with tenant_context(self.tenant):
    #         put the correct exception her
    #         TypeTwoOnly(name='hello')


class MultiTypeBaseSchemaTestCase(MultiTypeBaseTestCase):
    """
    Creating a tenant by cloning a template schema, when the types don't share one.

    A type1 template holds none of a type2 tenant's tables, so each type names its
    own under TENANT_TYPES[type]['BASE_SCHEMA']. See #533.
    """

    def setUp(self):
        super().setUp()
        self.created = []
        self.type1_template = self.create_tenant('type1_template', 'type1')
        self.type2_template = self.create_tenant('type2_template', 'type2')

    def tearDown(self):
        from django.db import connection

        connection.set_schema_to_public()
        for tenant in reversed(self.created):
            tenant.delete(force_drop=True)

        super().tearDown()

    def create_tenant(self, schema_name, tenant_type):
        tenant = get_tenant_model()(schema_name=schema_name, type=tenant_type)
        tenant.save(verbosity=0)
        self.created.append(tenant)
        return tenant

    @staticmethod
    def tenant_types_with_templates(**base_schemas):
        tenant_types = copy.deepcopy(settings.TENANT_TYPES)
        for tenant_type, base_schema in base_schemas.items():
            tenant_types[tenant_type]['BASE_SCHEMA'] = base_schema
        return tenant_types

    def test_each_type_is_cloned_from_the_template_of_its_own_type(self):
        with tenant_context(self.type1_template):
            DummyModel(name='from the type1 template').save()
        with tenant_context(self.type2_template):
            TypeTwoOnly(name='from the type2 template').save()

        tenant_types = self.tenant_types_with_templates(type1='type1_template',
                                                        type2='type2_template')
        with override_settings(TENANT_CREATION_FAKES_MIGRATIONS=True, TENANT_TYPES=tenant_types):
            type1_tenant = self.create_tenant('cloned_type1', 'type1')
            type2_tenant = self.create_tenant('cloned_type2', 'type2')

        with tenant_context(type1_tenant):
            self.assertTrue(DummyModel.objects.filter(name='from the type1 template').exists())
        with tenant_context(type2_tenant):
            self.assertTrue(TypeTwoOnly.objects.filter(name='from the type2 template').exists())

        # neither may have been cloned from the other type's template
        self.assertNotIn('dts_multi_type2_typetwoonly',
                         self.get_tables_list_in_schema('cloned_type1'))
        self.assertNotIn('dts_test_app_dummymodel',
                         self.get_tables_list_in_schema('cloned_type2'))

    def test_a_type_without_a_template_of_its_own_still_runs_its_migrations(self):
        tenant_types = self.tenant_types_with_templates(type1='type1_template')

        with override_settings(TENANT_CREATION_FAKES_MIGRATIONS=True, TENANT_TYPES=tenant_types):
            self.create_tenant('migrated_type2', 'type2')

        self.assertIn('dts_multi_type2_typetwoonly',
                      self.get_tables_list_in_schema('migrated_type2'))

    def test_a_type_without_a_template_of_its_own_falls_back_to_tenant_base_schema(self):
        with tenant_context(self.type2_template):
            TypeTwoOnly(name='from the shared template').save()

        tenant_types = self.tenant_types_with_templates(type1='type1_template')
        with override_settings(TENANT_CREATION_FAKES_MIGRATIONS=True,
                               TENANT_TYPES=tenant_types,
                               TENANT_BASE_SCHEMA='type2_template'):
            tenant = self.create_tenant('fallback_type2', 'type2')

        with tenant_context(tenant):
            self.assertTrue(TypeTwoOnly.objects.filter(name='from the shared template').exists())
