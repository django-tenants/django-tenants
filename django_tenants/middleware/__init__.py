import warnings

from django_tenants.middleware.main import TenantMainMiddleware


class TenantMiddleware(TenantMainMiddleware):
    def __init__(self, *args, **kwargs):
        warnings.warn("This class has been renamed to TenantCoreMiddleware",
                      DeprecationWarning)
        TenantMainMiddleware.__init__(*args, **kwargs)
