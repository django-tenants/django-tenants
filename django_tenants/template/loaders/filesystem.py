"""
Wrapper for loading templates from the filesystem in a multi-tenant setting.
"""

from django.template import Origin

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, SuspiciousFileOperation
from django.utils._os import safe_join
from django.db import connection
from django.template.loaders.filesystem import Loader as BaseLoader


class Loader(BaseLoader):
    def get_dirs(self):
        try:
            self.dirs = settings.MULTITENANT_TEMPLATE_DIRS
            return self.dirs if self.dirs is not None else self.engine.dirs
        except AttributeError:
            raise ImproperlyConfigured(
                "To use %s.%s you must define the MULTITENANT_TEMPLATE_DIRS"
                % (__name__, Loader.__name__)
            )

    def get_template_sources(self, template_name):
        """
        Return an Origin object pointing to an absolute path in each directory
        in template_dirs. For security reasons, if a path doesn't lie inside
        one of the template_dirs it is excluded from the result set.
        """
        for template_dir in self.get_dirs():
            try:
                if "%s" in template_dir:
                    name = safe_join(
                        template_dir % connection.tenant.schema_name, template_name
                    )
                else:
                    name = safe_join(
                        template_dir, connection.tenant.schema_name, template_name
                    )
            except SuspiciousFileOperation:
                # The joined path was located outside of this template_dir
                # (it might be inside another one, so this isn't fatal).
                continue

            yield Origin(name=name, template_name=template_name, loader=self)
