import os
from django.contrib.staticfiles.storage import StaticFilesStorage
from django_tenants.files.storages import TenantStorageMixin
from django.conf import settings


class TenantStaticFilesStorage(TenantStorageMixin, StaticFilesStorage):
    """
    Implementation that extends core Django's StaticFilesStorage for multi-tenant setups.
    """

    def __init__(self, location=None, base_url=None, *args, **kwargs):
        super(TenantStaticFilesStorage, self).__init__(
            location, base_url, *args, **kwargs
        )
        if hasattr(settings, "MULTITENANT_RELATIVE_STATIC_ROOT"):
            self.location = os.path.join(
                self.location, settings.MULTITENANT_RELATIVE_STATIC_ROOT
            )
