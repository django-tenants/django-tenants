import unittest

from django.db import connection
from django.test import TransactionTestCase

from django_tenants.utils import FakeTenant, get_public_schema_name

mysql_only = unittest.skipUnless(
    connection.vendor == 'mysql',
    "MySQL-only test — run with DATABASE_ENGINE=django_tenants.mysql_backend",
)


@mysql_only
class MySQLTenantSwitchingTestCase(TransactionTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        connection.set_schema_to_public()
        with connection.cursor() as cursor:
            cursor.execute('CREATE DATABASE IF NOT EXISTS tenant_switch_test')
            cursor.execute('CREATE DATABASE IF NOT EXISTS tenant_switch_test_2')
            cursor.execute('CREATE DATABASE IF NOT EXISTS fake_tenant_db')

    @classmethod
    def tearDownClass(cls):
        connection.set_schema_to_public()
        with connection.cursor() as cursor:
            cursor.execute('DROP DATABASE IF EXISTS tenant_switch_test')
            cursor.execute('DROP DATABASE IF EXISTS tenant_switch_test_2')
            cursor.execute('DROP DATABASE IF EXISTS fake_tenant_db')
        super().tearDownClass()

    def test_starts_on_public_schema(self):
        self.assertEqual(connection.schema_name, get_public_schema_name())

    def test_set_schema_switches_current_database(self):
        connection.set_schema('tenant_switch_test')
        with connection.cursor() as cursor:
            cursor.execute('SELECT DATABASE()')
            self.assertEqual(cursor.fetchone()[0], 'tenant_switch_test')
        connection.set_schema_to_public()

    def test_set_schema_to_public_returns_to_public_database(self):
        connection.set_schema('tenant_switch_test_2')
        connection.set_schema_to_public()
        with connection.cursor() as cursor:
            cursor.execute('SELECT DATABASE()')
            self.assertEqual(cursor.fetchone()[0], get_public_schema_name())

    def test_set_tenant_accepts_fake_tenant(self):
        connection.set_tenant(FakeTenant(schema_name='fake_tenant_db'))
        self.assertEqual(connection.schema_name, 'fake_tenant_db')
        connection.set_schema_to_public()

    def test_set_tenant_does_not_mutate_settings_dict_name(self):
        """
        Regression test: settings_dict['NAME'] must never be overwritten by
        tenant switching. Django's own test-database machinery
        (BaseDatabaseCreation.create_test_db()/destroy_test_db()) reads and
        writes connection.settings_dict['NAME'] to track the test database's
        name across a test run. If set_settings_schema() ever stomps on
        that key again, it would collide with Django's bookkeeping and
        could cause the wrong database to be destroyed at teardown.
        """
        original_name = connection.settings_dict['NAME']

        connection.set_schema('tenant_switch_test')
        self.assertEqual(connection.settings_dict['NAME'], original_name)

        connection.set_schema_to_public()
        self.assertEqual(connection.settings_dict['NAME'], original_name)

        connection.set_tenant(FakeTenant(schema_name='fake_tenant_db'))
        self.assertEqual(connection.settings_dict['NAME'], original_name)

        connection.set_schema_to_public()
        self.assertEqual(connection.settings_dict['NAME'], original_name)
