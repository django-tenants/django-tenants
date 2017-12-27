# -*- coding: utf-8 -*-
import os
from django.contrib.staticfiles.finders import FileSystemFinder
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import connection
from collections import OrderedDict
from django.core.exceptions import ImproperlyConfigured
from django_tenants.utils import get_tenant_model, get_public_schema_name


class TenantFileSystemFinder(FileSystemFinder):
    def __init__(self, app_names=None, *args, **kwargs):
        self.current_tenant_dir_name = None

        print "TenantFileSystemFinder"

        if connection.schema_name != get_public_schema_name():
            self.set_tenant_dir_name()
        else:
            # Below the explanation, why to use set CURRENT_SCHEMA_TO_SERVER_STATICFILES.
            # To work locally in your development environment unfortunately it is
            # necessary to set the variable CURRENT_SCHEMA_TO_SERVER_STATICFILES
            # to the name of the current schema you are working on, because after
            # much searching it is not possible to automatically set the
            # current schema value because when Django is serving static files
            # it does not pass through the TenantMiddleware middleware that is
            # responsible for lets the current tenant available through
            # from django.db import connection; connection.schema_name.
            # Also I tried to use request.path but request is also not available
            # within FileSystemFinder, so we have to do as below. This is
            # necessary only to server static files locally.

            # IMPORTANT: For all the other things like collectstatic files,
            # medias files, the variable CURRENT_SCHEMA_TO_SERVER_STATICFILES
            # it's not necessary, because the schema name is automatically found
            # for these actions.

            try:
                CURRENT_SCHEMA_TO_SERVER_STATICFILES = \
                    settings.CURRENT_SCHEMA_TO_SERVER_STATICFILES
            except AttributeError:
                raise ImproperlyConfigured('To use %s.%s you must '
                                           'define the CURRENT_SCHEMA_TO_SERVER_STATICFILES '
                                           'in your settings' %
                                           (__name__, TenantFileSystemFinder.__name__))

            if not CURRENT_SCHEMA_TO_SERVER_STATICFILES:
                raise ImproperlyConfigured(
                    "Your CURRENT_SCHEMA_TO_SERVER_STATICFILES setting can't be empty; "
                    "it must have the value of the schema_name in which you are "
                    "currently working on")
            else:
                all_tenants = get_tenant_model().objects.values_list('schema_name', flat=True)
                # print "=========== all_tenants ============"
                # print all_tenants
                if CURRENT_SCHEMA_TO_SERVER_STATICFILES not in all_tenants:
                    raise ImproperlyConfigured(
                        "The value of CURRENT_SCHEMA_TO_SERVER_STATICFILES setting "
                        "doesnt correspond to a valid schema_name tentant")

            self.current_tenant_dir_name = CURRENT_SCHEMA_TO_SERVER_STATICFILES

        # print "--------- schema_name -----------"
        # print settings.CURRENT_SCHEMA_TO_SERVER_STATICFILES
        # print self.current_tenant_dir_name

        """
        if not hasattr(settings, "MULTITENANT_RELATIVE_STATIC_ROOT") or \
                not settings.MULTITENANT_RELATIVE_STATIC_ROOT:
            raise ImproperlyConfigured("You're using the TenantStaticFilesStorage "
                                       "without having set the MULTITENANT_RELATIVE_STATIC_ROOT "
                                       "setting to a filesystem path.")
        """

        self.config_by_tenant_dir()

    def get_tenant_dir_name(self):
        return connection.schema_name

    def set_tenant_dir_name(self):
        self.current_tenant_dir_name = self.get_tenant_dir_name()

    def config_by_tenant_dir(self):
        self.locations = []
        self.storages = OrderedDict()

        multitenant_relative_static_root = ""
        if hasattr(settings, "MULTITENANT_RELATIVE_STATIC_ROOT"):
            if '%s' in settings.MULTITENANT_RELATIVE_STATIC_ROOT:
                multitenant_relative_static_root = \
                    settings.MULTITENANT_RELATIVE_STATIC_ROOT % \
                    self.current_tenant_dir_name
            else:
                multitenant_relative_static_root = \
                    os.path.join(settings.MULTITENANT_RELATIVE_STATIC_ROOT,
                                 self.current_tenant_dir_name)
        else:
            multitenant_relative_static_root = self.current_tenant_dir_name

        multitenant_static_root = os.path.join(settings.STATIC_ROOT,
                                               multitenant_relative_static_root)

        # print "multitenant_relative_static_root"
        # print multitenant_relative_static_root
        # print "multitenant_static_root"
        # print multitenant_static_root

        try:
            multitenant_staticfiles_dirs = settings.MULTITENANT_STATICFILES_DIRS
        except AttributeError:
            raise ImproperlyConfigured('To use %s.%s you must '
                                       'define the MULTITENANT_STATICFILES_DIRS '
                                       'in your settings' %
                                       (__name__, TenantFileSystemFinder.__name__))

        if not isinstance(multitenant_staticfiles_dirs, (list, tuple)):
            raise ImproperlyConfigured(
                "Your MULTITENANT_STATICFILES_DIRS setting is not a tuple or list; "
                "perhaps you forgot a trailing comma?")

        tenant_paths = []
        for staticfile_dir in multitenant_staticfiles_dirs:
            if '%s' in staticfile_dir:
                tenant_paths.append(staticfile_dir % self.current_tenant_dir_name)
            else:
                tenant_paths.append(os.path.join(staticfile_dir, self.current_tenant_dir_name))

        dirs = tenant_paths

        # print "----------- dirs -------------"
        # print dirs

        for root in dirs:
            if isinstance(root, (list, tuple)):
                prefix, root = root
            else:
                prefix = ''

            # print "=========================================="
            # print os.path.abspath(multitenant_static_root)
            # print os.path.abspath(root)

            if os.path.abspath(multitenant_static_root) == os.path.abspath(root):
                raise ImproperlyConfigured(
                    "The MULTITENANT_STATICFILES_DIRS setting should "
                    "not contain the (STATIC_ROOT + MULTITENANT_RELATIVE_STATIC_ROOT) path")
            if (prefix, root) not in self.locations:
                self.locations.append((prefix, root))

        for prefix, root in self.locations:
            filesystem_storage = FileSystemStorage(location=root)
            filesystem_storage.prefix = prefix
            self.storages[root] = filesystem_storage

    def verify_need_change_tenant_dir(self):
        if connection.schema_name != get_public_schema_name() and \
                self.current_tenant_dir_name != self.get_tenant_dir_name():
            print "TenantFileSystemFinder change config $$$$$$$$$$$$$$$$$$$$ ==============="
            print "self.current_tenant_dir_name: {0}".format(self.current_tenant_dir_name)
            print "tenant_dir_name: {0}".format(self.get_tenant_dir_name())

            # print "TenantSiteFileSystemFinder change config $$$$$$$$$$$$$$$$$$$$ ==============="
            # print "self.current_tenant_dir_name: {}".format(self.current_tenant_dir_name)
            # print "self.site_dir: {}".format(self.site_dir)
            # print "connection.schema_name: {}".format(connection.schema_name)
            # print "bucket_static_name: {}".format(self.get_bucket_static_name())
            self.set_tenant_dir_name()
            self.config_by_tenant_dir()

    def find(self, path, all=False):
        """
        List all files in all locations and update initial configs if the schema is changed
        For now we need this override to work with command compress_schemas when it runs over all schemas
        """
        self.verify_need_change_tenant_dir()
        return super(TenantFileSystemFinder, self).find(path, all=all)

    def list(self, ignore_patterns):
        """
        List all files in all locations and update initial configs if the schema is changed
        For now we need this override to work with command collectstatic_schemas when it runs over all schemas
        """
        self.verify_need_change_tenant_dir()
        return super(TenantFileSystemFinder, self).list(ignore_patterns)
