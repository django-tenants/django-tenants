"""
Check for the migrations table without listing every table in the database.

Django's MigrationRecorder.has_table() asks introspection for every table name
and looks for django_migrations in the list. On PostgreSQL that list comes from
a query that reads all of pg_class and runs pg_table_is_visible() on each row,
so its cost grows with the number of tables in every schema, and
migrate_schemas makes about four of these calls per tenant. See #1269.
"""
from django.db.migrations.recorder import MigrationRecorder

from django_tenants.postgresql_backend.introspection import DatabaseSchemaIntrospection
from django_tenants.utils import quote_schema_name

django_has_table = MigrationRecorder.has_table


def has_table(self):
    """
    Return True if the connection's schema has the migrations table.

    django-tenants' introspection lists only the tables in the connection's
    own schema, even when public is on the search_path. Looking the table up
    by its schema-qualified name gives the same answer through the catalog
    indexes, and public's migrations table never counts for a tenant that has
    none yet. Connections that don't use that introspection keep Django's check.
    """
    if not isinstance(self.connection.introspection, DatabaseSchemaIntrospection):
        return django_has_table(self)

    # Like Django, only cache a positive answer: the table can be created later.
    if self._has_table:
        return True

    table_name = '{}.{}'.format(
        quote_schema_name(self.connection.schema_name),
        self.connection.ops.quote_name(self.Migration._meta.db_table),
    )
    with self.connection.cursor() as cursor:
        cursor.execute('SELECT to_regclass(%s) IS NOT NULL', [table_name])
        self._has_table = cursor.fetchone()[0]
    return self._has_table


def install_has_table():
    """
    Use has_table() for every MigrationRecorder. Django creates its recorders
    inside the migration loader and executor, so there is no setting to swap
    the class.
    """
    MigrationRecorder.has_table = has_table
