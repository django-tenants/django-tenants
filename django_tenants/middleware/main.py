from django.conf import settings
from django.db import connection
from django.http import Http404
from django.urls import set_urlconf
from django.utils.deprecation import MiddlewareMixin

from django_tenants.utils import remove_www, get_public_schema_name, get_tenant_domain_model, get_tenants_type, \
    has_multi_type_tenants


class TenantMainMiddleware(MiddlewareMixin):
    TENANT_NOT_FOUND_EXCEPTION = Http404
    """
    This middleware should be placed at the very top of the middleware stack.
    Selects the proper database schema using the request host. Can fail in
    various ways which is better than corrupting or revealing data.
    """

    @staticmethod
    def hostname_from_request(request):
        """ Extracts hostname from request. Used for custom requests filtering.
            By default removes the request's port and common prefixes.
        """
        return remove_www(request.get_host().split(':')[0])

    def get_tenant(self, domain_model, hostname):
        domain = domain_model.objects.select_related('tenant').get(domain=hostname)
        return domain.tenant

    def process_request(self, request):
        # Connection needs first to be at the public schema, as this is where
        # the tenant metadata is stored.
        public_schema_name = get_public_schema_name()
        connection.set_schema_to_public()
        hostname = self.hostname_from_request(request)

        domain_model = get_tenant_domain_model()
        try:
            tenant = self.get_tenant(domain_model, hostname)
        except domain_model.DoesNotExist:
            raise self.TENANT_NOT_FOUND_EXCEPTION('No tenant for hostname "%s"' % hostname)

        tenant.domain_url = hostname
        request.tenant = tenant
        connection.set_tenant(request.tenant)

        if has_multi_type_tenants():
            tenant_types = get_tenants_type()

            # Do we have a public-specific urlconf?
            if 'URLCONF' in tenant_types[public_schema_name] and request.tenant.schema_name == get_public_schema_name():
                request.urlconf = settings.PUBLIC_SCHEMA_URLCONF
            else:
                request.urlconf = tenant_types[public_schema_name]['URLCONF']
            set_urlconf(request.urlconf)

        else:
            if hasattr(settings, 'PUBLIC_SCHEMA_URLCONF') and request.tenant.schema_name == get_public_schema_name():
                request.urlconf = settings.PUBLIC_SCHEMA_URLCONF


