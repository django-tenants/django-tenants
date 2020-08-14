import warnings

from django_tenants.middleware.main import TenantMainMiddleware
from django_tenants.middleware.subfolder import TenantSubfolderMiddleware


class TenantMiddleware(TenantMainMiddleware):
    def __init__(self, get_response=None):
        super().__init__(get_response=get_response)

        warnings.warn("This class has been renamed to TenantMainMiddleware",
                      DeprecationWarning)
