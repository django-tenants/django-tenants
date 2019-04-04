import os

from django.conf import settings
from django.utils.functional import cached_property
from django.core.files.storage import FileSystemStorage

from django_tenants import utils


class TenantFileSystemStorage(FileSystemStorage):
    """
    Implementation that extends core Django's FileSystemStorage for multi-tenant setups.
    """
    @cached_property
    def relative_media_root(self):
        try:
            return settings.MULTITENANT_RELATIVE_MEDIA_ROOT
        except AttributeError:
            # MULTITENANT_RELATIVE_MEDIA_ROOT is an optional setting, use the default value if none provided
            # Use %s instead of "" to avoid raising exception every time in parse_tenant_config_path()
            return "%s"

    @property  # not cached like in parent class
    def base_url(self):
        _url = super().base_url
        _url = os.path.join(_url,
                            utils.parse_tenant_config_path(self.relative_media_root))
        if not _url.endswith('/'):
            _url += '/'
        return _url

    @property  # not cached like in parent class
    def location(self):
        _location = os.path.join(super().location,
                                 utils.parse_tenant_config_path(self.relative_media_root))
        return os.path.abspath(_location)
