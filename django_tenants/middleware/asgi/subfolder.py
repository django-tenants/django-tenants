
from asgiref.sync import sync_to_async
from django.db import connection
from django_tenants.utils import get_tenant_domain_model
from asgiref.sync import sync_to_async

from django.core.exceptions import ImproperlyConfigured
from django.urls import set_urlconf, clear_url_caches
from django_tenants.urlresolvers import get_subfolder_urlconf
from django_tenants.utils import (
    get_public_schema_name,
    get_tenant_domain_model,
    get_subfolder_prefix,
    get_tenant_model,

)
from django.http import Http404, HttpResponseNotFound
from django_tenants.middleware.asgi.main import ASGITenantMainMiddleware


class ASGITenantSubfolderMiddleware(ASGITenantMainMiddleware):
    """
    Middleware that handles subfolder-based multi-tenancy for ASGI applications.
    This middleware selects the appropriate tenant based on the request's subfolder.

    ASGITenantSubfolderMiddleware must wrapped the http value (get_asgi_application()) of the 
    `ProtocolTypeRouter`class which is the entry point of asgi application instance. 
    This ensures that the middleware is being called first in the Django request-response
    cycle made by the user. 

    """

    TENANT_NOT_FOUND_EXCEPTION = Http404

    def __init__(self, inner):
        super().__init__(inner)

        if not get_subfolder_prefix():
            raise ImproperlyConfigured(
                ' "TenantSubfolderMiddleware" requires "TENANT_SUBFOLDER_PREFIX" '
                "present and non-empty in settings"
            )

    @staticmethod
    def extract_subfolder_from_request(request):
        """ 
         Extracts the subfolder from the URL as a string.
        """

        path = request.path.split('/')
        return path[1] if len(path) > 1 else None

    async def process_request(self, request):
        """ This method is responsible for proccessing the tenant 
            schema based on the request subfolder """

        # Short circuit if tenant is already set by another middleware.
        # This allows for multiple tenant-resolving middleware chained together.
        if hasattr(request, "tenant"):
            return

        connection.set_schema_to_public()
        urlconf = None
        tenant_model = get_tenant_model()
        domain_model = get_tenant_domain_model()
        hostname = self.hostname_from_request(request)
        subfolder_prefix_path = f"/{get_subfolder_prefix()}/"

        # if public specific
        if not request.path.startswith(subfolder_prefix_path):
            try:
                tenant = \
                    await sync_to_async(tenant_model.objects.get)(schema_name=get_public_schema_name())
            except tenant_model.DoesNotExist:
                raise self.TENANT_NOT_FOUND_EXCEPTION(
                    "Unable to find public tenant")
            self.setup_url_routing(request, force_public=True)
        #  if tenant specific
        else:
            path_chunks = request.path[len(subfolder_prefix_path):].split("/")
            tenant_subfolder = path_chunks[0]
            try:
                tenant = await sync_to_async(self.get_tenant)(
                    domain_model=domain_model, hostname=tenant_subfolder)
            except domain_model.DoesNotExist:
                return self.no_tenant_found(request, tenant_subfolder)

            except domain_model.DoesNotExist:
                return HttpResponseNotFound()
            tenant.domain_subfolder = tenant_subfolder
            urlconf = get_subfolder_urlconf(tenant)

        tenant.domain_url = hostname
        request.tenant = tenant
        connection.set_tenant(request.tenant)
        clear_url_caches()  # Required to remove previous tenant prefix from cache, if present

        if urlconf:
            request.urlconf = urlconf
            set_urlconf(urlconf)

        return None

    def no_tenant_found(self, request, hostname):
        """ What should happen if no tenant is found.
        This makes it easier if you want to override the default behavior """

        raise self.TENANT_NOT_FOUND_EXCEPTION(
            'No tenant for subfolder "%s"' % hostname)
