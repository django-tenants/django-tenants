# Import the backend's base module before its introspection module. On Django 6.1
# `django.db.backends.postgresql.introspection` imports `psycopg_version` from
# `...postgresql.base`, which in turn imports `...postgresql.introspection` -- so
# importing introspection first leaves base half-initialised and the cycle raises
# ImportError. Django itself never hits this because base is always imported first.
import django.db.backends.postgresql.base  # noqa: F401
from django.db.backends.postgresql.introspection import DatabaseIntrospection


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
        self.cursor.execute('SHOW search_path')
        self.original_search_path = [
            search_path.strip().replace('"', '')
            for search_path in self.cursor.fetchone()[0].split(',')
        ]
        self.cursor.execute(f"SET search_path = '{self.connection.schema_name}'")

    def __exit__(self, *args, **kwargs):
        formatted_search_paths = ', '.join(
            f"'{search_path}'"
            for search_path in self.original_search_path
        )
        self.cursor.execute(f'SET search_path = {formatted_search_paths}')


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
