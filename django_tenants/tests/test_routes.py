from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.test.client import RequestFactory

from django_tenants.middleware import TenantMainMiddleware, TenantSubfolderMiddleware
from django_tenants.tests.testcases import BaseTestCase
from django_tenants.utils import get_tenant_model, get_tenant_domain_model, get_public_schema_name


class RoutesTestCase(BaseTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        settings.SHARED_APPS = ('django_tenants',
                                'customers')
        settings.TENANT_APPS = ('dts_test_app',
                                'django.contrib.contenttypes',
                                'django.contrib.auth', )
        settings.INSTALLED_APPS = settings.SHARED_APPS + settings.TENANT_APPS
        cls.available_apps = settings.INSTALLED_APPS
        cls.sync_shared()
        cls.public_tenant = get_tenant_model()(schema_name=get_public_schema_name())
        cls.public_tenant.save()
        cls.public_domain = get_tenant_domain_model()(domain='test.com', tenant=cls.public_tenant)
        cls.public_domain.save()

    @classmethod
    def tearDownClass(cls):
        from django.db import connection

        connection.set_schema_to_public()

        cls.public_domain.delete()
        cls.public_tenant.delete()

        super().tearDownClass()

    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()
        self.tm = TenantMainMiddleware(lambda r: r)

        self.tenant_domain = 'tenant.test.com'
        self.tenant = get_tenant_model()(schema_name='test')
        self.tenant.save()
        self.domain = get_tenant_domain_model()(tenant=self.tenant, domain=self.tenant_domain)
        self.domain.save()

    def tearDown(self):
        from django.db import connection

        connection.set_schema_to_public()

        self.domain.delete()
        self.tenant.delete(force_drop=True)

        super().tearDown()

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


class SubfolderRoutesTestCase(BaseTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        settings.SHARED_APPS = ('django_tenants',
                                'customers')
        settings.TENANT_APPS = ('dts_test_app',
                                'django.contrib.contenttypes',
                                'django.contrib.auth', )
        settings.INSTALLED_APPS = settings.SHARED_APPS + settings.TENANT_APPS
        cls.available_apps = settings.INSTALLED_APPS
        settings.TENANT_SUBFOLDER_PREFIX = 'clients/'

    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()
        self.tsf = TenantSubfolderMiddleware(lambda r: r)

        self.sync_shared()
        self.public_tenant = get_tenant_model()(schema_name=get_public_schema_name())
        self.public_tenant.save()
        self.public_domain = get_tenant_domain_model()(domain='test.com', tenant=self.public_tenant)
        self.public_domain.save()

        self.tenant_domain = 'tenant.test.com'
        self.tenant = get_tenant_model()(schema_name='test')
        self.tenant.save()
        self.domain = get_tenant_domain_model()(tenant=self.tenant, domain=self.tenant_domain)
        self.domain.save()

    def tearDown(self):
        from django.db import connection

        connection.set_schema_to_public()

        self.domain.delete()
        self.tenant.delete(force_drop=True)

        self.public_domain.delete()
        self.public_tenant.delete()

        super().tearDown()

    def test_tenant_routing(self):
        """
        Request path should not be altered.
        """
        request_url = '/clients/tenant.test.com/any/request/'
        request = self.factory.get('/clients/tenant.test.com/any/request/',
                                   HTTP_HOST=self.public_domain.domain)
        self.tsf.process_request(request)

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
        self.tsf.process_request(request)

        self.assertEqual(request.path_info, request_url)

        # request.tenant should also have been set
        self.assertEqual(request.tenant, self.public_tenant)

    def test_missing_tenant(self):
        """
        Request path should not be altered.
        """
        request = self.factory.get('/clients/not-found/any/request/',
                                   HTTP_HOST=self.public_domain.domain)

        with self.assertRaises(self.tsf.TENANT_NOT_FOUND_EXCEPTION):
            self.tsf.process_request(request)


class SubfolderRoutesWithoutPrefixTestCase(BaseTestCase):
    def test_subfolder_routing_without_prefix(self):
        """
        Should raise ImproperlyConfigured if no sensible TENANT_SUBFOLDER_PREFIX
        is found in settings.
        """
        settings.TENANT_SUBFOLDER_PREFIX = None
        with self.assertRaises(ImproperlyConfigured):
            TenantSubfolderMiddleware(lambda r: r)
        settings.TENANT_SUBFOLDER_PREFIX = '  '
        with self.assertRaises(ImproperlyConfigured):
            TenantSubfolderMiddleware(lambda r: r)
