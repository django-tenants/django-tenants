"""
Wrapper for loading templates from the filesystem in a multi-tenant setting.
"""


from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from django.template.loaders.filesystem import Loader as BaseLoader

from django_tenants import utils


class Loader(BaseLoader):
    def __init__(self, engine, dirs=None):
        self._dirs = {}

        super().__init__(engine)

        if dirs is not None:
            self.dirs = dirs

    @property
    def dirs(self):
        """
        Lazy retrieval of list of template directories based on current tenant schema.
        :return: The list of template file dirs that have been configured for this tenant.
        """
        if self._dirs.get(connection.schema_name, None) is None:
            try:
                # Use directories configured via MULTITENANT_TEMPLATE_DIRS
                dirs = [
                    utils.parse_tenant_config_path(dir_)
                    for dir_ in settings.MULTITENANT_TEMPLATE_DIRS
                ]
            except AttributeError:
                raise ImproperlyConfigured(
                    "To use {}.{} you must define the MULTITENANT_TEMPLATE_DIRS setting.".format(
                        __name__, Loader.__name__
                    )
                )

            self.dirs = dirs

        return self._dirs[connection.schema_name]

    @dirs.setter
    def dirs(self, value):
        self._dirs[connection.schema_name] = value
