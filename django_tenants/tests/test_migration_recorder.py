from unittest import mock

from django.core.management import call_command
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder

from django_tenants.migration_recorder import has_table
from django_tenants.tests.testcases import BaseTestCase
from django_tenants.utils import quote_schema_name


class MigrationRecorderHasTableTest(BaseTestCase):
    """
    MigrationRecorder.has_table() looks for the migrations table in the
    connection's own schema instead of listing every table. #1269
    """

    def create_schema(self, schema_name, with_migrations_table=False):
        with connection.cursor() as cursor:
            cursor.execute('CREATE SCHEMA %s' % quote_schema_name(schema_name))
        self.addCleanup(self.drop_schema, schema_name)

        if with_migrations_table:
            connection.set_schema(schema_name, include_public=False)
            with connection.schema_editor() as editor:
                editor.create_model(MigrationRecorder.Migration)
            connection.set_schema_to_public()

    @staticmethod
    def drop_schema(schema_name):
        connection.set_schema_to_public()
        with connection.cursor() as cursor:
            cursor.execute('DROP SCHEMA %s CASCADE' % quote_schema_name(schema_name))

    def assertHasTable(self, expected):
        """
        Check has_table() against Django's own answer, which comes from the
        table listing that django-tenants' introspection limits to one schema.
        """
        self.assertIs(MigrationRecorder(connection).has_table(), expected)
        self.assertIs(MigrationRecorder.Migration._meta.db_table in connection.introspection.table_names(),
                      expected)

    def test_finds_the_table_in_the_tenant_schema(self):
        self.create_schema('recorder_tenant', with_migrations_table=True)

        connection.set_schema('recorder_tenant', include_public=False)
        self.assertHasTable(True)

        connection.set_schema('recorder_tenant')
        self.assertHasTable(True)

    def test_empty_schema_without_public_on_the_search_path(self):
        self.create_schema('recorder_empty')
        # public has a migrations table, so the empty schema must not borrow it
        self.assertHasTable(True)

        connection.set_schema('recorder_empty', include_public=False)
        self.assertHasTable(False)

    def test_empty_schema_with_public_on_the_search_path(self):
        self.create_schema('recorder_empty')
        self.assertHasTable(True)

        connection.set_schema('recorder_empty')
        self.assertHasTable(False)

    def test_schema_names_that_need_quoting(self):
        self.create_schema('Recorder.Tenant Schema', with_migrations_table=True)
        self.create_schema('Recorder.Empty Schema')

        connection.set_schema('Recorder.Tenant Schema')
        self.assertHasTable(True)

        connection.set_schema('Recorder.Empty Schema')
        self.assertHasTable(False)

    def test_positive_answer_is_cached(self):
        recorder = MigrationRecorder(connection)
        self.assertTrue(recorder.has_table())

        with self.assertNumQueries(0):
            self.assertTrue(recorder.has_table())

    def test_negative_answer_is_checked_again(self):
        self.create_schema('recorder_empty')
        connection.set_schema('recorder_empty', include_public=False)
        recorder = MigrationRecorder(connection)
        self.assertFalse(recorder.has_table())

        with connection.schema_editor() as editor:
            editor.create_model(MigrationRecorder.Migration)

        self.assertTrue(recorder.has_table())

    def test_other_connections_keep_djangos_check(self):
        # e.g. a second database that does not use the django-tenants backend
        other_connection = mock.Mock()
        recorder = MigrationRecorder(other_connection)

        with mock.patch('django_tenants.migration_recorder.django_has_table', return_value=True) as django_has_table:
            self.assertTrue(recorder.has_table())

        django_has_table.assert_called_once_with(recorder)
        other_connection.cursor.assert_not_called()

    def test_installed_by_the_app_config(self):
        self.assertIs(MigrationRecorder.has_table, has_table)

    def test_migrate_schemas_does_not_list_every_table(self):
        self.create_schema('recorder_migrate')
        statements = []

        def capture_sql(execute, sql, params, many, context):
            statements.append(sql)
            return execute(sql, params, many, context)

        # The standard executor migrates in this process, so the wrapper sees its queries.
        with connection.execute_wrapper(capture_sql):
            for _ in range(2):  # first run creates the tables, the second has nothing to do
                call_command('migrate_schemas', schema_name='recorder_migrate', executor='standard',
                             interactive=False, verbosity=0)

        self.assertEqual([sql for sql in statements if 'pg_table_is_visible' in sql], [])
        self.assertTrue(any('to_regclass' in sql for sql in statements))
        self.assertIn('django_migrations', self.get_tables_list_in_schema('recorder_migrate'))
