import os

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.functional import cached_property

from django_tenants import utils
from django_tenants.files.storage import TenantFileSystemStorage


class TenantStaticFilesStorage(TenantFileSystemStorage):
    """
    Implementation that extends core Django's StaticFilesStorage for multi-tenant setups.

    The defaults for ``location`` and ``base_url`` are ``STATIC_ROOT`` and ``STATIC_URL``.

    """
    def _clear_cached_properties(self, setting, **kwargs):
        """Reset setting based property values."""
        super()._clear_cached_properties(settings, **kwargs)

        if setting == 'MULTITENANT_RELATIVE_STATIC_ROOT':
            self.__dict__.pop('relative_static_root', None)

    @cached_property
    def relative_static_root(self):
        try:
            return os.path.join(settings.STATIC_ROOT, settings.MULTITENANT_RELATIVE_STATIC_ROOT)
        except AttributeError:
            # MULTITENANT_RELATIVE_STATIC_ROOT is an optional setting. Use the default of just appending
            # the tenant schema_name to STATIC_ROOT if no configuration value is provided
            try:
                return settings.STATIC_ROOT
            except AttributeError:
                raise ImproperlyConfigured("You're using the staticfiles app "
                                           "without having set the STATIC_ROOT "
                                           "setting to a filesystem path.")

    @cached_property
    def relative_static_url(self):
        url = settings.STATIC_URL
        rewrite_on = False

        try:
            if settings.REWRITE_STATIC_URLS is True:
                rewrite_on = True
                try:
                    multitenant_relative_url = settings.MULTITENANT_RELATIVE_STATIC_ROOT
                except AttributeError:
                    # MULTITENANT_RELATIVE_STATIC_ROOT is an optional setting. Use the default of just appending
                    # the tenant schema_name to STATIC_ROOT if no configuration value is provided
                    multitenant_relative_url = "%s"

                url = "/" + "/".join(s.strip("/") for s in [url, multitenant_relative_url]) + "/"

        except AttributeError:
            # REWRITE_STATIC_URLS not set - ignore
            pass

        return rewrite_on, url

    @property  # Not cached like in parent class
    def base_location(self):
        return self._value_or_setting(self._location, utils.parse_tenant_config_path(self.relative_static_root))

    @property  # Not cached like in parent class
    def base_url(self):
        rewrite_on, relative_tenant_url = self.relative_static_url
        if rewrite_on:
            relative_tenant_url = utils.parse_tenant_config_path(relative_tenant_url)

        if not relative_tenant_url.endswith('/'):
            relative_tenant_url += '/'

        if self._base_url is not None and not self._base_url.endswith('/'):
            self._base_url += '/'

        return self._value_or_setting(self._base_url, relative_tenant_url)
