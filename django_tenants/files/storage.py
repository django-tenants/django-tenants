import os

from django.conf import settings
from django.utils.functional import cached_property
from django.db import connection

from django.core.files.storage import FileSystemStorage

from django_tenants import utils


class TenantFileSystemStorage(FileSystemStorage):
    """
    Implementation that extends core Django's FileSystemStorage for multi-tenant setups.
    """
    def _clear_cached_properties(self, setting, **kwargs):
        """Reset setting based property values."""
        super()._clear_cached_properties(settings, **kwargs)

        if setting == 'MULTITENANT_RELATIVE_MEDIA_ROOT':
            self.__dict__.pop('relative_media_root', None)

    @cached_property
    def relative_media_root(self):
        try:
            return os.path.join(settings.MEDIA_ROOT, settings.MULTITENANT_RELATIVE_MEDIA_ROOT)
        except AttributeError:
            # MULTITENANT_RELATIVE_MEDIA_ROOT is an optional setting, use the default value if none provided
            return settings.MEDIA_ROOT

    @cached_property
    def relative_media_url(self):
        url = settings.MEDIA_URL

        if not url.endswith('/'):
            url += '/'

        try:
            multitenant_relative_url = settings.MULTITENANT_RELATIVE_MEDIA_ROOT
        except AttributeError:
            # MULTITENANT_RELATIVE_MEDIA_ROOT is an optional setting. Use the default of just appending
            # the tenant schema_name to STATIC_ROOT if no configuration value is provided
            multitenant_relative_url = "%s"

        url = "{}{}".format(url, multitenant_relative_url)
        return url

    @property  # Not cached like in parent class
    def base_location(self):
        return self._value_or_setting(
            self._location,
            utils.parse_tenant_config_path(self.relative_media_root)
        )

    @property  # Not cached like in parent class
    def location(self):
        return os.path.abspath(self.base_location)

    @property
    def base_url(self):
        if self._base_url is not None and not self._base_url.endswith('/'):
            self._base_url += '/'

        relative_tenant_url = self.relative_media_url % connection.schema_name

        if not relative_tenant_url.endswith('/'):
            relative_tenant_url += '/'

        return self._value_or_setting(self._base_url, relative_tenant_url)

    def listdir(self, path):
        """
        More forgiving wrapper for parent class implementation that does not insist on
        each tenant having its own static files dir.
        """
        try:
            return super().listdir(path)
        except FileNotFoundError:
            # Having static files for each tenant is optional - ignore.
            return [], []
