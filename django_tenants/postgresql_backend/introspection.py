# Import the backend's base module before its introspection module. On Django 6.1
# `django.db.backends.postgresql.introspection` imports `psycopg_version` from
# `...postgresql.base`, which in turn imports `...postgresql.introspection` -- so
# importing introspection first leaves base half-initialised and the cycle raises
# ImportError. Django itself never hits this because base is always imported first.
import django.db.backends.postgresql.base  # noqa: F401
from django.db.backends.postgresql.introspection import DatabaseIntrospection

from django_tenants.utils import quote_schema_name


class DatabaseSchemaIntrospectionSearchPathContext:
    """
    This context manager restores the original search path of the cursor
    once the method of the introspection class has been called.
    """
    def __init__(self, cursor, connection):
        self.cursor = cursor
        self.connection = connection
        self.original_search_path = None

    def __enter__(self):
        # Keep the setting exactly as PostgreSQL reports it: PostgreSQL quotes
        # any identifier in it that needs quoting, so it can be SET back as is.
        self.cursor.execute('SHOW search_path')
        self.original_search_path = self.cursor.fetchone()[0]
        self.cursor.execute(f'SET search_path = {quote_schema_name(self.connection.schema_name)}')

    def __exit__(self, *args, **kwargs):
        self.cursor.execute(f'SET search_path = {self.original_search_path}')


class DatabaseSchemaIntrospection(DatabaseIntrospection):
    """
    database schema introspection class
    """

    def get_table_list(self, cursor):
        with DatabaseSchemaIntrospectionSearchPathContext(cursor=cursor, connection=self.connection):
            return super().get_table_list(cursor)

    def get_table_description(self, cursor, table_name):
        with DatabaseSchemaIntrospectionSearchPathContext(cursor=cursor, connection=self.connection):
            return super().get_table_description(cursor, table_name)

    def get_sequences(self, cursor, table_name, table_fields=()):
        with DatabaseSchemaIntrospectionSearchPathContext(cursor=cursor, connection=self.connection):
            return super().get_sequences(cursor, table_name, table_fields)

    def get_key_columns(self, cursor, table_name):
        with DatabaseSchemaIntrospectionSearchPathContext(cursor=cursor, connection=self.connection):
            return super().get_key_columns(cursor, table_name)

    def get_constraints(self, cursor, table_name):
        with DatabaseSchemaIntrospectionSearchPathContext(cursor=cursor, connection=self.connection):
            return super().get_constraints(cursor, table_name)
