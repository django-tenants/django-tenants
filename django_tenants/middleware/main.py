from django.conf import settings
from django.db import connection
from django.http import Http404
from django.urls import set_urlconf
from django.utils.deprecation import MiddlewareMixin

from django_tenants.utils import remove_www, get_public_schema_name, get_tenant_model, get_tenant_domain_model
from django_tenants.urlresolvers import subfolder_matcher, subfolder_dynamic_urlconf


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
        connection.set_schema_to_public()
        hostname = self.hostname_from_request(request)

        tenant_model = get_tenant_model()
        domain_model = get_tenant_domain_model()
        try:
            tenant = self.get_tenant(domain_model, hostname)
        except domain_model.DoesNotExist:
            raise self.TENANT_NOT_FOUND_EXCEPTION('No tenant for hostname "%s"' % hostname)

        if tenant.schema_name == get_public_schema_name():
            subfolder_match = subfolder_matcher.match(request.path)

            # Are we in a subfolder routing?
            if subfolder_match:
                subfolder = subfolder_match["schema_name"]
                try:
                    tenant = tenant_model.objects.get(schema_name=subfolder)
                except tenant_model.DoesNotExist:
                    raise self.TENANT_NOT_FOUND_EXCEPTION('No tenant for subfolder "%s"' % subfolder)

                request.urlconf = subfolder_dynamic_urlconf(tenant)
                set_urlconf(request.urlconf)

            # Do we have a public-specific urlconf?
            elif hasattr(settings, 'PUBLIC_SCHEMA_URLCONF'):
                request.urlconf = settings.PUBLIC_SCHEMA_URLCONF
                set_urlconf(request.urlconf)

        tenant.domain_url = hostname
        request.tenant = tenant

        connection.set_tenant(request.tenant)
