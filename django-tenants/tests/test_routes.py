from django.conf import settings
from django.test.client import RequestFactory
from tenant_schemas import get_public_schema_name

from tenant_schemas.middleware import TenantMiddleware
from tenant_schemas.tests.models import Tenant
from tenant_schemas.tests.testcases import BaseTestCase


class RoutesTestCase(BaseTestCase):
    @classmethod
    def setUpClass(cls):
        super(RoutesTestCase, cls).setUpClass()
        settings.SHARED_APPS = ('tenant_schemas', )
        settings.TENANT_APPS = ('dts_test_app',
                                'django.contrib.contenttypes',
                                'django.contrib.auth', )
        settings.INSTALLED_APPS = settings.SHARED_APPS + settings.TENANT_APPS
        cls.sync_shared()
        cls.public_tenant = Tenant(domain_url='test.com', schema_name=get_public_schema_name())
        cls.public_tenant.save()

    def setUp(self):
        super(RoutesTestCase, self).setUp()
        self.factory = RequestFactory()
        self.tm = TenantMiddleware()

        self.tenant_domain = 'tenant.test.com'
        self.tenant = Tenant(domain_url=self.tenant_domain, schema_name='test')
        self.tenant.save()

    def test_tenant_routing(self):
        """
        Request path should not be altered.
        """
        request_url = '/any/request/'
        request = self.factory.get('/any/request/',
                                   HTTP_HOST=self.tenant_domain)
        self.tm.process_request(request)

        self.assertEquals(request.path_info, request_url)

        # request.tenant should also have been set
        self.assertEquals(request.tenant, self.tenant)

    def test_public_schema_routing(self):
        """
        Request path should not be altered.
        """
        request_url = '/any/request/'
        request = self.factory.get('/any/request/',
                                   HTTP_HOST=self.public_tenant.domain_url)
        self.tm.process_request(request)

        self.assertEquals(request.path_info, request_url)

        # request.tenant should also have been set
        self.assertEquals(request.tenant, self.public_tenant)
