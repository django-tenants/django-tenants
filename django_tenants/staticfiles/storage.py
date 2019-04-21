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

    @property  # Not cached like in parent class
    def base_location(self):
        return utils.parse_tenant_config_path(self.relative_static_root)

    @property  # Not cached like in parent class
    def base_url(self):
        url_ = settings.STATIC_URL
        if not url_.endswith('/'):
            url_ += '/'

        return url_
