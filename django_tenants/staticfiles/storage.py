import os

from django.contrib.staticfiles.utils import check_settings
from django.core.files.storage import FileSystemStorage

from django.conf import settings
from django.utils.functional import cached_property

from django_tenants import utils


class TenantStaticFilesStorage(FileSystemStorage):
    """
    Implementation that extends core Django's StaticFilesStorage for multi-tenant setups.
    """

    @cached_property
    def relative_static_root(self):
        try:
            return settings.MULTITENANT_RELATIVE_STATIC_ROOT
        except AttributeError:
            # MULTITENANT_RELATIVE_STATIC_ROOT is an optional setting, use the default value if none provided
            # Use %s instead of "" to avoid raising exception every time in parse_tenant_config_path()
            return "%s"

    @property
    def base_url(self):
        if self._base_url is not None and not self._base_url.endswith('/'):
            self._base_url += '/'
        _url = self._value_or_setting(self._base_url, settings.STATIC_URL)

        _url = os.path.join(_url,
                            utils.parse_tenant_config_path(self.relative_static_root))
        if not _url.endswith("/"):
            _url += "/"

        check_settings(_url)

        return _url

    @property  # not cached like in parent class
    def location(self):
        _location = os.path.join(settings.STATIC_ROOT,
                                 utils.parse_tenant_config_path(self.relative_static_root))
        return os.path.abspath(_location)

    def listdir(self, path):
        """
        More forgiving wrapper for parent class implementation that does not insist on
        each tenant having its own static files dir.
        """
        try:
            return super(TenantStaticFilesStorage, self).listdir(path)
        except FileNotFoundError:
            # Having static files for each tenant is optional - ignore.
            return [], []
