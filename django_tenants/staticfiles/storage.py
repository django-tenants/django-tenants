import os
from django.contrib.staticfiles.storage import StaticFilesStorage
from django_tenants.files.storages import TenantStorageMixin
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class TenantStaticFilesStorage(TenantStorageMixin, StaticFilesStorage):
    """
    Implementation that extends core Django's StaticFilesStorage.
    """

    def __init__(self, location=None, base_url=None, *args, **kwargs):
        super(TenantStaticFilesStorage, self).__init__(location, base_url, *args, **kwargs)
        if hasattr(settings, "MULTITENANT_RELATIVE_STATIC_ROOT"):
            self.location = os.path.join(self.location, settings.MULTITENANT_RELATIVE_STATIC_ROOT)

    """
    def path(self, name):
        if not hasattr(settings, "MULTITENANT_RELATIVE_STATIC_ROOT") or \
                not settings.MULTITENANT_RELATIVE_STATIC_ROOT:
            raise ImproperlyConfigured("You're using the TenantStaticFilesStorage "
                                       "without having set the MULTITENANT_RELATIVE_STATIC_ROOT "
                                       "setting to a filesystem path.")
        return super(TenantStaticFilesStorage, self).path(name)
    """
