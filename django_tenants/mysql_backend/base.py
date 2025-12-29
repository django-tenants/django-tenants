import re
import warnings
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError
import django.db.utils
from django.db.backends.mysql.base import DatabaseWrapper as OriginalDatabaseWrapper
from django_tenants.utils import get_public_schema_name

def _check_schema_name(name):
    # MySQL db names must be < 64 chars. 
    # Valid chars: alphanumeric, _, $, (but mostly just use alphanumeric and _)
    if len(name) > 63:
        raise ValidationError("Schema name is too long (max 63 characters).")
    if not re.match(r'^[a-zA-Z0-9_$]+$', name):
        raise ValidationError("Invalid string used for the schema name.")

class DatabaseWrapper(OriginalDatabaseWrapper):
    def __init__(self, *args, **kwargs):
        self.tenant = None
        self.schema_name = None
        self.current_schema = None
        super().__init__(*args, **kwargs)
        
        # Initialize to public schema
        self.set_schema_to_public()

    def set_tenant(self, tenant, include_public=True):
        self.tenant = tenant
        self.schema_name = tenant.schema_name
        self.set_settings_schema(self.schema_name)
        
        # In MySQL, we switch databases, so "include_public" concept (search_path)
        # is implemented via Views in the tenant database, effectively handled by data layer.
        # Here we just mark that we need to switch.
        self.current_schema = None # Force switch on next cursor logic

    def set_schema(self, schema_name, include_public=True, tenant_type=None):
        self.set_tenant(FakeTenant(schema_name=schema_name, tenant_type=tenant_type), include_public)

    def set_schema_to_public(self):
        self.set_tenant(FakeTenant(schema_name=get_public_schema_name()))

    def set_settings_schema(self, schema_name):
        self.settings_dict['SCHEMA'] = schema_name

    def _cursor(self, name=None):
        cursor = super()._cursor(name)
        
        target_db = self.schema_name
        # If we are targeting the public schema, use the configured database name
        # This ensures we use the test database name (e.g. test_project) when running tests
        if target_db == get_public_schema_name():
            target_db = self.settings_dict['NAME']
        
        # Check if we need to switch database
        if target_db and target_db != self.current_schema:
            try:
                # Quote name to be safe
                cursor.execute(f"USE `{target_db}`")
                self.current_schema = target_db
            except Exception as e:
                # If DB doesn't exist yet (e.g. creating it), might fail. 
                # But typically we switch DB to run things inside it.
                # If it fails, we might be in a state where we just created the connection 
                # and the DB doesn't exist.
                # However, for 'create_tenant', we need to successfully connect first.
                # We'll allow invalid schema only if we are about to create it?
                # For now let it raise, catch specific cases if needed.
                raise e
                
        return cursor

class FakeTenant:
    def __init__(self, schema_name, tenant_type=None):
        self.schema_name = schema_name
        self.tenant_type = tenant_type

    def get_tenant_type(self):
        return self.tenant_type
