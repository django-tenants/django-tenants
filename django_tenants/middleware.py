from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import connections, DEFAULT_DB_ALIAS
from django.shortcuts import get_object_or_404
from .utils import get_tenant_model, remove_www, get_public_schema_name, get_tenant_domain_model


class TenantMiddleware(object):
    """
    This middleware should be placed at the very top of the middleware stack.
    Selects the proper database schema using the request host. Can fail in
    various ways which is better than corrupting or revealing data.
    """
    def hostname_from_request(self, request):
        """ Extracts hostname from request. Used for custom requests filtering.
            By default removes the request's port and common prefixes.
        """
        return remove_www(request.get_host().split(':')[0])

    def process_request(self, request):
        # what type of config are we looking at? session or url based?
        if settings.TENANT_SELECTION_METHOD == 'session':
            connections[DEFAULT_DB_ALIAS].set_schema_to_public()

            connections[settings.TENANT_DATABASE].set_schema(
                request.session.get('SELECTED_SCHEMA', 'public'))

        else:
            # Connection needs first to be at the public schema, as this is where
            # the tenant metadata is stored.
            connections[DEFAULT_DB_ALIAS].set_schema_to_public()
            hostname = self.hostname_from_request(request)

            domain = get_object_or_404(get_tenant_domain_model().objects.select_related('tenant'),
                                       domain=hostname)
            request.tenant = domain.tenant
            connections[settings.TENANT_DATABASE].set_schema(request.tenant.schema_name)

            # Content type can no longer be cached as public and tenant schemas
            # have different models. If someone wants to change this, the cache
            # needs to be separated between public and shared schemas. If this
            # cache isn't cleared, this can cause permission problems. For example,
            # on public, a particular model has id 14, but on the tenants it has
            # the id 15. if 14 is cached instead of 15, the permissions for the
            # wrong model will be fetched.
            ContentType.objects.clear_cache()

        # Do we have a public-specific urlconf?
        if hasattr(settings, 'PUBLIC_SCHEMA_URLCONF') and request.tenant.schema_name == get_public_schema_name():
            request.urlconf = settings.PUBLIC_SCHEMA_URLCONF
