import re
import warnings

from MySQLdb._exceptions import InternalError
from django.conf import settings
from importlib import import_module

from django.utils.module_loading import import_string

from django_tenants.mysql_backend.introspection import DatabaseSchemaIntrospection
from django_tenants.utils import get_public_schema_name, get_limit_set_calls
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ImproperlyConfigured, ValidationError
import django.db.utils

"""
This code is still using some postgres naming, this is because external code is referencing those names.
Additionally, mysql code is still using SCHEMA naming, though in reality it's using databases.
"""


DatabaseError = django.db.utils.DatabaseError

ORIGINAL_BACKEND = getattr(settings, 'ORIGINAL_BACKEND', 'django.db.backends.mysql')

original_backend = import_module(ORIGINAL_BACKEND + '.base')

EXTRA_SET_TENANT_METHOD_PATH = getattr(settings, 'EXTRA_SET_TENANT_METHOD_PATH', None)
if EXTRA_SET_TENANT_METHOD_PATH:
    EXTRA_SET_TENANT_METHOD = import_string(EXTRA_SET_TENANT_METHOD_PATH)
else:
    EXTRA_SET_TENANT_METHOD = None

PGSQL_VALID_SCHEMA_NAME = re.compile(r'^[A-Za-z0-9_]{1,64}$', re.IGNORECASE)



def _check_schema_name(name):
    if not DatabaseWrapper.is_valid_schema_name(name):
        raise ValidationError("Invalid string used for the schema name.")


class DatabaseWrapper(original_backend.DatabaseWrapper):
    def __init__(self, *args, **kwargs):
        self.tenant = None
        self.schema_name = None
        self.current_schema = None
        super().__init__(*args, **kwargs)

        # Use a patched version of the DatabaseIntrospection that only returns the table list for the
        # currently selected schema.
        self.introspection = DatabaseSchemaIntrospection(self)

        self.set_schema_to_public()

    @staticmethod
    def is_valid_schema_name(name):
        return PGSQL_VALID_SCHEMA_NAME.match(name)

    def close(self):
        self.current_schema = None
        super().close()

    def set_tenant(self, tenant, include_public=True):
        """
        Main API method to current database schema,
        but it does not actually modify the db connection.
        """
        self.tenant = tenant
        self.schema_name = tenant.schema_name
        self.set_settings_schema(self.schema_name)

        if EXTRA_SET_TENANT_METHOD:
            EXTRA_SET_TENANT_METHOD(self, tenant)

        self.current_schema = None

        # Content type can no longer be cached as public and tenant schemas
        # have different models. If someone wants to change this, the cache
        # needs to be separated between public and shared schemas. If this
        # cache isn't cleared, this can cause permission problems. For example,
        # on public, a particular model has id 14, but on the tenants it has
        # the id 15. if 14 is cached instead of 15, the permissions for the
        # wrong model will be fetched.
        ContentType.objects.clear_cache()

    def set_schema(self, schema_name, include_public=True, tenant_type=None):
        """
        Main API method to current database schema,
        but it does not actually modify the db connection.
        """
        self.set_tenant(FakeTenant(schema_name=schema_name,
                                   tenant_type=tenant_type), include_public)

    def set_schema_to_public(self):
        """
        Instructs to stay in the common 'public' schema.
        """
        self.set_tenant(FakeTenant(schema_name=get_public_schema_name()))

    def set_settings_schema(self, schema_name):
        self.settings_dict['SCHEMA'] = schema_name

    def get_schema(self):
        warnings.warn("connection.get_schema() is deprecated, use connection.schema_name instead.",
                      category=DeprecationWarning)
        return self.schema_name

    def get_tenant(self):
        warnings.warn("connection.get_tenant() is deprecated, use connection.tenant instead.",
                      category=DeprecationWarning)
        return self.tenant

    def _cursor(self, name=None):
        """
        Here it happens. We hope every Django db operation must go through this to get the cursor handle.
        """
        cursor = super()._cursor(name=name)

        if self.schema_name and self.schema_name != self.current_schema:
            try:
                # Quote name to be safe
                cursor.execute(f'USE `{self.schema_name}`')
                self.current_schema = self.schema_name
            except (django.db.utils.DatabaseError, InternalError):
                self.schema_name = None

        return cursor



class FakeTenant:
    """
    We can't import any db model in a backend (apparently?), so this class is used
    for wrapping schema names in a tenant-like structure.
    """
    def __init__(self, schema_name, tenant_type=None):
        self.schema_name = schema_name
        self.tenant_type = tenant_type

    def get_tenant_type(self):
        return self.tenant_type
