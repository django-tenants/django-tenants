"""
Adaptations of the cached and filesystem template loader working in a
multi-tenant setting
"""

import hashlib
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.template.base import TemplateDoesNotExist
from django.template.loader import (BaseLoader, get_template_from_string,
                                    find_template_loader, make_origin)
from django.utils.encoding import force_bytes
from django.utils._os import safe_join
from django.db import connection


class CachedLoader(BaseLoader):
    is_usable = True

    def __init__(self, loaders):
        self.template_cache = {}
        self._loaders = loaders
        self._cached_loaders = []

    @property
    def loaders(self):
        # Resolve loaders on demand to avoid circular imports
        if not self._cached_loaders:
            # Set self._cached_loaders atomically. Otherwise, another thread
            # could see an incomplete list. See #17303.
            cached_loaders = []
            for loader in self._loaders:
                cached_loaders.append(find_template_loader(loader))
            self._cached_loaders = cached_loaders
        return self._cached_loaders

    def find_template(self, name, dirs=None):
        for loader in self.loaders:
            try:
                template, display_name = loader(name, dirs)
                return template, make_origin(display_name, loader, name, dirs)
            except TemplateDoesNotExist:
                pass
        raise TemplateDoesNotExist(name)

    def load_template(self, template_name, template_dirs=None):
        if connection.tenant:
            key = '-'.join([str(connection.tenant.pk), template_name])
        else:
            key = template_name
        if template_dirs:
            # If template directories were specified, use a hash to
            # differentiate
            if connection.tenant:
                key = '-'.join([str(connection.tenant.pk), template_name,
                                hashlib.sha1(force_bytes('|'.join(template_dirs))).hexdigest()])
            else:
                key = '-'.join([template_name, hashlib.sha1(force_bytes('|'.join(template_dirs))).hexdigest()])

        if key not in self.template_cache:
            template, origin = self.find_template(template_name, template_dirs)
            if not hasattr(template, 'render'):
                try:
                    template = get_template_from_string(template, origin, template_name)
                except TemplateDoesNotExist:
                    # If compiling the template we found raises TemplateDoesNotExist,
                    # back off to returning the source and display name for the template
                    # we were asked to load. This allows for correct identification (later)
                    # of the actual template that does not exist.
                    return template, origin
            self.template_cache[key] = template
        return self.template_cache[key], None

    def reset(self):
        "Empty the template cache."
        self.template_cache.clear()


class FilesystemLoader(BaseLoader):
    is_usable = True

    def get_template_sources(self, template_name, template_dirs=None):
        """
        Returns the absolute paths to "template_name", when appended to each
        directory in "template_dirs". Any paths that don't lie inside one of the
        template dirs are excluded from the result set, for security reasons.
        """
        if not connection.tenant:
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
                    yield safe_join(template_dir % connection.tenant.domain_url, template_name)
                else:
                    yield safe_join(template_dir, connection.tenant.domain_url, template_name)
            except UnicodeDecodeError:
                # The template dir name was a bytestring that wasn't valid UTF-8.
                raise
            except ValueError:
                # The joined path was located outside of this particular
                # template_dir (it might be inside another one, so this isn't
                # fatal).
                pass

    def load_template_source(self, template_name, template_dirs=None):
        tried = []
        for filepath in self.get_template_sources(template_name, template_dirs):
            try:
                with open(filepath, 'rb') as fp:
                    return (fp.read().decode(settings.FILE_CHARSET), filepath)
            except IOError:
                tried.append(filepath)
        if tried:
            error_msg = "Tried %s" % tried
        else:
            error_msg = "Your TEMPLATE_DIRS setting is empty. Change it to point to at least one template directory."
        raise TemplateDoesNotExist(error_msg)
    load_template_source.is_usable = True
