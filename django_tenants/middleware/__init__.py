import warnings

from django_tenants.middleware.main import TenantMainMiddleware
from django_tenants.middleware.subfolder import TenantSubfolderMiddleware
from django_tenants.middleware.subdomain_with_subfolder import TenantSubdomainWithSubfolderMiddleware


class TenantMiddleware(TenantMainMiddleware):
    def __init__(self, get_response=None):
        super().__init__(get_response=get_response)

        warnings.warn("This class has been renamed to TenantMainMiddleware",
                      DeprecationWarning)
