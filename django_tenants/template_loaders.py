"""
Adaptations of the cached and filesystem template loader working in a
multi-tenant setting
"""

import hashlib
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, SuspiciousFileOperation
from django.template.base import Template
from django.utils.encoding import force_bytes
from django.utils._os import safe_join
from django.db import connection
from django.template.loaders.base import Loader as BaseLoader
from django_tenants.postgresql_backend.base import FakeTenant
from django.template.exceptions import TemplateDoesNotExist


class CachedLoader(BaseLoader):
    is_usable = True

    def __init__(self, engine, loaders):
        self.template_cache = {}
        self.find_template_cache = {}
        self.loaders = engine.get_template_loaders(loaders)
        super(CachedLoader, self).__init__(engine)

    @staticmethod
    def cache_key(template_name, template_dirs):
        if connection.tenant and template_dirs:
            return '-'.join([str(connection.tenant.pk), template_name,
                             hashlib.sha1(force_bytes('|'.join(template_dirs))).hexdigest()])
        if template_dirs:
            # If template directories were specified, use a hash to differentiate
            return '-'.join([template_name, hashlib.sha1(force_bytes('|'.join(template_dirs))).hexdigest()])
        else:
            return template_name

    def find_template(self, name, dirs=None):
        """
        Helper method. Lookup the template :param name: in all the configured loaders
        """
        key = self.cache_key(name, dirs)
        try:
            result = self.find_template_cache[key]
        except KeyError:
            result = None
            for loader in self.loaders:
                try:
                    template, display_name = loader(name, dirs)
                except TemplateDoesNotExist:
                    pass
                else:
                    origin = self.engine.make_origin(display_name, loader, name, dirs)
                    result = template, origin
                    break
        self.find_template_cache[key] = result
        if result:
            return result
        else:
            self.template_cache[key] = TemplateDoesNotExist
            raise TemplateDoesNotExist(name)

    def load_template(self, template_name, template_dirs=None):
        key = self.cache_key(template_name, template_dirs)
        template_tuple = self.template_cache.get(key)
        # A cached previous failure:
        if template_tuple is TemplateDoesNotExist:
            raise TemplateDoesNotExist
        elif template_tuple is None:
            template, origin = self.find_template(template_name, template_dirs)
            if not hasattr(template, 'render'):
                try:
                    template = Template(template, origin, template_name, self.engine)
                except TemplateDoesNotExist:
                    # If compiling the template we found raises TemplateDoesNotExist,
                    # back off to returning the source and display name for the template
                    # we were asked to load. This allows for correct identification (later)
                    # of the actual template that does not exist.
                    self.template_cache[key] = (template, origin)
            self.template_cache[key] = (template, None)
        return self.template_cache[key]

    def reset(self):
        """
        Empty the template cache.
        """
        self.template_cache.clear()


class FilesystemLoader(BaseLoader):
    is_usable = True

    @staticmethod
    def get_template_sources(template_name, template_dirs=None):
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
                    yield safe_join(template_dir % connection.tenant.schema_name, template_name)
                else:
                    yield safe_join(template_dir, connection.tenant.schema_name, template_name)
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
