from django.core.exceptions import ObjectDoesNotExist
from django.db import connection
from django.http import Http404
from django.urls import set_urlconf, clear_url_caches
from django_tenants.middleware import TenantMainMiddleware
from django_tenants.urlresolvers import get_subfolder_urlconf
from django_tenants.utils import (
    get_public_schema_name,
    get_tenant_model,
    get_tenant_domain_model,
)

class TenantDirectFolderMiddleware(TenantMainMiddleware):
    """
    This middleware should be placed at the very top of the middleware stack.
    Selects the proper tenant using the path direct folder. Can fail in
    various ways which is better than corrupting or revealing data.
    """

    TENANT_NOT_FOUND_EXCEPTION = Http404

    def __init__(self, get_response=None):
        super().__init__(get_response)
        self.get_response = get_response

    def process_request(self, request):
        # Short circuit if tenant is already set by another middleware.
        # This allows for multiple tenant-resolving middleware chained together.
        if hasattr(request, "tenant"):
            return

        connection.set_schema_to_public()

        urlconf = None

        tenant_model = get_tenant_model()
        domain_model = get_tenant_domain_model()
        hostname = self.hostname_from_request(request)
        path_chunks = request.path.split("/")
        tenant_subfolder = path_chunks[1]

        try:
            tenant = self.get_tenant(domain_model=domain_model, hostname=tenant_subfolder)

            tenant.domain_url = hostname
            tenant.domain_subfolder = tenant_subfolder
            urlconf = get_subfolder_urlconf(tenant)
        except ObjectDoesNotExist:
            try:
                tenant = tenant_model.objects.get(schema_name=get_public_schema_name())
            except ObjectDoesNotExist:
                return self.no_tenant_found(request, hostname=tenant_subfolder)

        request.tenant = tenant
        self.setup_url_routing(request)

        connection.set_tenant(request.tenant)
        clear_url_caches()  # Required to remove previous tenant prefix from cache, if present

        if urlconf:
            request.urlconf = urlconf
            set_urlconf(urlconf)

    def no_tenant_found(self, request, hostname):
        """ What should happen if no tenant is found.
        This makes it easier if you want to override the default behavior """
        raise self.TENANT_NOT_FOUND_EXCEPTION('No tenant for subfolder "%s"' % hostname)