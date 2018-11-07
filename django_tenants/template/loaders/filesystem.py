"""
Wrapper for loading templates from the filesystem in a multi-tenant setting.
"""


from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.template.loaders.filesystem import Loader as BaseLoader

from django_tenants import utils


class Loader(BaseLoader):

    def __init__(self, engine, dirs=None):
        super().__init__(engine)

        if dirs is None:
            try:
                # Use directories configured via MULTITENANT_TEMPLATE_DIRS
                dirs = [utils.parse_tenant_config_path(dir_) for dir_ in settings.MULTITENANT_TEMPLATE_DIRS]
            except AttributeError:
                raise ImproperlyConfigured(
                    "To use %s.%s you must define the MULTITENANT_TEMPLATE_DIRS"
                    % (__name__, Loader.__name__)
                )
        self.dirs = dirs
