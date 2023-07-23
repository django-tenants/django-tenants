import re
import warnings
from django.conf import settings
from importlib import import_module

from django.utils.module_loading import import_string

from django_tenants.postgresql_backend.introspection import DatabaseSchemaIntrospection
from django_tenants.utils import get_public_schema_name, get_limit_set_calls
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ImproperlyConfigured, ValidationError
import django.db.utils

try:
     from django.db.backends.postgresql.psycopg_any import is_psycopg3
except ImportError:
    is_psycopg3 = False

if is_psycopg3:
    import psycopg
else:
    import psycopg2 as psycopg


DatabaseError = django.db.utils.DatabaseError
IntegrityError = psycopg.IntegrityError

ORIGINAL_BACKEND = getattr(settings, 'ORIGINAL_BACKEND', 'django.db.backends.postgresql')

original_backend = import_module(ORIGINAL_BACKEND + '.base')

EXTRA_SEARCH_PATHS = getattr(settings, 'PG_EXTRA_SEARCH_PATHS', [])

EXTRA_SET_TENANT_METHOD_PATH = getattr(settings, 'EXTRA_SET_TENANT_METHOD_PATH', None)
if EXTRA_SET_TENANT_METHOD_PATH:
    EXTRA_SET_TENANT_METHOD = import_string(EXTRA_SET_TENANT_METHOD_PATH)
else:
    EXTRA_SET_TENANT_METHOD = None

# Valid PostgreSQL schema name regex
# Criteria:
#  1. Cannot start with 'pg_'
#  2. Can be any valid character, if quoted
#  3. Must be between 1 and 63 characters long
#
# Reference:
# https://www.postgresql.org/docs/13/sql-createschema.html
PGSQL_VALID_SCHEMA_NAME = re.compile(r'^(?!pg_).{1,63}$', re.IGNORECASE)


def is_valid_schema_name(name):
    return PGSQL_VALID_SCHEMA_NAME.match(name)


def _check_schema_name(name):
    if not is_valid_schema_name(name):
        raise ValidationError("Invalid string used for the schema name.")


class DatabaseWrapper(original_backend.DatabaseWrapper):
    """
    Adds the capability to manipulate the search_path using set_tenant and set_schema_name
    """
    include_public_schema = True
    # Use a patched version of the DatabaseIntrospection that only returns the table list for the
    # currently selected schema.

    def __init__(self, *args, **kwargs):
        self.search_path_set_schemas = None
        self.tenant = None
        self.schema_name = None
        super().__init__(*args, **kwargs)

        # Use a patched version of the DatabaseIntrospection that only returns the table list for the
        # currently selected schema.
        self.introspection = DatabaseSchemaIntrospection(self)

        self.set_schema_to_public()

    def close(self):
        self.search_path_set_schemas = None
        super().close()

    def set_tenant(self, tenant, include_public=True):
        """
        Main API method to current database schema,
        but it does not actually modify the db connection.
        """
        self.tenant = tenant
        self.schema_name = tenant.schema_name
        self.include_public_schema = include_public
        self.set_settings_schema(self.schema_name)

        if EXTRA_SET_TENANT_METHOD:
            EXTRA_SET_TENANT_METHOD(self, tenant)

        self.search_path_set_schemas = None

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
        Here it happens. We hope every Django db operation using PostgreSQL
        must go through this to get the cursor handle. We change the path.
        """
        if name:
            # Only supported and required by Django 1.11 (server-side cursor)
            cursor = super()._cursor(name=name)
        else:
            cursor = super()._cursor()

        # optionally limit the number of executions - under load, the execution
        # of `set search_path` can be quite time consuming
        if (not get_limit_set_calls()) or not self.search_path_set_schemas:
            # Actual search_path modification for the cursor. Database will
            # search schemata from left to right when looking for the object
            # (table, index, sequence, etc.).
            if not self.schema_name:
                raise ImproperlyConfigured("Database schema not set. Did you forget "
                                           "to call set_schema() or set_tenant()?")

            search_paths = self._get_cursor_search_paths()

            if name or is_psycopg3:
                # Named cursor can only be used once, psycopg3 and Django 4 have recursion issue
                cursor_for_search_path = self.connection.cursor()
            else:
                # Reuse
                cursor_for_search_path = cursor

            # In the event that an error already happened in this transaction and we are going
            # to rollback we should just ignore database error when setting the search_path
            # if the next instruction is not a rollback it will just fail also, so
            # we do not have to worry that it's not the good one
            try:
                formatted_search_paths = ['\'{}\''.format(s) for s in search_paths]
                cursor_for_search_path.execute('SET search_path = {0}'.format(','.join(formatted_search_paths)))
            except (django.db.utils.DatabaseError, psycopg.InternalError):
                self.search_path_set_schemas = None
            else:
                self.search_path_set_schemas = search_paths
            if name or is_psycopg3:
                cursor_for_search_path.close()
        return cursor

    def _get_cursor_search_paths(self):
        _check_schema_name(self.schema_name)
        public_schema_name = get_public_schema_name()

        if self.schema_name == public_schema_name:
            search_paths = [public_schema_name]
        elif self.include_public_schema:
            search_paths = [self.schema_name, public_schema_name]
        else:
            search_paths = [self.schema_name]

        search_paths.extend(EXTRA_SEARCH_PATHS)

        return search_paths


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
