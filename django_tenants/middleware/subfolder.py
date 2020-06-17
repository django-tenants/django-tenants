from django.conf import settings
from django.db import connection
from django.http import Http404
from django.urls import set_urlconf, clear_url_caches
from django.utils.deprecation import MiddlewareMixin

from django_tenants.urlresolvers import get_subfolder_urlconf
from django_tenants.utils import (
    remove_www,
    get_public_schema_name,
    get_tenant_model,
    get_subfolder_prefix,
)


class TenantSubfolderMiddleware(MiddlewareMixin):
    """
    This middleware should be placed at the very top of the middleware stack.
    Selects the proper tenant using the path subfolder prefix. Can fail in
    various ways which is better than corrupting or revealing data.
    """

    TENANT_NOT_FOUND_EXCEPTION = Http404

    @staticmethod
    def hostname_from_request(request):
        """ Extracts hostname from request. Used for custom requests filtering.
            By default removes the request's port and common prefixes.
        """
        return remove_www(request.get_host().split(":")[0])

    def process_request(self, request):
        # Short circuit if tenant is already set by another middleware.
        # This allows for multiple tenant-resolving middleware chained together.
        if hasattr(request, "tenant"):
            return

        connection.set_schema_to_public()

        tenant = None
        urlconf = None

        TenantModel = get_tenant_model()
        hostname = self.hostname_from_request(request)
        subfolder_prefix_path = "/{}/".format(get_subfolder_prefix())

        # We are in the public tenant
        if not request.path.startswith(subfolder_prefix_path):
            try:
                tenant = TenantModel.objects.get(schema_name=get_public_schema_name())
            except TenantModel.DoesNotExist:
                raise self.TENANT_NOT_FOUND_EXCEPTION("Unable to find public tenant")

            # Do we have a public-specific urlconf?
            if (
                hasattr(settings, "PUBLIC_SCHEMA_URLCONF")
                and request.tenant.schema_name == get_public_schema_name()
            ):
                urlconf = settings.PUBLIC_SCHEMA_URLCONF

        # We are in a specific tenant
        else:
            path_chunks = request.path[len(subfolder_prefix_path) :].split("/")
            tenant_subfolder = path_chunks[0]

            try:
                tenant = TenantModel.objects.get(domains__domain=tenant_subfolder)
            except TenantModel.DoesNotExist:
                raise self.TENANT_NOT_FOUND_EXCEPTION(
                    'No tenant for subfolder "%s"' % (tenant_subfolder or "")
                )

            urlconf = get_subfolder_urlconf(tenant)

        tenant.domain_url = hostname
        request.tenant = tenant

        connection.set_tenant(request.tenant)
        clear_url_caches()  # Required to remove previous tenant prefix from cache, if present

        if urlconf:
            request.urlconf = urlconf
            set_urlconf(urlconf)
