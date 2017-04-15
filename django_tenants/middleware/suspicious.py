from django.core.exceptions import DisallowedHost
from django_tenants.middleware import TenantMainMiddleware


class SuspiciousTenantMiddleware(TenantMainMiddleware):
    """
    Extend the TenantMiddleware in scenario where you need to configure
    ``ALLOWED_HOSTS`` to allow ANY domain_url to be used because your tenants
    can bring any custom domain with them, as opposed to all tenants being a
    subdomain of a common base.
    See https://github.com/bernardopires/django-tenant-schemas/pull/269 for
    discussion on this middleware.
    """
    TENANT_NOT_FOUND_EXCEPTION = DisallowedHost
