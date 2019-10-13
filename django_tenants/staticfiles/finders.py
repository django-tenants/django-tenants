from django.contrib.staticfiles.finders import FileSystemFinder
from django.conf import settings
from django.core.checks import Error
from collections import OrderedDict

from django.db import connection

from django_tenants import utils as tenant_utils
from django_tenants.files.storage import TenantFileSystemStorage


class TenantFileSystemFinder(FileSystemFinder):
    """
    A static files finder that uses the ``MULTITENANT_STATICFILES_DIRS`` setting
    to locate files for different tenants.

    The only difference between this and the standard FileSystemFinder implementation
    is that we need to keep references to the storage locations of the static files,
    as well as maps of dir paths to an appropriate storage instance, for each tenant.
    """
    def __init__(self, app_names=None, *args, **kwargs):
        # Don't call parent's init method as settings.STATICFILES_DIRS will be loaded
        # by the standard FileSystemFinder already.

        # Instead of initializing the locations and storages now, we'll do so lazily
        # the first time they are needed.
        self._locations = {}
        self._storages = {}

    @property
    def locations(self):
        """
        Lazy retrieval of list of locations with static files based on current tenant schema.
        :return: The list of static file dirs that have been configured for this tenant.
        """
        if self._locations.get(connection.schema_name, None) is None:
            schema_locations = []
            for root in settings.MULTITENANT_STATICFILES_DIRS:
                root = tenant_utils.parse_tenant_config_path(root)

                if isinstance(root, (list, tuple)):
                    prefix, root = root
                else:
                    prefix = ""

                if (prefix, root) not in schema_locations:
                    schema_locations.append((prefix, root))

            self._locations[connection.schema_name] = schema_locations

        return self._locations[connection.schema_name]

    @locations.setter
    def locations(self, value):
        self._locations[connection.schema_name] = value

    @property
    def storages(self):
        """
        Lazy retrieval of list of storage handlers for the current tenant.
        :return: A ,a[ pf dir paths to an appropriate storage instance.
        """
        if self._storages.get(connection.schema_name, None) is None:
            schema_storages = OrderedDict()

            for prefix, root in self.locations:
                filesystem_storage = TenantFileSystemStorage(location=root)
                filesystem_storage.prefix = prefix
                schema_storages[root] = filesystem_storage

            self._storages[connection.schema_name] = schema_storages

        return self._storages[connection.schema_name]

    @storages.setter
    def storages(self, value):
        self._storages[connection.schema_name] = value

    def check(self, **kwargs):
        """
        In addition to parent class' checks, also ensure that MULTITENANT_STATICFILES_DIRS
        is a tuple or a list.
        """
        errors = super().check(**kwargs)
        multitenant_staticfiles_dirs = settings.MULTITENANT_STATICFILES_DIRS

        if not isinstance(multitenant_staticfiles_dirs, (list, tuple)):
            errors.append(
                Error(
                    "Your MULTITENANT_STATICFILES_DIRS setting is not a tuple or list.",
                    hint="Perhaps you forgot a trailing comma?",
                )
            )

        return errors
