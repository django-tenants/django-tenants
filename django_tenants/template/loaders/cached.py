"""
Wrapper class that takes a list of template loaders as an argument and attempts
to load templates from them in order, caching the result, in a multi-tenant setting.
"""

from django.db import connection

from django.template.loaders.cached import Loader as BaseLoader


class Loader(BaseLoader):

    def cache_key(self, template_name, skip=None):
        """
        Generate a cache key for the template name, dirs, and skip.

        If skip is provided, only origins that match template_name are included
        in the cache key. This ensures each template is only parsed and cached
        once if contained in different extend chains like:

            x -> a -> a
            y -> a -> a
            z -> a -> a
        """
        dirs_prefix = ''
        skip_prefix = ''

        if skip:
            matching = [origin.name for origin in skip if origin.template_name == template_name]

            if matching:
                skip_prefix = self.generate_hash(matching)

        if connection.tenant:
            dirs_prefix = connection.tenant.pk

        return '-'.join(s for s in (str(template_name), skip_prefix, dirs_prefix) if s)
