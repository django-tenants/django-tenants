import warnings

from django_tenants.files.storage import TenantFileSystemStorage as NewTenantFileSystemStorage


class TenantFileSystemStorage(NewTenantFileSystemStorage):
    """
    Deprecated - Use django_tenants.files.storage.TenantFileSystemStorage instead
    """

    def __init__(self, location=None, base_url=None, *args, **kwargs):
        super().__init__(location=location, base_url=base_url, *args, **kwargs)

        warnings.warn(
            "TenantFileSystemStorage has been moved from django_tenants.files.storages to django_tenants.files.storage.",
            DeprecationWarning
        )
