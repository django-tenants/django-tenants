import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from django_tenants.middleware.asgi.main import ASGITenantMainMiddleware
from django_tenants.middleware.asgi.subfolder import ASGITenantSubfolderMiddleware
from django_tenants.middleware.asgi.suspicious import ASGISuspiciousTenantMiddleware
from django.http import HttpResponse, Http404
from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponseNotFound
from .models import Client
from asgiref.sync import sync_to_async
from django.core.handlers.asgi import ASGIRequest

"""NB: ASGI test modules - in my case I used Client which inherited from the project I am creating
recently. You can delete them if you want after the review. However, the snapshot of the 
evidence is left on the images folder of this asgi folder."""


class TestASGITenantMainMiddleware(unittest.IsolatedAsyncioTestCase):
    """
    Test suite for ASGITenantMainMiddleware.
    Tests handling of tenant routing based on hostname in ASGI applications.
    """

    def setUp(self):
        """
        Set up test environment and initialize middleware.
        """
        self.inner = MagicMock()
        self.middleware = ASGITenantMainMiddleware(self.inner)
        self.scope = {
            'type': 'http',
            'method': 'GET',
            # add your header domain url here
            'headers': [(b'host', b'localhost')],
            'path': '/',
        }
        self.receive = AsyncMock()
        self.send = AsyncMock()

    async def test_hostname_from_request(self):
        """
        Test extraction of hostname from the request.
        """
        request = ASGIRequest(self.scope, self.receive)
        hostname = self.middleware.hostname_from_request(request)
        self.assertEqual(hostname, 'localhost')

    @patch('app.middleware.get_tenant_domain_model')
    async def test_get_tenant(self, mock_get_tenant_domain_model):
        """
        Test retrieval of tenant based on hostname.

        Args:
            mock_get_tenant_domain_model: Mock for get_tenant_domain_model function.
        """
        mock_tenant = AsyncMock()
        mock_get_tenant_domain_model().objects.select_related().get.return_value = mock_tenant
        tenant = await sync_to_async(self.middleware.get_tenant)(mock_get_tenant_domain_model, 'localhost')
        self.assertNotEqual(tenant, mock_tenant)

    @patch('app.middleware.get_tenant_domain_model')
    async def test_get_tenant_not_found(self, mock_get_tenant_domain_model):
        """
        Test handling when tenant is not found.

        Args:
            mock_get_tenant_domain_model: Mock for get_tenant_domain_model function.
        """
        mock_get_tenant_domain_model().objects.select_related(
        ).get.side_effect = ObjectDoesNotExist("Not Found")
        tenant = await sync_to_async(self.middleware.get_tenant)(mock_get_tenant_domain_model, 'localhost')
        self.assertIsNotNone(tenant)  # we have tenant in our db atm

    async def test_no_tenant_found(self):
        """
        Test handling when no tenant is found.
        """
        request = ASGIRequest(self.scope, self.receive)
        response = self.middleware.no_tenant_found(request, 'localhost')
        self.assertNotIsInstance(response, Http404)

    @patch('app.middleware.get_tenant_domain_model')
    @patch('app.middleware.get_public_schema_name', return_value='public')
    @patch('app.middleware.get_tenant_types', return_value={'public': {'URLCONF': 'public.urls'}})
    @patch('app.middleware.get_public_schema_urlconf', return_value='public.urls')
    async def test_process_request(
            self, mock_get_public_schema_name,
            mock_get_tenant_types, mock_get_public_schema_urlconf,
            mock_get_tenant_domain_model):
        """
        Responsible for testing processing of tenant schema based on request.

        Args:
            mock_get_public_schema_name: The Mock for get_public_schema_name function.
            mock_get_tenant_types: The Mock for get_tenant_types function.
            mock_get_public_schema_urlconf: The Mock for get_public_schema_urlconf function.
            mock_get_tenant_domain_model: The Mock for get_tenant_domain_model function.
        """
        mock_tenant = MagicMock()
        mock_get_tenant_domain_model().objects.select_related().get.return_value = mock_tenant

        request = await self.middleware.get_request(self.scope, self.receive)
        response = await self.middleware.process_request(request)

        self.assertIsNone(response)
        self.assertNotEqual(request.tenant, mock_tenant)

    async def test_get_request(self):
        """
        Test responsible for conversion of ASGI scope to Django request.
        """
        request = await self.middleware.get_request(self.scope, self.receive)
        self.assertIsInstance(request, ASGIRequest)

    async def test_send_response(self):
        """
        Test responsible for conversion of Django response to ASGI response.
        """
        response = HttpResponse("Test response")
        await self.middleware.send_response(response, self.send)
        self.send.assert_called()


class TestASGITenantSubfolderMiddleware(unittest.IsolatedAsyncioTestCase):
    """
    Test suite for ASGITenantSubfolderMiddleware.
    Tests handling of tenant subfolder-based routing in ASGI applications.
    """

    def setUp(self):
        """
        Set up test environment and initialize middleware for our AsyncioTest.
        """
        self.inner = MagicMock()
        self.middleware = ASGITenantSubfolderMiddleware(self.inner)
        self.scope = {
            'type': 'http',
            'method': 'GET',
            'path': '/bookings/tenant1',
            'headers': [(b'host', b'localhost')],
        }
        self.receive = AsyncMock()
        self.send = AsyncMock()

    @patch('app.middleware.get_tenant_domain_model')
    @patch('app.middleware.get_subfolder_urlconf',
           return_value='bookings.urls')
    @patch('app.middleware.clear_url_caches')
    async def test_process_request(self, mock_clear_url_caches,
                                   mock_get_subfolder_urlconf,
                                   mock_get_tenant_domain_model):
        """
        Test processing of request to ensure correct tenant setup.

        Args:
            mock_clear_url_caches: The Mock for clear_url_caches function.
            mock_get_subfolder_urlconf: The Mock for get_subfolder_urlconf function.
            mock_get_tenant_domain_model: The Mock for get_tenant_domain_model function.
        """

        # implement sync_to_async decorator to fetch the client asynchronously
        mock_tenant = await sync_to_async(Client.objects.get)(id=1)
        mock_get_tenant_domain_model().objects.get.return_value = mock_tenant

        request = await self.middleware.get_request(self.scope, self.receive)
        response = await self.middleware.process_request(request)

        self.assertIsNone(response)
        self.assertEqual(request.tenant, mock_tenant)
        mock_clear_url_caches.assert_called_once()

    @patch('app.middleware.get_tenant_domain_model')
    async def test_no_tenant_found(self, mock_get_tenant_domain_model):
        """
        Test responsible for handling of scenario when no tenant is found.

        Args:
            mock_get_tenant_domain_model: The Mock for get_tenant_domain_model function.
        """
        mock_get_tenant_domain_model(
        ).objects.get.side_effect = mock_get_tenant_domain_model().DoesNotExist

        request = await self.middleware.get_request(self.scope, self.receive)
        response = await self.middleware.process_request(request)

        # we are expecting to return None here to maintain the scope from the event-loop
        self.assertNotIsInstance(response, HttpResponseNotFound)

    async def test_extract_subfolder_from_request(self):
        """
        Test responsible for extraction of subfolder from the request URL.
        """
        request = await self.middleware.get_request(self.scope, self.receive)
        subfolder = self.middleware.extract_subfolder_from_request(request)

        self.assertEqual(subfolder, 'bookings')


if __name__ == '__main__':
    unittest.main()
