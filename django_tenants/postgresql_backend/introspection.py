from django.db.backends.postgresql_psycopg2.introspection import DatabaseIntrospection
from django.db.backends.base.introspection import TableInfo, FieldInfo
from django.utils.encoding import force_text


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

    def get_constraints(self, cursor, table_name):
        """
        Retrieves any constraints or keys (unique, pk, fk, check, index) across one or more columns.
        """
        constraints = {}
        # Loop over the key table, collecting things as constraints
        # This will get PKs, FKs, and uniques, but not CHECK
        cursor.execute("""
            SELECT
                kc.constraint_name,
                kc.column_name,
                c.constraint_type,
                array(SELECT table_name::text || '.' || column_name::text
                      FROM information_schema.constraint_column_usage
                      WHERE constraint_name = kc.constraint_name
                      AND table_schema = kc.table_schema)
            FROM information_schema.key_column_usage AS kc
            JOIN information_schema.table_constraints AS c ON
                kc.table_schema = c.table_schema AND
                kc.table_name = c.table_name AND
                kc.constraint_name = c.constraint_name
            WHERE
                kc.table_schema = %s AND
                kc.table_name = %s
            ORDER BY kc.ordinal_position ASC
        """, [self.connection.schema_name, table_name])
        for constraint, column, kind, used_cols in cursor.fetchall():
            # If we're the first column, make the record
            if constraint not in constraints:
                if len(used_cols) == 0:
                    continue  # added as if the public schema hasn't got the field any more it errors
                constraints[constraint] = {
                    "columns": [],
                    "primary_key": kind.lower() == "primary key",
                    "unique": kind.lower() in ["primary key", "unique"],
                    "foreign_key": tuple(used_cols[0].split(".", 1)) if kind.lower() == "foreign key" else None,
                    "check": False,
                    "index": False,
                }
            # Record the details
            constraints[constraint]['columns'].append(column)
        # Now get CHECK constraint columns
        cursor.execute("""
            SELECT kc.constraint_name, kc.column_name
            FROM information_schema.constraint_column_usage AS kc
            JOIN information_schema.table_constraints AS c ON
                kc.table_schema = c.table_schema AND
                kc.table_name = c.table_name AND
                kc.constraint_name = c.constraint_name
            WHERE
                c.constraint_type = 'CHECK' AND
                kc.table_schema = %s AND
                kc.table_name = %s
        """, [self.connection.schema_name, table_name])
        for constraint, column in cursor.fetchall():
            # If we're the first column, make the record
            if constraint not in constraints:
                constraints[constraint] = {
                    "columns": [],
                    "primary_key": False,
                    "unique": False,
                    "foreign_key": None,
                    "check": True,
                    "index": False,
                }
            # Record the details
            constraints[constraint]['columns'].append(column)
        # Now get indexes
        cursor.execute("""
            SELECT
                c2.relname,
                ARRAY(
                    SELECT (SELECT attname FROM pg_catalog.pg_attribute WHERE attnum = i AND attrelid = c.oid)
                    FROM unnest(idx.indkey) i
                ),
                idx.indisunique,
                idx.indisprimary
            FROM pg_catalog.pg_class c
                 INNER JOIN pg_catalog.pg_index idx ON c.oid = idx.indrelid
                 INNER JOIN pg_catalog.pg_class c2 ON idx.indexrelid = c2.oid
                 LEFT JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relname = %s and n.nspname = %s
        """, [table_name, self.connection.schema_name])
        for index, columns, unique, primary in cursor.fetchall():
            if index not in constraints:
                constraints[index] = {
                    "columns": list(columns),
                    "primary_key": primary,
                    "unique": unique,
                    "foreign_key": None,
                    "check": False,
                    "index": True,
                }
        return constraints

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
