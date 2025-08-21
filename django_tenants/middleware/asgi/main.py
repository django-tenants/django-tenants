from django.conf import settings
from asgiref.sync import sync_to_async
from django.db import connection
from django.core.exceptions import DisallowedHost
from django_tenants.utils import get_tenant_domain_model
from asgiref.sync import sync_to_async
from django.http import HttpResponse
from django.urls import set_urlconf
from django_tenants.utils import (
    remove_www, get_public_schema_name,
    get_tenant_types,
    has_multi_type_tenants,
    get_tenant_domain_model,
    get_public_schema_urlconf,

)
from django.core.handlers.asgi import ASGIRequest
from django_tenants.middleware.asgi import CoreMiddleware


class ASGITenantMainMiddleware(CoreMiddleware):
    """
     Middleware that handles multi-tenancy for ASGI application


     This middleware selects the proper database schema using the request host. Can fail in
     various ways which is better than corrupting or revealing data.

     ASGITenantMainMiddleware must wrapped the http value (get_asgi_application()) of the `ProtocolTypeRouter`
     class which is the entry point of asgi application instance. This ensures that the middleware
     is being called first in the Django request-response cycle made by the user.

     Attrs:

        TENANT_NOT_FOUND_EXCEPTION (Exception): Exception that is raised when no tenant is found.

        inner (callable): The next ASGI application or middleware in the chain.

     Methods:
        hostname_from_request(request): This method extracts the hostname from the request

        get_tenant(domain_model, hostname): This method retrieves the tenant based on the hostname a user created.

        __call__(scope, receive, send): This method processes the incoming ASGI requests

        process_request(request): This method processes the tenant schema based on the request

        get_request(scope, receive): This method converts ASGI scope to Django request object.

        send_response(response, send): This method converts Django response to ASGI response

        no_tenant_found(request, hostname): Handles the case when no tenant is found.

        set_url_routing(request, force_public): Sets up the correct URL configuration based on the tenant.

    """

    def __init__(self, inner):
        """ Initializes the middleware with the next ASGI application or the middleware in the chain"""

        super().__init__(inner)

    @staticmethod
    def host_from_request(request) -> str:
        """ Extracts hostname from request. Used for custom requests filtering.
            By default removes the request's port and common prefixes.
        """

        return remove_www(request.get_host().split(":")[0])

    def get_tenant(self, domain_model, hostname):
        """ 
        Retrieves the tenant based on the hostname.

        Args:
            domain_model(Model): The domain model object 
            hostname (str): The hostname extracted from the request

        Returns:
            Tenant: The tenant associated with the hostname if found, or None if not found.

        """

        try:
            domain = domain_model.objects.select_related(
                'tenant').get(domain=hostname)
            return domain.tenant

        except Exception as e:
            print(f'Error fetching tenant:{e}')
            return None

    async def __call__(self, scope, receive, send):
        """ Processes incoming ASGI requests. 

        Args:
            scope(dict): The ASGI scope dictionary
            receive (callable): The receive callable
            send (callable): The send callable

        """

        if scope['type'] == 'http':
            request = await self.get_request(scope, receive)
            response = await self.process_request(request)

            if isinstance(response, HttpResponse):
                await self.send_response(response, send)
            else:
                await self.inner(scope, receive, send)

        else:
            await self.inner(scope, receive, send)

    async def process_request(self, request):
        """ 
        This method processes the tenant schema based on the request and returns 
        a django HttpResponse object if the tenant is processed or HttpResponseNotFound if not . 

        """

        connection.set_schema_to_public()
        try:
            hostname = self.hostname_from_request(request)
        except DisallowedHost:
            from django.http import HttpResponseNotFound
            return HttpResponseNotFound()

        domain_model = get_tenant_domain_model()
        try:
            tenant = await sync_to_async(self.get_tenant(domain_model, hostname))
        except domain_model.DoesNotExist:
            self.no_tenant_found(request, hostname)
            return HttpResponseNotFound()

        tenant.domain_url = hostname
        request.tenant = tenant
        connection.set_tenant(request.tenant)
        self.setup_url_routing(request)

    async def get_request(self, scope, receive):
        """ This method is responsible for converting ASGI scope to Django request. """

        return ASGIRequest(scope, receive)

    async def send_response(self, response, send):
        """ This method is responsible for converting Django response to ASGI response. """

        headers = [
            (b'content-type', response['Content-Type'].encode('latin-1'))]

        # using a forloop we need to fetch the key and value of the response
        #  items and accurately mapped them to the headers object, and the send
        # object (dict) must be awaited
        for key, value in response.items():
            headers.append([key.encode('latin-1')], value.encode('latin-1'))

        await send({
            'type': 'http.response.start',
            'status': response.status_code,
            'headers': headers
        })

        await send({
            'type': 'http.response.start',
            'status': response.status_code,
            'headers': headers
        })

    def no_tenant_found(self, request, hostname):
        """ This method handles the case when no tenant is found. """

        if hasattr(settings, 'SHOW_PUBLIC_IF_NO_TENANT_FOUND') and \
                settings.SHOW_PUBLIC_IF_NO_TENANT_FOUND:
            self.setup_url_routing(request=request, force_public=True)
        else:
            raise self.TENANT_NOT_FOUND_EXCEPTION(
                'No tenant for hostname "%s"' % hostname)

    @staticmethod
    def setup_url_routing(request, force_public=False):
        """ 
         This method sets up the correct URL configuration based on the tenant. 

        :param request:
        :param force_public
        """
        public_schema_name = get_public_schema_name()
        if has_multi_type_tenants():
            tenant_types = get_tenant_types()
            if (not hasattr(request, 'tenant') or
                    ((force_public or request.tenant.schema_name == get_public_schema_name()) and
                     'URLCONF' in tenant_types[public_schema_name])):
                request.urlconf = get_public_schema_urlconf()
            else:
                tenant_type = request.tenant.get_tenant_type()
                request.urlconf = tenant_types[tenant_type]['URLCONF']
            set_urlconf(request.urlconf)

        else:
            # Do we have a public-specific urlconf?
            if (hasattr(settings, 'PUBLIC_SCHEMA_URLCONF') and
                    (force_public or request.tenant.schema_name == get_public_schema_name())):
                request.urlconf = settings.PUBLIC_SCHEMA_URLCONF
