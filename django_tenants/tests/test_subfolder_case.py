from django.test.client import RequestFactory
from django.conf import settings

from django_tenants.middleware import TenantSubfolderMiddleware
from django_tenants.test.cases import SubfolderTenantTestCase


class SubfolderTenantTestCase(SubfolderTenantTestCase):
    """Testing use of SubfolderTenantTestCase to build testcases supporting
    projects making use of TenantSubfolderMiddleware
    """

    def setUp(self) -> None:
        super().setUp()
        settings.TENANT_SUBFOLDER_PREFIX = 'clients/'
        self.factory = RequestFactory()
        self.tsf = TenantSubfolderMiddleware(lambda r: r)

    def test_tenant_routing(self):
        """
        Request path should not be altered.
        """
        request_url = '/clients/tenant.test.com/any/request/'
        request = self.factory.get('/clients/tenant.test.com/any/request/')
        self.tsf.process_request(request)

        self.assertEqual(request.path_info, request_url)

        # request.tenant should also have been set
        self.assertEqual(request.tenant, self.tenant)

    def test_public_schema_routing(self):
        """
        Request path should not be altered.
        """
        request_url = '/any/request/'
        request = self.factory.get('/any/request/')
        self.tsf.process_request(request)

        self.assertEqual(request.path_info, request_url)

        # request.tenant should also have been set
        self.assertEqual(request.tenant, self.public_tenant)

    def test_missing_tenant(self):
        """
        Request path should not be altered.
        """
        request = self.factory.get('/clients/not-found/any/request/')

        with self.assertRaises(self.tsf.TENANT_NOT_FOUND_EXCEPTION):
            self.tsf.process_request(request)
