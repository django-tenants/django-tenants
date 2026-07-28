import warnings
from importlib import import_module

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.utils.module_loading import import_string
import django.db.utils

from django_tenants.utils import get_public_schema_name, get_limit_set_calls, FakeTenant

# Valid MySQL database (schema) name.
# Criteria:
#  1. Cannot be empty
#  2. Cannot exceed 64 characters
#  3. Cannot contain '/', '\', '.', or a backtick (the identifier-quote
#     character) — disallowed here to avoid needing to escape it when
#     building `USE `<name>`` statements
#  4. Cannot have a trailing space
#
# Reference: https://dev.mysql.com/doc/refman/8.0/en/identifiers.html
DISALLOWED_CHARACTERS = ('/', '\\', '.', '`')


def is_valid_schema_name(name):
    if not name or len(name) > 64:
        return False
    if name != name.rstrip():
        return False
    return not any(char in name for char in DISALLOWED_CHARACTERS)


def _check_schema_name(name):
    if not is_valid_schema_name(name):
        raise ValidationError("Invalid string used for the schema name.")


ORIGINAL_BACKEND = getattr(settings, 'ORIGINAL_BACKEND', 'django.db.backends.mysql')
original_backend = import_module(ORIGINAL_BACKEND + '.base')

EXTRA_SET_TENANT_METHOD_PATH = getattr(settings, 'EXTRA_SET_TENANT_METHOD_PATH', None)
if EXTRA_SET_TENANT_METHOD_PATH:
    EXTRA_SET_TENANT_METHOD = import_string(EXTRA_SET_TENANT_METHOD_PATH)
else:
    EXTRA_SET_TENANT_METHOD = None


class DatabaseWrapper(original_backend.DatabaseWrapper):
    """
    Adds the capability to switch the active MySQL database using
    set_tenant()/set_schema(), mirroring the Postgres backend's
    search_path-based tenant switching. MySQL has no concept of a search
    path spanning databases, so switching means literally changing which
    database this connection currently has selected, via `USE`.
    """
    include_public_schema = True

    def __init__(self, *args, **kwargs):
        self.active_schema_name = None
        self.tenant = None
        self.schema_name = None
        super().__init__(*args, **kwargs)

        self.set_schema_to_public()

    def close(self):
        self.active_schema_name = None
        super().close()

    def set_tenant(self, tenant, include_public=True):
        """
        Main API method to set the current database schema, but it does
        not actually modify the db connection.
        """
        self.tenant = tenant
        self.schema_name = tenant.schema_name
        self.include_public_schema = include_public
        self.set_settings_schema(self.schema_name)

        if EXTRA_SET_TENANT_METHOD:
            EXTRA_SET_TENANT_METHOD(self, tenant)

        self.active_schema_name = None

        from django.contrib.contenttypes.models import ContentType
        ContentType.objects.clear_cache()

    def set_schema(self, schema_name, include_public=True, tenant_type=None):
        """
        Main API method to set the current database schema, but it does
        not actually modify the db connection.
        """
        self.set_tenant(FakeTenant(schema_name=schema_name, tenant_type=tenant_type), include_public)

    def set_schema_to_public(self):
        """
        Instructs to stay in the common 'public' database.
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
        Every MySQL db operation must go through this to get the cursor
        handle. We switch the active database here.
        """
        if name:
            cursor = super()._cursor(name=name)
        else:
            cursor = super()._cursor()

        if (not get_limit_set_calls()) or self.active_schema_name != self.schema_name:
            if not self.schema_name:
                raise ImproperlyConfigured("Database schema not set. Did you forget "
                                           "to call set_schema() or set_tenant()?")

            _check_schema_name(self.schema_name)

            try:
                cursor.execute('USE `{0}`'.format(self.schema_name))
            except django.db.utils.DatabaseError:
                self.active_schema_name = None
            else:
                self.active_schema_name = self.schema_name

        return cursor
