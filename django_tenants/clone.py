from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.db.utils import ProgrammingError
from django_tenants.utils import schema_exists




class CloneSchema:

    def _create_clone_schema_function(self):
        """
        Creates a postgres function `clone_schema` that copies a schema and its
        contents. Will replace any existing `clone_schema` functions owned by the
        `postgres` superuser.
        """
	clone_schema = open('clone_schema.sql', 'r)
	sql_code = clone_schema.read()
        cursor = connection.cursor()
	clone_schema.close()

        db_user = settings.DATABASES["default"].get("USER", None) or "postgres"
        cursor.execute(sql)
        # cursor.execute(ALTER_FUNCTION_CLONE_SCHEMA.format(db_user=db_user))
        cursor.close()

    def clone_schema(self, base_schema_name, new_schema_name, set_connection=True):
        """
        Creates a new schema `new_schema_name` as a clone of an existing schema
        `old_schema_name`.
        """
        # if set_connection:
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

        sql = f"select clone_schema('{base_schema_name}', '{new_schema_name}', 'DATA');"
        cursor.execute(sql)
        cursor.close()
