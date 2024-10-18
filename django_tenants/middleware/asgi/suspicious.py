from django.core.exceptions import DisallowedHost
from django_tenants.middleware.asgi.main import ASGITenantMainMiddleware


class ASGISuspiciousTenantMiddleware(ASGITenantMainMiddleware):

    """
    Middleware that handles suspicious multi-tenancy for ASGI applications.

    Extend the TenantMiddleware in scenario where you need to configure
    ``ALLOWED_HOSTS`` to allow ANY domain_url to be used because your tenants
    can bring any custom domain with them, as opposed to all tenants being a
    subdomain of a common base.
    See https://github.com/bernardopires/django-tenant-schemas/pull/269 for
    discussion on this middleware.

    PS: ASGISuspiciousTenantMiddleware must wrapped the http value (get_asgi_application()) of 
    the `ProtocolTypeRouter` class which is the entry point of asgi application instance. 
    This ensures that the middleware is being called first in the Django request-response 
    cycle made by the user.
    """
    TENANT_NOT_FOUND_EXCEPTION = DisallowedHost
