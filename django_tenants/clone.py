class CloneSchema(object):

    def __init__(self, cursor):
        self.cursor = cursor
        self.create_function()

    def clone(self, old_schema_name, new_schema_name):
        self.cursor.execute("select clone_schema('%s', '%s', TRUE);" % (old_schema_name,
                                                                        new_schema_name))

    def create_function(self):
        self.cursor.execute("""

            -- Function: clone_schema(text, text)

            -- DROP FUNCTION clone_schema(text, text);

            CREATE OR REPLACE FUNCTION clone_schema(
                source_schema text,
                dest_schema text,
                include_recs boolean)
              RETURNS void AS
            $BODY$

            --  This function will clone all sequences, tables, data, views & functions from any existing schema to a new one
            -- SAMPLE CALL:
            -- SELECT clone_schema('public', 'new_schema', TRUE);

            DECLARE
              src_oid          oid;
              tbl_oid          oid;
              func_oid         oid;
              object           text;
              buffer           text;
              srctbl           text;
              default_         text;
              column_          text;
              qry              text;
              dest_qry         text;
              v_def            text;
              seqval           bigint;
              sq_last_value    bigint;
              sq_max_value     bigint;
              sq_start_value   bigint;
              sq_increment_by  bigint;
              sq_min_value     bigint;
              sq_cache_value   bigint;
              sq_log_cnt       bigint;
              sq_is_called     boolean;
              sq_is_cycled     boolean;
              sq_cycled        char(10);

            BEGIN

            -- Check that source_schema exists
              SELECT oid INTO src_oid
                FROM pg_namespace
               WHERE nspname = quote_ident(source_schema);
              IF NOT FOUND
                THEN
                RAISE NOTICE 'source schema % does not exist!', source_schema;
                RETURN ;
              END IF;

              -- Check that dest_schema does not yet exist
              PERFORM nspname
                FROM pg_namespace
               WHERE nspname = quote_ident(dest_schema);
              IF FOUND
                THEN
                RAISE NOTICE 'dest schema % already exists!', dest_schema;
                RETURN ;
              END IF;

              EXECUTE 'CREATE SCHEMA ' || quote_ident(dest_schema) ;

              -- Create sequences
              -- TODO: Find a way to make this sequence's owner is the correct table.
              FOR object IN
                SELECT sequence_name::text
                  FROM information_schema.sequences
                 WHERE sequence_schema = quote_ident(source_schema)
              LOOP
                EXECUTE 'CREATE SEQUENCE ' || quote_ident(dest_schema) || '.' || quote_ident(object);
                srctbl := quote_ident(source_schema) || '.' || quote_ident(object);

                EXECUTE 'SELECT last_value, max_value, start_value, increment_by, min_value, cache_value, log_cnt, is_cycled, is_called
                          FROM ' || quote_ident(source_schema) || '.' || quote_ident(object) || ';'
                          INTO sq_last_value, sq_max_value, sq_start_value, sq_increment_by, sq_min_value, sq_cache_value, sq_log_cnt, sq_is_cycled, sq_is_called ;

                IF sq_is_cycled
                  THEN
                    sq_cycled := 'CYCLE';
                ELSE
                    sq_cycled := 'NO CYCLE';
                END IF;

                EXECUTE 'ALTER SEQUENCE '   || quote_ident(dest_schema) || '.' || quote_ident(object)
                        || ' INCREMENT BY ' || sq_increment_by
                        || ' MINVALUE '     || sq_min_value
                        || ' MAXVALUE '     || sq_max_value
                        || ' START WITH '   || sq_start_value
                        || ' RESTART '      || sq_min_value
                        || ' CACHE '        || sq_cache_value
                        || sq_cycled || ' ;' ;

                buffer := quote_ident(dest_schema) || '.' || quote_ident(object);
                IF include_recs
                    THEN
                        EXECUTE 'SELECT setval( ''' || buffer || ''', ' || sq_last_value || ', ' || sq_is_called || ');' ;
                ELSE
                        EXECUTE 'SELECT setval( ''' || buffer || ''', ' || sq_start_value || ', ' || sq_is_called || ');' ;
                END IF;

              END LOOP;

            -- Create tables
              FOR object IN
                SELECT TABLE_NAME::text
                  FROM information_schema.tables
                 WHERE table_schema = quote_ident(source_schema)
                   AND table_type = 'BASE TABLE'

              LOOP
                buffer := dest_schema || '.' || quote_ident(object);
                EXECUTE 'CREATE TABLE ' || buffer || ' (LIKE ' || quote_ident(source_schema) || '.' || quote_ident(object)
                    || ' INCLUDING ALL)';

                IF include_recs
                  THEN
                  -- Insert records from source table
                  EXECUTE 'INSERT INTO ' || buffer || ' SELECT * FROM ' || quote_ident(source_schema) || '.' || quote_ident(object) || ';';
                END IF;

                FOR column_, default_ IN
                  SELECT column_name::text,
                         REPLACE(column_default::text, source_schema, dest_schema)
                    FROM information_schema.COLUMNS
                   WHERE table_schema = dest_schema
                     AND TABLE_NAME = object
                     AND column_default LIKE 'nextval(%' || quote_ident(source_schema) || '%::regclass)'
                LOOP
                  EXECUTE 'ALTER TABLE ' || buffer || ' ALTER COLUMN ' || column_ || ' SET DEFAULT ' || default_;
                END LOOP;

              END LOOP;

            --  add FK constraint
              FOR qry IN
                SELECT 'ALTER TABLE ' || quote_ident(dest_schema) || '.' || quote_ident(rn.relname)
                                      || ' ADD CONSTRAINT ' || quote_ident(ct.conname) || ' ' || pg_get_constraintdef(ct.oid) || ';'
                  FROM pg_constraint ct
                  JOIN pg_class rn ON rn.oid = ct.conrelid
                 WHERE connamespace = src_oid
                   AND rn.relkind = 'r'
                   AND ct.contype = 'f'

                LOOP
                  EXECUTE qry;

                END LOOP;


            -- Create views
              FOR object IN
                SELECT table_name::text,
                       view_definition
                  FROM information_schema.views
                 WHERE table_schema = quote_ident(source_schema)

              LOOP
                buffer := dest_schema || '.' || quote_ident(object);
                SELECT view_definition INTO v_def
                  FROM information_schema.views
                 WHERE table_schema = quote_ident(source_schema)
                   AND table_name = quote_ident(object);

                EXECUTE 'CREATE OR REPLACE VIEW ' || buffer || ' AS ' || v_def || ';' ;

              END LOOP;

            -- Create functions
              FOR func_oid IN
                SELECT oid
                  FROM pg_proc
                 WHERE pronamespace = src_oid

              LOOP
                SELECT pg_get_functiondef(func_oid) INTO qry;
                SELECT replace(qry, source_schema, dest_schema) INTO dest_qry;
                EXECUTE dest_qry;

              END LOOP;

              RETURN;

            END;

            $BODY$
              LANGUAGE plpgsql VOLATILE
              COST 100;

            """)
