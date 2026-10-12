from django.db import connection
from django.conf import settings
from django.core.management import call_command
from django.test import TransactionTestCase

from django_tenants.utils import get_public_schema_name


class BaseTestCase(TransactionTestCase):
    """
    Base test case that comes packed with overloaded INSTALLED_APPS,
    custom public tenant, and schemas cleanup on tearDown.
    """

    TENANT_APPS = ('dts_test_app',
                   'django.contrib.contenttypes',
                   'django.contrib.auth', )
    SHARED_APPS = ('django_tenants',
                   'customers')

    @classmethod
    def setUpClass(cls):
        settings.TENANT_MODEL = 'customers.Client'
        settings.TENANT_DOMAIN_MODEL = 'customers.Domain'
        settings.SHARED_APPS = cls.SHARED_APPS
        settings.TENANT_APPS = cls.TENANT_APPS
        settings.INSTALLED_APPS = settings.SHARED_APPS + settings.TENANT_APPS
        if '.test.com' not in settings.ALLOWED_HOSTS:
            settings.ALLOWED_HOSTS += ['.test.com']
        cls.available_apps = settings.INSTALLED_APPS

        super().setUpClass()

    def setUp(self):
        connection.set_schema_to_public()
        super().setUp()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        if '.test.com' in settings.ALLOWED_HOSTS:
            settings.ALLOWED_HOSTS.remove('.test.com')

    @classmethod
    def get_tables_list_in_schema(cls, schema_name):
        cursor = connection.cursor()
        sql = """SELECT table_name FROM information_schema.tables
              WHERE table_schema = %s"""
        cursor.execute(sql, (schema_name, ))
        return [row[0] for row in cursor.fetchall()]

    @classmethod
    def sync_shared(cls):
        call_command('migrate_schemas',
                     schema_name=get_public_schema_name(),
                     interactive=False,
                     verbosity=0)


class TestConnectionClosePreservesSchema(BaseTestCase):
    """
    Regression test: close() should not wipe tenant/schema state.

    Django's TestCase.tearDown() force-closes connections via
    _post_teardown() -> conn.close() and then reuses the same
    DatabaseWrapper instance. If close() cleared the schema to None,
    the next query would raise "Database schema not set".

    The middleware already resets the schema at the start of each
    request, so no tenant can leak between requests.
    """

    def test_close_preserves_schema_name(self):
        """Schema name should persist after close() for reuse."""
        connection.set_schema_to_public()
        self.assertEqual(connection.schema_name, get_public_schema_name())

        connection.close()

        # After close, schema_name should still be available (not None)
        # so that queries don't raise "Database schema not set"
        self.assertIsNotNone(connection.schema_name)

        # Verify we can execute a query without setting the schema again
        cursor = connection.cursor()
        cursor.execute("SELECT 1")
        self.assertEqual(cursor.fetchone()[0], 1)
        cursor.close()

    def test_close_preserves_tenant(self):
        """Tenant object should persist after close() for reuse."""
        connection.set_schema_to_public()
        self.assertIsNotNone(connection.tenant)

        connection.close()

        # Tenant should still be available after close
        self.assertIsNotNone(connection.tenant)
