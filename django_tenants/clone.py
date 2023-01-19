from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.db.utils import ProgrammingError

from django_tenants.utils import schema_exists

CLONE_SCHEMA_FUNCTION = r"""
-- https://github.com/denishpatel/pg-clone-schema/ rev 0d3b522
-- https://github.com/tomturner/django-tenants/issues/322

-- Function: clone_schema(text, text, boolean, boolean)

-- DROP FUNCTION clone_schema(text, text, boolean, boolean);

CREATE OR REPLACE FUNCTION public.clone_schema(
    source_schema text,
    dest_schema text,
    include_recs boolean,
    ddl_only     boolean)
  RETURNS void AS
$BODY$

--  This function will clone all sequences, tables, data, views & functions from any existing schema to a new one
-- SAMPLE CALL:
-- SELECT clone_schema('public', 'new_schema', True, False);

DECLARE
  src_oid          oid;
  tbl_oid          oid;
  func_oid         oid;
  object           text;
  buffer           text;
  buffer2          text;
  srctbl           text;
  default_         text;
  column_          text;
  qry              text;
  ix_old_name      text;
  ix_new_name      text;
  dest_qry         text;
  v_def            text;
  src_path_old     text;
  aclstr           text;
  grantor          text;
  grantee          text;
  privs            text;
  records_count    bigint;
  seqval           bigint;
  sq_last_value    bigint;
  sq_max_value     bigint;
  sq_start_value   bigint;
  sq_increment_by  bigint;
  sq_min_value     bigint;
  sq_cache_value   bigint;
  sq_is_called     boolean;
  sq_is_cycled     boolean;
  sq_data_type     text;
  sq_cycled        char(10);
  arec             RECORD;
  cnt              integer;
  cnt2             integer;
  seq_cnt          integer;
  pos              integer;
  action           text := 'N/A';
  v_ret            text;
  v_diag1          text;
  v_diag2          text;
  v_diag3          text;
  v_diag4          text;
  v_diag5          text;
  v_diag6          text;

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
  IF ddl_only and include_recs THEN
    RAISE WARNING 'You cannot specify to clone data and generate ddl at the same time.';
    RETURN ;
  END IF;

  -- Set the search_path to source schema. Before exiting set it back to what it was before.
  SELECT setting INTO src_path_old FROM pg_settings WHERE name='search_path';
  EXECUTE 'SET search_path = ' || quote_ident(source_schema) ;
  -- RAISE NOTICE 'Using source search_path=%', buffer;

  -- Validate required types exist.  If not, create them.
  select a.objtypecnt, b.permtypecnt INTO cnt, cnt2 FROM
  (SELECT count(*) as objtypecnt FROM pg_catalog.pg_type t LEFT JOIN pg_catalog.pg_namespace n ON n.oid = t.typnamespace
  WHERE (t.typrelid = 0 OR (SELECT c.relkind = 'c' FROM pg_catalog.pg_class c WHERE c.oid = t.typrelid))
  AND NOT EXISTS(SELECT 1 FROM pg_catalog.pg_type el WHERE el.oid = t.typelem AND el.typarray = t.oid)
  AND n.nspname <> 'pg_catalog' AND n.nspname <> 'information_schema' AND pg_catalog.pg_type_is_visible(t.oid) AND pg_catalog.format_type(t.oid, NULL) = 'obj_type') a,
  (SELECT count(*) as permtypecnt FROM pg_catalog.pg_type t LEFT JOIN pg_catalog.pg_namespace n ON n.oid = t.typnamespace
  WHERE (t.typrelid = 0 OR (SELECT c.relkind = 'c' FROM pg_catalog.pg_class c WHERE c.oid = t.typrelid))
  AND NOT EXISTS(SELECT 1 FROM pg_catalog.pg_type el WHERE el.oid = t.typelem AND el.typarray = t.oid)
  AND n.nspname <> 'pg_catalog' AND n.nspname <> 'information_schema' AND pg_catalog.pg_type_is_visible(t.oid) AND pg_catalog.format_type(t.oid, NULL) = 'perm_type') b;
  IF cnt = 0 THEN
    CREATE TYPE obj_type AS ENUM ('TABLE','VIEW','COLUMN','SEQUENCE','FUNCTION','SCHEMA','DATABASE');
  END IF;
  IF cnt2 = 0 THEN
    CREATE TYPE perm_type AS ENUM ('SELECT','INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER','USAGE','CREATE','EXECUTE','CONNECT','TEMPORARY');
  END IF;

  IF ddl_only THEN
    RAISE NOTICE 'Only generating DDL, not actually creating anything...';
  END IF;

  IF ddl_only THEN
    RAISE NOTICE '%', 'CREATE SCHEMA ' || quote_ident(dest_schema);
  ELSE
    EXECUTE 'CREATE SCHEMA ' || quote_ident(dest_schema) ;
  END IF;

  -- MV: Create Collations
  action := 'Collations';
  cnt := 0;
  FOR arec IN
    SELECT n.nspname as schemaname, a.rolname as ownername , c.collname, c.collprovider,  c.collcollate as locale,
    'CREATE COLLATION ' || quote_ident(dest_schema) || '."' || c.collname || '" (provider = ' || CASE WHEN c.collprovider = 'i' THEN 'icu' WHEN c.collprovider = 'c' THEN 'libc' ELSE '' END || ', locale = ''' || c.collcollate || ''');' as COLL_DDL
    FROM pg_collation c JOIN pg_namespace n ON (c.collnamespace = n.oid) JOIN pg_roles a ON (c.collowner = a.oid) WHERE n.nspname = quote_ident(source_schema) order by c.collname
  LOOP
    BEGIN
      cnt := cnt + 1;
      IF ddl_only THEN
        RAISE INFO '%', arec.coll_ddl;
      ELSE
        EXECUTE arec.coll_ddl;
      END IF;
    END;
  END LOOP;
  RAISE NOTICE '  COLLATIONS cloned: %', LPAD(cnt::text, 5, ' ');

  -- MV: Create Domains
  action := 'Domains';
  cnt := 0;
  FOR arec IN
    SELECT n.nspname as "Schema", t.typname as "Name", pg_catalog.format_type(t.typbasetype, t.typtypmod) as "Type",
    (SELECT c.collname FROM pg_catalog.pg_collation c, pg_catalog.pg_type bt WHERE c.oid = t.typcollation AND
    bt.oid = t.typbasetype AND t.typcollation <> bt.typcollation) as "Collation",
    CASE WHEN t.typnotnull THEN 'not null' END as "Nullable", t.typdefault as "Default",
    pg_catalog.array_to_string(ARRAY(SELECT pg_catalog.pg_get_constraintdef(r.oid, true) FROM pg_catalog.pg_constraint r WHERE t.oid = r.contypid), ' ') as "Check",
    'CREATE DOMAIN ' || quote_ident(dest_schema) || '.' || t.typname || ' AS ' || pg_catalog.format_type(t.typbasetype, t.typtypmod) ||
    CASE WHEN t.typnotnull IS NOT NULL THEN ' NOT NULL ' ELSE ' ' END || CASE WHEN t.typdefault IS NOT NULL THEN 'DEFAULT ' || t.typdefault || ' ' ELSE ' ' END ||
    pg_catalog.array_to_string(ARRAY(SELECT pg_catalog.pg_get_constraintdef(r.oid, true) FROM pg_catalog.pg_constraint r WHERE t.oid = r.contypid), ' ') || ';' AS DOM_DDL
    FROM pg_catalog.pg_type t LEFT JOIN pg_catalog.pg_namespace n ON n.oid = t.typnamespace
    WHERE t.typtype = 'd' AND n.nspname = quote_ident(source_schema) AND pg_catalog.pg_type_is_visible(t.oid) ORDER BY 1, 2
  LOOP
    BEGIN
      cnt := cnt + 1;
      IF ddl_only THEN
        RAISE INFO '%', arec.dom_ddl;
      ELSE
        EXECUTE arec.dom_ddl;
      END IF;
    END;
  END LOOP;
  RAISE NOTICE '     DOMAINS cloned: %', LPAD(cnt::text, 5, ' ');

  -- MV: Create types
  action := 'Types';
  cnt := 0;
  FOR arec IN
    SELECT c.relkind, n.nspname AS schemaname, t.typname AS typname, t.typcategory, CASE WHEN t.typcategory='C' THEN
    'CREATE TYPE ' || quote_ident(dest_schema) || '.' || t.typname || ' AS (' || array_to_string(array_agg(a.attname || ' ' || pg_catalog.format_type(a.atttypid, a.atttypmod) ORDER BY c.relname, a.attnum),', ') || ');'
    WHEN t.typcategory='E' THEN
    'CREATE TYPE ' || quote_ident(dest_schema) || '.' || t.typname || ' AS ENUM (' || REPLACE(quote_literal(array_to_string(array_agg(e.enumlabel ORDER BY e.enumsortorder),',')), ',', ''',''') || ');'
    ELSE '' END AS type_ddl FROM pg_type t JOIN pg_namespace n ON (n.oid = t.typnamespace)
    LEFT JOIN pg_enum e ON (t.oid = e.enumtypid)
    LEFT JOIN pg_class c ON (c.reltype = t.oid) LEFT JOIN pg_attribute a ON (a.attrelid = c.oid)
    WHERE n.nspname = quote_ident(source_schema) and (c.relkind IS NULL or c.relkind = 'c') and t.typcategory in ('C', 'E') group by 1,2,3,4 order by n.nspname, t.typcategory, t.typname
  LOOP
    BEGIN
      cnt := cnt + 1;
      -- Keep composite and enum types in separate branches for fine tuning later if needed.
      IF arec.typcategory = 'E' THEN
          -- RAISE NOTICE '%', arec.type_ddl;
      IF ddl_only THEN
        RAISE INFO '%', arec.type_ddl;
      ELSE
        EXECUTE arec.type_ddl;
      END IF;

      ELSEIF arec.typcategory = 'C' THEN
        -- RAISE NOTICE '%', arec.type_ddl;
        IF ddl_only THEN
          RAISE INFO '%', arec.type_ddl;
        ELSE
          EXECUTE arec.type_ddl;
        END IF;
      ELSE
          RAISE NOTICE 'Unhandled type:%-%', arec.typcategory, arec.typname;
      END IF;
    END;
  END LOOP;
  RAISE NOTICE '       TYPES cloned: %', LPAD(cnt::text, 5, ' ');

  -- Create sequences
  action := 'Sequences';
  seq_cnt := 0;
  -- TODO: Find a way to make this sequence's owner is the correct table.
  FOR object IN
    SELECT sequence_name::text
      FROM information_schema.sequences
     WHERE sequence_schema = quote_ident(source_schema)
  LOOP
    seq_cnt := seq_cnt + 1;
    IF ddl_only THEN
      RAISE INFO '%', 'CREATE SEQUENCE ' || quote_ident(dest_schema) || '.' || quote_ident(object) || ';';
    ELSE
      EXECUTE 'CREATE SEQUENCE ' || quote_ident(dest_schema) || '.' || quote_ident(object);
    END IF;
    srctbl := quote_ident(source_schema) || '.' || quote_ident(object);

    EXECUTE 'SELECT last_value, is_called
              FROM ' || quote_ident(source_schema) || '.' || quote_ident(object) || ';'
              INTO sq_last_value, sq_is_called;

    EXECUTE 'SELECT max_value, start_value, increment_by, min_value, cache_size, cycle, data_type
              FROM pg_catalog.pg_sequences WHERE schemaname='|| quote_literal(source_schema) || ' AND sequencename=' || quote_literal(object) || ';'
              INTO sq_max_value, sq_start_value, sq_increment_by, sq_min_value, sq_cache_value, sq_is_cycled, sq_data_type ;

    IF sq_is_cycled
      THEN
        sq_cycled := 'CYCLE';
    ELSE
        sq_cycled := 'NO CYCLE';
    END IF;

    qry := 'ALTER SEQUENCE '   || quote_ident(dest_schema) || '.' || quote_ident(object)
           || ' AS ' || sq_data_type
           || ' INCREMENT BY ' || sq_increment_by
           || ' MINVALUE '     || sq_min_value
           || ' MAXVALUE '     || sq_max_value
           || ' START WITH '   || sq_start_value
           || ' RESTART '      || sq_min_value
           || ' CACHE '        || sq_cache_value
           || ' '              || sq_cycled || ' ;' ;

    IF ddl_only THEN
      RAISE INFO '%', qry;
    ELSE
      EXECUTE qry;
    END IF;

    buffer := quote_ident(dest_schema) || '.' || quote_ident(object);
    IF include_recs THEN
      EXECUTE 'SELECT setval( ''' || buffer || ''', ' || sq_last_value || ', ' || sq_is_called || ');' ;
    ELSE
      if ddl_only THEN
        RAISE INFO '%', 'SELECT setval( ''' || buffer || ''', ' || sq_start_value || ', ' || sq_is_called || ');' ;
      ELSE
        EXECUTE 'SELECT setval( ''' || buffer || ''', ' || sq_start_value || ', ' || sq_is_called || ');' ;
      END IF;

    END IF;
  END LOOP;
  RAISE NOTICE '   SEQUENCES cloned: %', LPAD(seq_cnt::text, 5, ' ');

-- Create tables
  action := 'Tables';
  cnt := 0;
  FOR object IN
    SELECT TABLE_NAME::text
      FROM information_schema.tables
     WHERE table_schema = quote_ident(source_schema)
       AND table_type = 'BASE TABLE'

  LOOP
    cnt := cnt + 1;
    buffer := quote_ident(dest_schema) || '.' || quote_ident(object);
    IF ddl_only THEN
      RAISE INFO '%', 'CREATE TABLE ' || buffer || ' (LIKE ' || quote_ident(source_schema) || '.' || quote_ident(object) || ' INCLUDING ALL)';
    ELSE
      EXECUTE 'CREATE TABLE ' || buffer || ' (LIKE ' || quote_ident(source_schema) || '.' || quote_ident(object) || ' INCLUDING ALL)';
    END IF;

    -- INCLUDING ALL creates new index names, we restore them to the old name.
    -- There should be no conflicts since they live in different schemas
    FOR ix_old_name, ix_new_name IN
      SELECT old.indexname, new.indexname
      FROM pg_indexes old, pg_indexes new
      WHERE old.schemaname = source_schema
        AND new.schemaname = dest_schema
        AND old.tablename = new.tablename
        AND old.tablename = object
        AND old.indexname <> new.indexname
        AND regexp_replace(old.indexdef, E'.*USING','') = regexp_replace(new.indexdef, E'.*USING','')
        ORDER BY old.indexname, new.indexname
    LOOP
      IF ddl_only THEN
        RAISE INFO '%', 'ALTER INDEX ' || quote_ident(dest_schema) || '.'  || quote_ident(ix_new_name) || ' RENAME TO ' || quote_ident(ix_old_name) || ';';
      ELSE
        EXECUTE 'ALTER INDEX ' || quote_ident(dest_schema) || '.'  || quote_ident(ix_new_name) || ' RENAME TO ' || quote_ident(ix_old_name) || ';';
      END IF;
    END LOOP;

    records_count := 0;
    IF include_recs
      THEN
      -- Insert records from source table
      RAISE NOTICE 'Populating cloned table, %', buffer;
      EXECUTE 'INSERT INTO ' || buffer || ' SELECT * FROM ' || quote_ident(source_schema) || '.' || quote_ident(object) || ';';

      -- restart the counter for PK's internal identity sequence
      EXECUTE 'SELECT count(*) FROM ' || quote_ident(dest_schema) || '.' || quote_ident(object) || ';' INTO records_count;
      FOR column_ IN
        SELECT column_name::text
            FROM information_schema.columns
        WHERE
            table_schema = dest_schema AND
            table_name = object AND
            is_identity = 'YES'
      LOOP
          EXECUTE 'ALTER TABLE ' || quote_ident(dest_schema) || '.' || quote_ident(object) || ' ALTER COLUMN ' || quote_ident(column_) || ' RESTART WITH ' || records_count + 1 || ';';
      END LOOP;
    END IF;

    SET search_path = '';
    FOR column_, default_ IN
      SELECT column_name::text,
             REPLACE(column_default::text, source_schema, dest_schema)
        FROM information_schema.COLUMNS
       WHERE table_schema = source_schema
         AND TABLE_NAME = object
         AND column_default LIKE 'nextval(%' || quote_ident(source_schema) || '%::regclass)'
    LOOP
      IF ddl_only THEN
        -- May need to come back and revisit this since previous sql will not return anything since no schema as created!
        RAISE INFO '%', 'ALTER TABLE ' || buffer || ' ALTER COLUMN ' || column_ || ' SET DEFAULT ' || default_ || ';';
      ELSE
        EXECUTE 'ALTER TABLE ' || buffer || ' ALTER COLUMN ' || column_ || ' SET DEFAULT ' || default_;
      END IF;
    END LOOP;
    EXECUTE 'SET search_path = ' || quote_ident(source_schema) ;

  END LOOP;
  RAISE NOTICE '      TABLES cloned: %', LPAD(cnt::text, 5, ' ');

  --  add FK constraint
  action := 'FK Constraints';
  cnt := 0;
  SET search_path = '';
  FOR qry IN
    SELECT 'ALTER TABLE ' || quote_ident(dest_schema) || '.' || quote_ident(rn.relname)
                          || ' ADD CONSTRAINT ' || quote_ident(ct.conname) || ' ' || REPLACE(pg_get_constraintdef(ct.oid), 'REFERENCES ' ||quote_ident(source_schema), 'REFERENCES ' || quote_ident(dest_schema)) || ';'
      FROM pg_constraint ct
      JOIN pg_class rn ON rn.oid = ct.conrelid
     WHERE connamespace = src_oid
       AND rn.relkind = 'r'
       AND ct.contype = 'f'
  LOOP
    cnt := cnt + 1;
    IF ddl_only THEN
      RAISE INFO '%', qry;
    ELSE
      EXECUTE qry;
    END IF;
  END LOOP;
  EXECUTE 'SET search_path = ' || quote_ident(source_schema) ;
  RAISE NOTICE '       FKEYS cloned: %', LPAD(cnt::text, 5, ' ');

-- Create views
  action := 'Views';
  cnt := 0;
  FOR object IN
    SELECT table_name::text,
           view_definition
      FROM information_schema.views
     WHERE table_schema = quote_ident(source_schema)

  LOOP
    cnt := cnt + 1;
    buffer := quote_ident(dest_schema) || '.' || quote_ident(object);
    SELECT view_definition INTO v_def
      FROM information_schema.views
     WHERE table_schema = quote_ident(source_schema)
       AND table_name = quote_ident(object);

    IF ddl_only THEN
      RAISE INFO '%', 'CREATE OR REPLACE VIEW ' || buffer || ' AS ' || v_def || ';' ;
    ELSE
    EXECUTE 'CREATE OR REPLACE VIEW ' || buffer || ' AS ' || v_def || ';' ;
    END IF;
  END LOOP;
  RAISE NOTICE '       VIEWS cloned: %', LPAD(cnt::text, 5, ' ');

  -- Create Materialized views
    action := 'Mat. Views';
    cnt := 0;
    FOR object IN
      SELECT matviewname::text,
             definition
        FROM pg_catalog.pg_matviews
       WHERE schemaname = quote_ident(source_schema)

    LOOP
      cnt := cnt + 1;
      buffer := dest_schema || '.' || quote_ident(object);
      SELECT replace(definition,';','') INTO v_def
        FROM pg_catalog.pg_matviews
       WHERE schemaname = quote_ident(source_schema)
         AND matviewname = quote_ident(object);

         IF include_recs THEN
           EXECUTE 'CREATE MATERIALIZED VIEW ' || buffer || ' AS ' || v_def || ';' ;
         ELSE
           IF ddl_only THEN
             RAISE INFO '%', 'CREATE MATERIALIZED VIEW ' || buffer || ' AS ' || v_def || ' WITH NO DATA;' ;
           ELSE
             EXECUTE 'CREATE MATERIALIZED VIEW ' || buffer || ' AS ' || v_def || ' WITH NO DATA;' ;
           END IF;

         END IF;

    END LOOP;
    RAISE NOTICE '   MAT VIEWS cloned: %', LPAD(cnt::text, 5, ' ');

-- Create functions
  action := 'Functions';
  cnt := 0;
  FOR func_oid IN
    SELECT oid
      FROM pg_proc
     WHERE pronamespace = src_oid
  LOOP
    cnt := cnt + 1;
    SELECT pg_get_functiondef(func_oid) INTO qry;
    SELECT replace(qry, source_schema, dest_schema) INTO dest_qry;
    IF ddl_only THEN
      RAISE INFO '%', dest_qry;
    ELSE
      EXECUTE dest_qry;
    END IF;

  END LOOP;
  RAISE NOTICE '   FUNCTIONS cloned: %', LPAD(cnt::text, 5, ' ');

  -- MV: Create Triggers
  action := 'Triggers';
  cnt := 0;
  FOR arec IN
    SELECT trigger_schema, trigger_name, event_object_table, action_order, action_condition, action_statement, action_orientation, action_timing, array_to_string(array_agg(event_manipulation::text), ' OR '),
    'CREATE TRIGGER ' || trigger_name || ' ' || action_timing || ' ' || array_to_string(array_agg(event_manipulation::text), ' OR ') || ' ON ' || quote_ident(dest_schema) || '.' || event_object_table ||
    ' FOR EACH ' || action_orientation || ' ' || action_statement || ';' as TRIG_DDL
    FROM information_schema.triggers where trigger_schema = quote_ident(source_schema) GROUP BY 1,2,3,4,5,6,7,8
  LOOP
    BEGIN
      cnt := cnt + 1;
      IF ddl_only THEN
        RAISE INFO '%', arec.trig_ddl;
      ELSE
        EXECUTE arec.trig_ddl;
      END IF;

    END;
  END LOOP;
  RAISE NOTICE '    TRIGGERS cloned: %', LPAD(cnt::text, 5, ' ');

  -- ---------------------
  -- MV: Permissions: Defaults
  -- ---------------------
  action := 'PRIVS: Defaults';
  cnt := 0;
  FOR arec IN
    SELECT pg_catalog.pg_get_userbyid(d.defaclrole) AS "owner", n.nspname AS schema,
    CASE d.defaclobjtype WHEN 'r' THEN 'table' WHEN 'S' THEN 'sequence' WHEN 'f' THEN 'function' WHEN 'T' THEN 'type' WHEN 'n' THEN 'schema' END AS atype,
    d.defaclacl as defaclacl, pg_catalog.array_to_string(d.defaclacl, ',') as defaclstr
    FROM pg_catalog.pg_default_acl d LEFT JOIN pg_catalog.pg_namespace n ON (n.oid = d.defaclnamespace) WHERE n.nspname IS NOT NULL and n.nspname = quote_ident(source_schema) ORDER BY 3, 2, 1
  LOOP
    BEGIN
      -- RAISE NOTICE 'owner=%  type=%  defaclacl=%  defaclstr=%', arec.owner, arec.atype, arec.defaclacl, arec.defaclstr;

      FOREACH aclstr IN ARRAY arec.defaclacl
      LOOP
          cnt := cnt + 1;
          -- RAISE NOTICE 'aclstr=%', aclstr;
          -- break up into grantor, grantee, and privs, mydb_update=rwU/mydb_owner
          SELECT split_part(aclstr, '=',1) INTO grantee;
          SELECT split_part(aclstr, '=',2) INTO grantor;
          SELECT split_part(grantor, '/',1) INTO privs;
          SELECT split_part(grantor, '/',2) INTO grantor;
          -- RAISE NOTICE 'grantor=%  grantee=%  privs=%', grantor, grantee, privs;

          IF arec.atype = 'function' THEN
            -- Just having execute is enough to grant all apparently.
            buffer := 'ALTER DEFAULT PRIVILEGES FOR ROLE ' || grantor || ' IN SCHEMA ' || quote_ident(dest_schema) || ' GRANT ALL ON FUNCTIONS TO "' || grantee || '";';
            IF ddl_only THEN
              RAISE INFO '%', buffer;
            ELSE
              EXECUTE buffer;
            END IF;

          ELSIF arec.atype = 'sequence' THEN
            IF POSITION('r' IN privs) > 0 AND POSITION('w' IN privs) > 0 AND POSITION('U' IN privs) > 0 THEN
              -- arU is enough for all privs
              buffer := 'ALTER DEFAULT PRIVILEGES FOR ROLE ' || grantor || ' IN SCHEMA ' || quote_ident(dest_schema) || ' GRANT ALL ON SEQUENCES TO "' || grantee || '";';
              IF ddl_only THEN
                RAISE INFO '%', buffer;
              ELSE
                EXECUTE buffer;
              END IF;

            ELSE
              -- have to specify each priv individually
              buffer2 := '';
              IF POSITION('r' IN privs) > 0 THEN
                    buffer2 := 'SELECT';
              END IF;
              IF POSITION('w' IN privs) > 0 THEN
                IF buffer2 = '' THEN
                  buffer2 := 'UPDATE';
                ELSE
                  buffer2 := buffer2 || ', UPDATE';
                END IF;
              END IF;
              IF POSITION('U' IN privs) > 0 THEN
                    IF buffer2 = '' THEN
                  buffer2 := 'USAGE';
                ELSE
                  buffer2 := buffer2 || ', USAGE';
                END IF;
              END IF;
              buffer := 'ALTER DEFAULT PRIVILEGES FOR ROLE ' || grantor || ' IN SCHEMA ' || quote_ident(dest_schema) || ' GRANT ' || buffer2 || ' ON SEQUENCES TO "' || grantee || '";';
              IF ddl_only THEN
                RAISE INFO '%', buffer;
              ELSE
                EXECUTE buffer;
              END IF;

            END IF;
          ELSIF arec.atype = 'table' THEN
            -- do each priv individually, jeeeesh!
            buffer2 := '';
            IF POSITION('a' IN privs) > 0 THEN
              buffer2 := 'INSERT';
            END IF;
            IF POSITION('r' IN privs) > 0 THEN
              IF buffer2 = '' THEN
                buffer2 := 'SELECT';
              ELSE
                buffer2 := buffer2 || ', SELECT';
              END IF;
            END IF;
            IF POSITION('w' IN privs) > 0 THEN
              IF buffer2 = '' THEN
                buffer2 := 'UPDATE';
              ELSE
                buffer2 := buffer2 || ', UPDATE';
              END IF;
            END IF;
            IF POSITION('d' IN privs) > 0 THEN
              IF buffer2 = '' THEN
                buffer2 := 'DELETE';
              ELSE
                buffer2 := buffer2 || ', DELETE';
              END IF;
            END IF;
            IF POSITION('t' IN privs) > 0 THEN
              IF buffer2 = '' THEN
                buffer2 := 'TRIGGER';
              ELSE
                buffer2 := buffer2 || ', TRIGGER';
              END IF;
            END IF;
            IF POSITION('T' IN privs) > 0 THEN
              IF buffer2 = '' THEN
                buffer2 := 'TRUNCATE';
              ELSE
                buffer2 := buffer2 || ', TRUNCATE';
              END IF;
            END IF;
            buffer := 'ALTER DEFAULT PRIVILEGES FOR ROLE ' || grantor || ' IN SCHEMA ' || quote_ident(dest_schema) || ' GRANT ' || buffer2 || ' ON TABLES TO "' || grantee || '";';
            IF ddl_only THEN
              RAISE INFO '%', buffer;
            ELSE
              EXECUTE buffer;
            END IF;

          ELSE
              RAISE WARNING 'Doing nothing for type=%  privs=%', arec.atype, privs;
          END IF;
      END LOOP;
    END;
  END LOOP;

  RAISE NOTICE '  DFLT PRIVS cloned: %', LPAD(cnt::text, 5, ' ');

  -- MV: PRIVS: schema
  -- crunchy data extension, check_access
  -- SELECT role_path, base_role, as_role, objtype, schemaname, objname, array_to_string(array_agg(privname),',') as privs  FROM all_access()
  -- WHERE base_role != CURRENT_USER and objtype = 'schema' and schemaname = 'public' group by 1,2,3,4,5,6;

  action := 'PRIVS: Schema';
  cnt := 0;
  FOR arec IN
    SELECT 'GRANT ' || p.perm::perm_type || ' ON SCHEMA ' || quote_ident(dest_schema) || ' TO "' || r.rolname || '";' as schema_ddl
    FROM pg_catalog.pg_namespace AS n CROSS JOIN pg_catalog.pg_roles AS r CROSS JOIN (VALUES ('USAGE'), ('CREATE')) AS p(perm)
    WHERE n.nspname = quote_ident(source_schema) AND NOT r.rolsuper AND has_schema_privilege(r.oid, n.oid, p.perm) order by r.rolname, p.perm::perm_type
  LOOP
    BEGIN
      cnt := cnt + 1;
      IF ddl_only THEN
        RAISE INFO '%', arec.schema_ddl;
      ELSE
        EXECUTE arec.schema_ddl;
      END IF;

    END;
  END LOOP;
  RAISE NOTICE 'SCHEMA PRIVS cloned: %', LPAD(cnt::text, 5, ' ');

  -- MV: PRIVS: sequences
  action := 'PRIVS: Sequences';
  cnt := 0;
  FOR arec IN
    SELECT 'GRANT ' || p.perm::perm_type || ' ON ' || quote_ident(dest_schema) || '.' || t.relname::text || ' TO "' || r.rolname || '";' as seq_ddl
    FROM pg_catalog.pg_class AS t CROSS JOIN pg_catalog.pg_roles AS r CROSS JOIN (VALUES ('SELECT'), ('USAGE'), ('UPDATE')) AS p(perm)
    WHERE t.relnamespace::regnamespace::name = quote_ident(source_schema) AND t.relkind = 'S'  AND NOT r.rolsuper AND has_sequence_privilege(r.oid, t.oid, p.perm)
  LOOP
    BEGIN
      cnt := cnt + 1;
      IF ddl_only OR seq_cnt = 0 THEN
        RAISE INFO '%', arec.seq_ddl;
      ELSE
        EXECUTE arec.seq_ddl;
      END IF;

    END;
  END LOOP;
  RAISE NOTICE '  SEQ. PRIVS cloned: %', LPAD(cnt::text, 5, ' ');

  -- MV: PRIVS: functions
  action := 'PRIVS: Functions';
  cnt := 0;
  FOR arec IN
    SELECT 'GRANT EXECUTE ON FUNCTION ' || quote_ident(dest_schema) || '.' || regexp_replace(f.oid::regprocedure::text, '^((("[^"]*")|([^"][^.]*))\.)?', '') || ' TO "' || r.rolname || '";' as func_ddl
    FROM pg_catalog.pg_proc f CROSS JOIN pg_catalog.pg_roles AS r WHERE f.pronamespace::regnamespace::name = quote_ident(source_schema) AND NOT r.rolsuper AND has_function_privilege(r.oid, f.oid, 'EXECUTE')
    order by regexp_replace(f.oid::regprocedure::text, '^((("[^"]*")|([^"][^.]*))\.)?', '')
  LOOP
    BEGIN
      cnt := cnt + 1;
      IF ddl_only THEN
        RAISE INFO '%', arec.func_ddl;
      ELSE
        EXECUTE arec.func_ddl;
      END IF;

    END;
  END LOOP;
  RAISE NOTICE '  FUNC PRIVS cloned: %', LPAD(cnt::text, 5, ' ');

  -- MV: PRIVS: tables
  action := 'PRIVS: Tables';
  -- regular, partitioned, and foreign tables plus view and materialized view permissions. TODO: implement foreign table defs.
  cnt := 0;
  FOR arec IN
    SELECT 'GRANT ' || p.perm::perm_type || CASE WHEN t.relkind in ('r', 'p', 'f') THEN ' ON TABLE ' WHEN t.relkind in ('v', 'm')  THEN ' ON ' END || quote_ident(dest_schema) || '.' || t.relname::text || ' TO "' || r.rolname || '";' as tbl_ddl,
    has_table_privilege(r.oid, t.oid, p.perm) AS granted, t.relkind
    FROM pg_catalog.pg_class AS t CROSS JOIN pg_catalog.pg_roles AS r CROSS JOIN (VALUES (TEXT 'SELECT'), ('INSERT'), ('UPDATE'), ('DELETE'), ('TRUNCATE'), ('REFERENCES'), ('TRIGGER')) AS p(perm)
    WHERE t.relnamespace::regnamespace::name = quote_ident(source_schema)  AND t.relkind in ('r', 'p', 'f', 'v', 'm')  AND NOT r.rolsuper AND has_table_privilege(r.oid, t.oid, p.perm) order by t.relname::text, t.relkind
  LOOP
    BEGIN
      cnt := cnt + 1;
      -- RAISE NOTICE 'ddl=%', arec.tbl_ddl;
      IF arec.relkind = 'f' THEN
        RAISE WARNING 'Foreign tables are not currently implemented, so skipping privs for them. ddl=%', arec.tbl_ddl;
      ELSE
        IF ddl_only THEN
          RAISE INFO '%', arec.tbl_ddl;
        ELSE
          EXECUTE arec.tbl_ddl;
        END IF;

      END IF;
    END;
  END LOOP;
  RAISE NOTICE ' TABLE PRIVS cloned: %', LPAD(cnt::text, 5, ' ');

  -- Set the search_path back to what it was before
  EXECUTE 'SET search_path = ' || src_path_old;

  EXCEPTION
     WHEN others THEN
     BEGIN
         GET STACKED DIAGNOSTICS v_diag1 = MESSAGE_TEXT, v_diag2 = PG_EXCEPTION_DETAIL, v_diag3 = PG_EXCEPTION_HINT, v_diag4 = RETURNED_SQLSTATE, v_diag5 = PG_CONTEXT, v_diag6 = PG_EXCEPTION_CONTEXT;
 	 -- v_ret := 'line=' || v_diag6 || '. '|| v_diag4 || '. ' || v_diag1 || ' .' || v_diag2 || ' .' || v_diag3;
 	 v_ret := 'line=' || v_diag6 || '. '|| v_diag4 || '. ' || v_diag1;
         RAISE EXCEPTION 'Action: %  Diagnostics: %',action, v_ret;
         -- Set the search_path back to what it was before
         EXECUTE 'SET search_path = ' || src_path_old;
         RETURN;
     END;

RETURN;
END;

$BODY$
  LANGUAGE plpgsql VOLATILE
  COST 100;
ALTER FUNCTION public.clone_schema(text, text, boolean, boolean) OWNER TO "{db_user}";
"""


class CloneSchema:

    def _create_clone_schema_function(self):
        """
        Creates a postgres function `clone_schema` that copies a schema and its
        contents. Will replace any existing `clone_schema` functions owned by the
        `postgres` superuser.
        """
        cursor = connection.cursor()

        db_user = settings.DATABASES["default"].get("USER", None) or "postgres"
        cursor.execute(CLONE_SCHEMA_FUNCTION.format(db_user=db_user))
        cursor.close()

    def clone_schema(self, base_schema_name, new_schema_name, set_connection=True):
        """
        Creates a new schema `new_schema_name` as a clone of an existing schema
        `old_schema_name`.
        """
        if set_connection:
            connection.set_schema_to_public()
        cursor = connection.cursor()

        # check if the clone_schema function already exists in the db
        try:
            cursor.execute("SELECT 'clone_schema'::regproc")
        except ProgrammingError:
            self._create_clone_schema_function()
            transaction.commit()

        if schema_exists(new_schema_name):
            raise ValidationError("New schema name already exists")

        sql = 'SELECT clone_schema(%(base_schema)s, %(new_schema)s, true, false)'
        cursor.execute(
            sql,
            {'base_schema': base_schema_name, 'new_schema': new_schema_name}
        )
        cursor.close()
