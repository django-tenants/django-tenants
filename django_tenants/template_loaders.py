"""
Adaptations of the cached and filesystem template loader working in a
multi-tenant setting
"""

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, SuspiciousFileOperation
from django.utils._os import safe_join
from django.db import connection
from django.template.loaders.base import Loader as BaseLoader
from django.template.loaders.cached import Loader as CachedLoaderOriginal
from django_tenants.postgresql_backend.base import FakeTenant

import django
if django.VERSION < (1, 9, 0):
    from django.template.base import TemplateDoesNotExist
else:
    from django.template.exceptions import TemplateDoesNotExist


class CachedLoader(CachedLoaderOriginal):
    def cache_key(self, template_name, template_dirs, skip=None):
        key = super(CachedLoader, self).cache_key(template_name, template_dirs, skip)
        # print "template key: {0}-{1}".format(str(connection.tenant.pk), key)
        return "{0}-{1}".format(str(connection.tenant.pk), key)


class FilesystemLoader(BaseLoader):
    is_usable = True

    def get_tenant_dir_name(self):
        return connection.schema_name

    def get_template_sources(self, template_name, template_dirs=None):
        """
        Returns the absolute paths to "template_name", when appended to each
        directory in "template_dirs". Any paths that don't lie inside one of the
        template dirs are excluded from the result set, for security reasons.
        """
        if not connection.tenant or isinstance(connection.tenant, FakeTenant):
            return
        if not template_dirs:
            try:
                template_dirs = settings.MULTITENANT_TEMPLATE_DIRS
            except AttributeError:
                raise ImproperlyConfigured('To use %s.%s you must define the MULTITENANT_TEMPLATE_DIRS' %
                                           (__name__, FilesystemLoader.__name__))

        for template_dir in template_dirs:
            try:
                if '%s' in template_dir:
                    yield safe_join(template_dir % self.get_tenant_dir_name(), template_name)
                else:
                    yield safe_join(template_dir, self.get_tenant_dir_name(), template_name)
            except UnicodeDecodeError:
                # The template dir name was a bytestring that wasn't valid UTF-8.
                raise
            except (SuspiciousFileOperation, ValueError):
                # The joined path was located outside of this particular
                # template_dir (it might be inside another one, so this isn't
                # fatal).
                pass

    def load_template_source(self, template_name, template_dirs=None):
        tried = []
        for filepath in self.get_template_sources(template_name, template_dirs):
            try:
                with open(filepath, 'rb') as fp:
                    return fp.read().decode(settings.FILE_CHARSET), filepath
            except IOError:
                tried.append(filepath)
        if tried:
            error_msg = "Tried %s" % tried
        else:
            error_msg = "Your TEMPLATE_DIRS setting is empty. Change it to point to at least one template directory."
        raise TemplateDoesNotExist(error_msg)
    load_template_source.is_usable = True
