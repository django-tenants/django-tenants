from django.core.exceptions import DisallowedHost, ImproperlyConfigured
from django.db import connection

from django_tenants.middleware import TenantMainMiddleware
from django_tenants.utils import (
    get_public_schema_name,
    get_subfolder_prefix,
    get_tenant_model,
)


class TenantSubfolderMiddleware(TenantMainMiddleware):

    """
    This middleware should be placed at the very top of the middleware stack.
    Selects the proper tenant using the path subfolder prefix. Can fail in
    various ways which is better than corrupting or revealing data.
    """

    def __init__(self, get_response) -> None:
        super().__init__(get_response)
        if not get_subfolder_prefix():
            raise ImproperlyConfigured(
                '"TenantSubfolderMiddleware" requires "TENANT_SUBFOLDER_PREFIX" '
                "present and non-empty in settings",
            )

    def get_tenant(self, tenant_model, schema_name):
        return tenant_model.objects.get(schema_name=schema_name)

    def process_request(self, request):
        # Short circuit if tenant is already set by another middleware.
        # This allows for multiple tenant-resolving middleware chained together.
        if hasattr(request, "tenant"):
            return

        connection.set_schema_to_public()
        try:
            hostname = self.hostname_from_request(request)
        except DisallowedHost:
            from django.http import HttpResponseNotFound
            return HttpResponseNotFound()
        tenant_model = get_tenant_model()
        subfolder_prefix_path = "/{}/".format(get_subfolder_prefix())

        is_public = False
        # We are in the public tenant
        if not request.path_info.startswith(subfolder_prefix_path):
            try:
                tenant = self.get_tenant(tenant_model, get_public_schema_name())
            except tenant_model.DoesNotExist:
                raise self.TENANT_NOT_FOUND_EXCEPTION("Unable to find public tenant")
            is_public = True
        # We are in a specific tenant
        else:
            path_chunks = request.path_info[len(subfolder_prefix_path):].split("/")
            tenant_subfolder = path_chunks[0]
            try:
                tenant = self.get_tenant(tenant_model, tenant_subfolder)
            except tenant_model.DoesNotExist:
                self.no_tenant_found(request, tenant_subfolder)

            tenant.domain_subfolder = tenant_subfolder
            request.path_info = request.path_info[len(subfolder_prefix_path) + len(tenant.domain_subfolder):]

        tenant.domain_url = hostname
        request.tenant = tenant
        connection.set_tenant(request.tenant)
        self.setup_url_routing(request, force_public=is_public)
