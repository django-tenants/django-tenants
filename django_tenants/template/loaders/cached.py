"""
Wrapper class that takes a list of template loaders as an argument and attempts
to load templates from them in order, caching the result, in a multi-tenant setting.
"""

from django.db import connection

from django.template.loaders.cached import Loader as BaseLoader

from django_tenants.postgresql_backend.base import FakeTenant


class Loader(BaseLoader):

    def cache_key(self, template_name, skip=None):
        key = super().cache_key(template_name, skip)

        if not connection.tenant or isinstance(connection.tenant, FakeTenant):
            return key

        return "-".join([connection.tenant.schema_name, key])
