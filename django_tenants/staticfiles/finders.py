import os
from django.contrib.staticfiles.finders import AppDirectoriesFinder, FileSystemFinder
from django.conf import settings
from django.core.checks import Error
from collections import OrderedDict

from django.db import connection

from django_tenants import utils
from django_tenants.staticfiles.storage import TenantStaticFilesStorage

class TenantAppDirectoriesFinder(AppDirectoriesFinder):
    """
    This is a replacement for the AppDirectoriesFinder. The only difference between
    this and the standard AppDirectoriesFinder implementation is that this one will
    understand how tenant-aware file handling works and where to search for your
    files.

    In-detail explanation:

    Let's say that we have a Tenant called "Foo" (foo.com).
    When we try to access, let's say, foo.com/admin, the browser will issue a request
    to (among others) foo.com/static/foo/admin/css/base.css , instead of the
    usual request if we didn't use django-tenants (foo.com/static/admin/css/base.css).

    See the "foo" right before "admin"?

    In order for this to work as expected we must remove the "foo", as we have
    already added the path "tenants/%s/static" to the paths that Django will
    look.

    If we didn't remove the "foo" from the path, Django would look in
    /code/tenants/foo/static/foo/admin/css/base.css , which is wrong.

    Note: Keep in mind that this code won't run at all when behind uWSGI/NGINX/whatever
    web server you're using. Django won't even know where your static files are at!
    """
    def find_in_app(self, app, path):
        """
        Find a requested static file in an app's static locations.
        """
        path = os.path.sep.join(path.split(os.path.sep)[1:])
        return super().find_in_app(app, path)

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

    def find_location(self, root, path, prefix=None):
        """
        Find a requested static file in a location and return the found
        absolute path (or ``None`` if no match).
        """
        # This will remove the name of the tenant from the path. This will
        # allow is to correctly match the path when using Djang's built-in
        # server.
        # Note that this doesn't matter at all when running in production
        # mode as Django won't be handling the static files.
        path = os.path.sep.join(path.split(os.path.sep)[1:])
        return super().find_location(root, path, prefix)

    @property
    def locations(self):
        """
        Lazy retrieval of list of locations with static files based on current tenant schema.
        :return: The list of static file dirs that have been configured for this tenant.
        """
        if self._locations.get(connection.schema_name, None) is None:
            schema_locations = []
            for root in settings.MULTITENANT_STATICFILES_DIRS:
                root = utils.parse_tenant_config_path(root)

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
                filesystem_storage = TenantStaticFilesStorage(location=root)
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
