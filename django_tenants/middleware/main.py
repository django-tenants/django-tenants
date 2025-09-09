from functools import lru_cache
from django.conf import settings
from django.core.exceptions import DisallowedHost
from django.db import connection
from django.http import Http404
from django.urls import set_urlconf
from django.utils.module_loading import import_string
from django.utils.deprecation import MiddlewareMixin

from django_tenants.utils import remove_www, get_public_schema_name, get_tenant_types, \
    has_multi_type_tenants, get_tenant_domain_model, get_public_schema_urlconf


class TenantMainMiddleware(MiddlewareMixin):
    TENANT_NOT_FOUND_EXCEPTION = Http404
    """
    This middleware should be placed at the very top of the middleware stack.
    Selects the proper database schema using the request host. Can fail in
    various ways which is better than corrupting or revealing data.
    """

    @staticmethod
    @lru_cache(maxsize=128)
    def hostname_from_request_host(request_host):
        """
        Extracts hostname from request host. Used for custom requests filtering.
        By default removes the request's port and common prefixes.

        Args:
            request_host (str): The host from the request.

        Returns:
            str: The extracted hostname.
        """
        return remove_www(request_host.split(':')[0])

    def get_tenant(self, domain_model, hostname):
        """
        Retrieves the tenant associated with the given hostname.

        :param domain_model: The domain model to query.
        :param hostname: The hostname to look up.
        :return: The tenant associated with the hostname.
        """
        domain = domain_model.objects.select_related('tenant').get(domain=hostname)
        return domain.tenant

    def process_request(self, request):
        """
        Processes the incoming request to set the appropriate tenant schema.

        Connection needs first to be at the public schema, as this is where
        the tenant metadata is stored.

        :param request: The incoming HTTP request.
        :return: An HTTP response if the tenant is not found, otherwise None.
        """

        connection.set_schema_to_public()
        try:
            hostname = self.hostname_from_request_host(request.get_host())
        except DisallowedHost:
            from django.http import HttpResponseNotFound
            return HttpResponseNotFound()

        domain_model = get_tenant_domain_model()
        try:
            tenant = self.get_tenant(domain_model, hostname)
        except domain_model.DoesNotExist:
            default_tenant = self.no_tenant_found(request, hostname)
            return default_tenant

        tenant.domain_url = hostname
        request.tenant = tenant
        connection.set_tenant(request.tenant)
        self.setup_url_routing(request)

    def no_tenant_found(self, request, hostname):
        """
        Handles the case where no tenant is found for the given hostname.
        This makes it easier if you want to override the default behavior

        :param request: The incoming HTTP request.
        :param hostname: The hostname that was not found.
        :return: An HTTP response if a custom view is defined, otherwise raises an exception.
        """
        if hasattr(settings, 'DEFAULT_NOT_FOUND_TENANT_VIEW'):
            view_path = settings.DEFAULT_NOT_FOUND_TENANT_VIEW
            view = import_string(view_path)
            if hasattr(view, 'as_view'):
                response = view.as_view()(request)
            else:
                response = view(request)
            if hasattr(response, 'render'):
                response.render()
            return response
        elif hasattr(settings, 'SHOW_PUBLIC_IF_NO_TENANT_FOUND') and settings.SHOW_PUBLIC_IF_NO_TENANT_FOUND:
            self.setup_url_routing(request=request, force_public=True)
        else:
            raise self.TENANT_NOT_FOUND_EXCEPTION('No tenant for hostname "%s"' % hostname)

    @staticmethod
    def setup_url_routing(request, force_public=False):
        """
        Sets the correct url conf based on the tenant
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
