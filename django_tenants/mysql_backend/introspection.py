from django.db.backends.mysql.introspection import DatabaseIntrospection


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
        self.cursor.execute('SELECT DATABASE()')
        self.original_search_path = self.cursor.fetchone()[0]
        self.cursor.execute(f'USE `{self.connection.schema_name}`')

    def __exit__(self, *args, **kwargs):
        self.cursor.execute(f'USE `{self.original_search_path}`')


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

    def get_storage_engine(self, cursor, table_name):
        with DatabaseSchemaIntrospectionSearchPathContext(cursor=cursor, connection=self.connection):
            return super().get_storage_engine(cursor, table_name)