import warnings

from django_tenants.middleware.main import TenantMainMiddleware


class TenantMiddleware(TenantMainMiddleware):
    warnings.warn("This class has been renamed to TenantMainMiddleware",
                  DeprecationWarning)
