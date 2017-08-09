import django

if django.VERSION < (1, 11):
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

elif django.VERSION < (2, 0):
    from django.db.models.indexes import Index

    def get_constraints(self, cursor, table_name):
        """
        Retrieve any constraints or keys (unique, pk, fk, check, index) across
        one or more columns. Also retrieve the definition of expression-based
        indexes.
        """
        constraints = {}
        # Loop over the key table, collecting things as constraints. The column
        # array must return column names in the same order in which they were
        # created.
        # The subquery containing generate_series can be replaced with
        # "WITH ORDINALITY" when support for PostgreSQL 9.3 is dropped.
        cursor.execute("""
            SELECT
                c.conname,
                array(
                    SELECT attname
                    FROM (
                        SELECT unnest(c.conkey) AS colid,
                               generate_series(1, array_length(c.conkey, 1)) AS arridx
                    ) AS cols
                    JOIN pg_attribute AS ca ON cols.colid = ca.attnum
                    WHERE ca.attrelid = c.conrelid
                    ORDER BY cols.arridx
                ),
                c.contype,
                (SELECT fkc.relname || '.' || fka.attname
                FROM pg_attribute AS fka
                JOIN pg_class AS fkc ON fka.attrelid = fkc.oid
                WHERE fka.attrelid = c.confrelid AND fka.attnum = c.confkey[1]),
                cl.reloptions
            FROM pg_constraint AS c
            JOIN pg_class AS cl ON c.conrelid = cl.oid
            JOIN pg_namespace AS ns ON cl.relnamespace = ns.oid
            WHERE ns.nspname = %s AND cl.relname = %s
        """, ["public", table_name])
        for constraint, columns, kind, used_cols, options in cursor.fetchall():
            constraints[constraint] = {
                "columns": columns,
                "primary_key": kind == "p",
                "unique": kind in ["p", "u"],
                "foreign_key": tuple(used_cols.split(".", 1)) if kind == "f" else None,
                "check": kind == "c",
                "index": False,
                "definition": None,
                "options": options,
            }
        # Now get indexes
        # The row_number() function for ordering the index fields can be
        # replaced by WITH ORDINALITY in the unnest() functions when support
        # for PostgreSQL 9.3 is dropped.
        cursor.execute("""
            SELECT
                indexname, array_agg(attname ORDER BY rnum), indisunique, indisprimary,
                array_agg(ordering ORDER BY rnum), amname, exprdef, s2.attoptions
            FROM (
                SELECT
                    row_number() OVER () as rnum, c2.relname as indexname,
                    idx.*, attr.attname, am.amname,
                    CASE
                        WHEN idx.indexprs IS NOT NULL THEN
                            pg_get_indexdef(idx.indexrelid)
                    END AS exprdef,
                    CASE am.amname
                        WHEN 'btree' THEN
                            CASE (option & 1)
                                WHEN 1 THEN 'DESC' ELSE 'ASC'
                            END
                    END as ordering,
                    c2.reloptions as attoptions
                FROM (
                    SELECT
                        *, unnest(i.indkey) as key, unnest(i.indoption) as option
                    FROM pg_index i
                ) idx
                LEFT JOIN pg_class c ON idx.indrelid = c.oid
                LEFT JOIN pg_class c2 ON idx.indexrelid = c2.oid
                LEFT JOIN pg_am am ON c2.relam = am.oid
                LEFT JOIN pg_attribute attr ON attr.attrelid = c.oid AND attr.attnum = idx.key
                WHERE c.relname = %s
            ) s2
            GROUP BY indexname, indisunique, indisprimary, amname, exprdef, attoptions;
        """, [table_name])
        for index, columns, unique, primary, orders, type_, definition, options in cursor.fetchall():
            if index not in constraints:
                constraints[index] = {
                    "columns": columns if columns != [None] else [],
                    "orders": orders if orders != [None] else [],
                    "primary_key": primary,
                    "unique": unique,
                    "foreign_key": None,
                    "check": False,
                    "index": True,
                    "type": Index.suffix if type_ == 'btree' else type_,
                    "definition": definition,
                    "options": options,
                }
        return constraints
