from django.db.backends.postgresql.introspection import DatabaseIntrospection
from django.db.backends.base.introspection import TableInfo, FieldInfo
from django.utils.encoding import force_text

from . import _constraints


class DatabaseSchemaIntrospection(DatabaseIntrospection):
    """
    database schema introspection class
    """
    _get_indexes_query = """
        SELECT attr.attname, idx.indkey, idx.indisunique, idx.indisprimary
        FROM pg_catalog.pg_class c,
            INNER JOIN pg_catalog.pg_index idx ON c.oid = idx.indrelid
            INNER JOIN pg_catalog.pg_class c2 ON idx.indexrelid = c2.oid
            INNER JOIN pg_catalog.pg_attribute attr ON attr.attrelid = c.oid and attr.attnum = idx.indkey[0]
            INNER JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relname = %s AND n.nspname = %s
    """

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

    def get_table_description(self, cursor, table_name):
        "Returns a description of the table, with the DB-API cursor.description interface."
        # As cursor.description does not return reliably the nullable property,
        # we have to query the information_schema (#7783)
        cursor.execute("""
            SELECT column_name, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = %s and table_name = %s""", [self.connection.schema_name, table_name])
        field_map = {line[0]: line[1:] for line in cursor.fetchall()}
        cursor.execute("SELECT * FROM %s LIMIT 1" % self.connection.ops.quote_name(table_name))
        return [FieldInfo(*((force_text(line[0]),) + line[1:6] +
                            (field_map[force_text(line[0])][0] == 'YES', field_map[force_text(line[0])][1])))
                for line in cursor.description]

    def get_indexes(self, cursor, table_name):
        # This query retrieves each index on the given table, including the
        # first associated field name
        cursor.execute(self._get_indexes_query, [table_name, self.connection.schema_name])
        indexes = {}
        for row in cursor.fetchall():
            # row[1] (idx.indkey) is stored in the DB as an array. It comes out as
            # a string of space-separated integers. This designates the field
            # indexes (1-based) of the fields that have indexes on the table.
            # Here, we skip any indexes across multiple fields.
            if ' ' in row[1]:
                continue
            if row[0] not in indexes:
                indexes[row[0]] = {'primary_key': False, 'unique': False}
            # It's possible to have the unique and PK constraints in separate indexes.
            if row[3]:
                indexes[row[0]]['primary_key'] = True
            if row[2]:
                indexes[row[0]]['unique'] = True
        return indexes

    def get_relations(self, cursor, table_name):
        """
        Returns a dictionary of {field_name: (field_name_other_table, other_table)}
        representing all relationships to the given table.
        """
        cursor.execute("""
            SELECT c2.relname, a1.attname, a2.attname
            FROM pg_constraint con
            LEFT JOIN pg_class c1 ON con.conrelid = c1.oid
            LEFT JOIN pg_namespace n ON n.oid = c1.relnamespace
            LEFT JOIN pg_class c2 ON con.confrelid = c2.oid
            LEFT JOIN pg_attribute a1 ON c1.oid = a1.attrelid AND a1.attnum = con.conkey[1]
            LEFT JOIN pg_attribute a2 ON c2.oid = a2.attrelid AND a2.attnum = con.confkey[1]
            WHERE c1.relname = %s and n.nspname = %s
                AND con.contype = 'f'""", [table_name, self.connection.schema_name])
        relations = {}
        for row in cursor.fetchall():
            relations[row[1]] = (row[2], row[0])
        return relations

    get_constraints = _constraints.get_constraints

    def get_key_columns(self, cursor, table_name):
        key_columns = []
        cursor.execute("""
            SELECT kcu.column_name, ccu.table_name AS referenced_table, ccu.column_name AS referenced_column
            FROM information_schema.constraint_column_usage ccu
            LEFT JOIN information_schema.key_column_usage kcu
                ON ccu.constraint_catalog = kcu.constraint_catalog
                    AND ccu.constraint_schema = kcu.constraint_schema
                    AND ccu.constraint_name = kcu.constraint_name
            LEFT JOIN information_schema.table_constraints tc
                ON ccu.constraint_catalog = tc.constraint_catalog
                    AND ccu.constraint_schema = tc.constraint_schema
                    AND ccu.constraint_name = tc.constraint_name
            WHERE kcu.table_name = %s AND tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = %s
        """, [table_name, self.connection.schema_name])
        key_columns.extend(cursor.fetchall())
        return key_columns
