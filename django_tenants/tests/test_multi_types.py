from django.conf import settings
from django.test.client import RequestFactory

from django_tenants.middleware import TenantMainMiddleware
from django_tenants.tests.testcases import BaseTestCase
from django_tenants.utils import get_tenant_model, get_tenant_domain_model, get_public_schema_name, tenant_context
from dts_multi_type2.models import TypeTwoOnly


class MultiTypeTestCase(BaseTestCase):
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
        cls.sync_shared()

    @classmethod
    def tearDownClass(cls):
        from django.db import connection

        connection.set_schema_to_public()
        delattr(settings, 'HAS_MULTI_TYPE_TENANTS')
        delattr(settings, 'MULTI_TYPE_DATABASE_FIELD')
        delattr(settings, 'TENANT_TYPES')
        super().tearDownClass()

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

    # For some reason the migrations are using the wrong settings hence I can't get this test to worl
    # If someone would like to fix this I would be grateful :)
    # def test_type2_with_type1(self):
    #     """
    #     Writing to type2 model shouldn't work
    #     """
    #     with tenant_context(self.tenant):
    #         put the correct exception her
    #         TypeTwoOnly(name='hello')


