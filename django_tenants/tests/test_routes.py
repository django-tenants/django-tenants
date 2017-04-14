from django.conf import settings
from django.test.client import RequestFactory

from django_tenants.middleware import TenantMiddleware
from django_tenants.tests.testcases import BaseTestCase
from django_tenants.utils import get_tenant_model, get_tenant_domain_model, get_public_schema_name


class RoutesTestCase(BaseTestCase):
    @classmethod
    def setUpClass(cls):
        super(RoutesTestCase, cls).setUpClass()
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

    def setUp(self):
        super(RoutesTestCase, self).setUp()
        self.factory = RequestFactory()
        self.tm = TenantMiddleware()

        self.tenant_domain = 'tenant.test.com'
        self.tenant = get_tenant_model()(schema_name='test')
        self.tenant.save(verbosity=BaseTestCase.get_verbosity())
        self.domain = get_tenant_domain_model()(tenant=self.tenant, domain=self.tenant_domain)
        self.domain.save(verbosity=BaseTestCase.get_verbosity())

    def tearDown(self):
        from django.db import connection

        connection.set_schema_to_public()

        self.domain.delete()
        self.tenant.delete(force_drop=True)

        super(RoutesTestCase, self).tearDown()

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
