"""
Wrapper class that takes a list of template loaders as an argument and attempts
to load templates from them in order, caching the result, in a multi-tenant setting.
"""

from django.db import connection

from django.template.loaders.cached import Loader as BaseLoader


class Loader(BaseLoader):

    def cache_key(self, template_name, skip=None):
        key = super().cache_key(template_name, skip)

        # Every key is prefixed with the active schema -- including under a
        # FakeTenant (schema_context(), the public schema, management commands),
        # whose templates come from that schema's directories too. '/' cannot
        # appear in a schema name, so the schema name is everything before the
        # first '/' and two schemas can never produce the same key. (With '-',
        # tenant 'acme' + 'base-x.html' and tenant 'acme-base' + 'x.html'
        # shared a cache entry; with an unprefixed FakeTenant key, tenant
        # 'admin' + 'login.html' collided with 'admin/login.html'.)
        return "/".join([connection.schema_name, key])
