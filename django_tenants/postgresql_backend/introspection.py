from django.db.backends.postgresql_psycopg2.introspection import DatabaseIntrospection
from django.db.backends.base.introspection import TableInfo


class DatabaseSchemaIntrospection(DatabaseIntrospection):
    def get_table_list(self, cursor):
        """
        Returns a list of table names in the current database and schema.
        """

        cursor.execute("""
            SELECT c.relname, c.relkind
            FROM pg_catalog.pg_class c
            LEFT JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relkind IN ('r', 'v', '')
                AND n.nspname = '%s'
                AND pg_catalog.pg_table_is_visible(c.oid)""" % self.connection.schema_name)

        return [TableInfo(row[0], {'r': 't', 'v': 'v'}.get(row[1]))
                for row in cursor.fetchall()
                if row[0] not in self.ignored_tables]
