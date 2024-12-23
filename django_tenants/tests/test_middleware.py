from django.http import HttpResponseNotFound, JsonResponse
from django.test.utils import override_settings
from django.views import View

from django_tenants.test.cases import FastTenantTestCase
from django_tenants.test.client import TenantClient


def custom_not_found_view(request):
    return JsonResponse({'error': 'Custom 404 Not Found'}, status=404)


class CustomNotFoundView(View):
    def get(self, request):
        return JsonResponse({'error': 'Custom 404 Not Found'}, status=404)


class InvalidHostname(FastTenantTestCase):
    @classmethod
    def get_test_tenant_domain(cls):
        # This domain is not valid according to RFC 1034/1035
        return '_.fast-test.com'

    @classmethod
    def get_test_schema_name(cls):
        return '_'

    def setUp(self):
        super().setUp()
        self.client = TenantClient(self.tenant)

    def test_invalid_hostname_should_return_404(self):
        response = self.client.get('/')

        self.assertIsInstance(response, HttpResponseNotFound)


@override_settings(ALLOWED_HOSTS=['nonexistent.fast-test.com', 'tenant.fast-test.com'])
class WhenTenantNotFound(FastTenantTestCase):
    @classmethod
    def get_test_tenant_domain(cls):
        return 'tenant.fast-test.com'

    def setUp(self):
        super().setUp()
        self.client = TenantClient(self.tenant)

    @override_settings(DEFAULT_NOT_FOUND_TENANT_VIEW='django_tenants.tests.test_middleware.custom_not_found_view')
    @override_settings(ALLOWED_HOSTS=['nonexistent.fast-test.com', 'tenant.fast-test.com'])
    def test_custom_function_based_view_is_shown(self):
        response = self.client.get('/', HTTP_HOST='nonexistent.fast-test.com')
        self.assertIsInstance(response, JsonResponse)
        self.assertEqual(response.json(), {'error': 'Custom 404 Not Found'})

    @override_settings(DEFAULT_NOT_FOUND_TENANT_VIEW='django_tenants.tests.test_middleware.CustomNotFoundView')
    @override_settings(ALLOWED_HOSTS=['nonexistent.fast-test.com', 'tenant.fast-test.com'])
    def test_custom_class_based_view_is_shown(self):
        response = self.client.get('/', HTTP_HOST='nonexistent.fast-test.com')
        self.assertIsInstance(response, JsonResponse)
        self.assertEqual(response.json(), {'error': 'Custom 404 Not Found'})
