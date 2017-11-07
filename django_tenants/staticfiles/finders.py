# -*- coding: utf-8 -*-
import os
from django.contrib.staticfiles.finders import FileSystemFinder
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import connection
from collections import OrderedDict
from django.core.exceptions import ImproperlyConfigured
from django_tenants.utils import get_tenant_model


class TenantFileSystemFinder(FileSystemFinder):
    def __init__(self, app_names=None, *args, **kwargs):
        self.schema_name = None

        TenantModel = get_tenant_model()
        all_tenants = TenantModel.objects.values_list('schema_name', flat=True)
        # print "=========== all_tenants ============"
        # print all_tenants

        if connection.schema_name != "public":
            self.schema_name = connection.schema_name
        else:
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
                if CURRENT_SCHEMA_TO_SERVER_STATICFILES not in all_tenants:
                    raise ImproperlyConfigured(
                        "The value of CURRENT_SCHEMA_TO_SERVER_STATICFILES setting "
                        "doesnt correspond to a valid schema_name tentant")

            self.schema_name = CURRENT_SCHEMA_TO_SERVER_STATICFILES

        # print "--------- schema_name -----------"
        # print settings.CURRENT_SCHEMA_TO_SERVER_STATICFILES
        # print self.schema_name

        """
        if not hasattr(settings, "MULTITENANT_RELATIVE_STATIC_ROOT") or \
                not settings.MULTITENANT_RELATIVE_STATIC_ROOT:
            raise ImproperlyConfigured("You're using the TenantStaticFilesStorage "
                                       "without having set the MULTITENANT_RELATIVE_STATIC_ROOT "
                                       "setting to a filesystem path.")
        """

        self.config_by_schema()

    def config_by_schema(self):
        self.locations = []
        self.storages = OrderedDict()

        multitenant_relative_static_root = ""
        if hasattr(settings, "MULTITENANT_RELATIVE_STATIC_ROOT"):
            if '%s' in settings.MULTITENANT_RELATIVE_STATIC_ROOT:
                multitenant_relative_static_root = \
                    settings.MULTITENANT_RELATIVE_STATIC_ROOT % \
                    self.schema_name
            else:
                multitenant_relative_static_root = \
                    os.path.join(settings.MULTITENANT_RELATIVE_STATIC_ROOT,
                                 self.schema_name)
        else:
            multitenant_relative_static_root = self.schema_name

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
        for template_dir in multitenant_staticfiles_dirs:
            if '%s' in template_dir:
                tenant_paths.append(template_dir % self.schema_name)
            else:
                tenant_paths.append(os.path.join(template_dir, self.schema_name))

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

    def verify_need_change_schema(self):
        if self.schema_name != connection.schema_name and connection.schema_name != "public":
            print "TenantFileSystemFinder change config $$$$$$$$$$$$$$$$$$$$ ==============="
            print "self.schema_name: {0}".format(self.schema_name)
            print "connection.schema_name: {0}".format(connection.schema_name)
            self.schema_name = connection.schema_name
            self.config_by_schema()

    def find(self, path, all=False):
        """
        List all files in all locations and update initial configs if the schema is changed
        For now we need this override to work with command compress_schemas when it runs over all schemas
        """
        self.verify_need_change_schema()
        return super(TenantFileSystemFinder, self).find(path, all=all)

    def list(self, ignore_patterns):
        """
        List all files in all locations and update initial configs if the schema is changed
        For now we need this override to work with command collectstatic_schemas when it runs over all schemas
        """
        self.verify_need_change_schema()
        return super(TenantFileSystemFinder, self).list(ignore_patterns)
