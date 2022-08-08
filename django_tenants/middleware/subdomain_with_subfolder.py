from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from django.http import Http404
from django.urls import set_urlconf, clear_url_caches
from django_tenants.middleware import TenantMainMiddleware
from django_tenants.urlresolvers import get_subfolder_urlconf
from django_tenants.utils import (
    get_public_schema_name,
    get_tenant_model,
    get_subfolder_prefix,
)


class TenantSubdomainWithSubfolderMiddleware(TenantMainMiddleware):
    """
    This middleware should be placed at the very top of the middleware stack.
    It selects the proper tenant using the path subfolder prefix or the subdomain.
    """

    def __init__(self, get_response):
        super().__init__(get_response)
        self.get_response = get_response
        if not get_subfolder_prefix():
            raise ImproperlyConfigured(
                '"TenantSubdomainWithSubfolderMiddleware" requires "TENANT_SUBFOLDER_PREFIX" '
                "present and non-empty in settings"
            )

    def process_request(self, request):
        # If tenant is already set return.
        if hasattr(request, "tenant"):
            return

        connection.set_schema_to_public()

        urlconf = None
        tenant = False

        tenant_model = get_tenant_model()
        hostname = self.hostname_from_request(request)
        subfolder_prefix_path = "/{}/".format(get_subfolder_prefix())

        # checking for subfolder prefix path
        path_chunks = request.path[len(subfolder_prefix_path):].split("/")
        tenant_subfolder = path_chunks[0]
        if request.path.startswith(subfolder_prefix_path):
            try:
                tenant = tenant_model.objects.get(schema_name=tenant_subfolder)
            except tenant_model.DoesNotExist:
                pass
            else:
                tenant.domain_subfolder = tenant_subfolder
                urlconf = get_subfolder_urlconf(tenant)
                tenant.domain_url = hostname
                request.tenant = tenant

                connection.set_tenant(request.tenant)
                clear_url_caches()  # Required to remove previous tenant prefix from cache, if present

                if urlconf:
                    request.urlconf = urlconf
                    set_urlconf(urlconf)

        # checking for subdomain
        if not tenant:
            super().process_request(request)
