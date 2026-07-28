import unittest

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import connection
from django.test import TransactionTestCase

from django_tenants.tests.testcases import BaseTestCase
from django_tenants.utils import (
    FakeTenant,
    create_schema_sql,
    drop_schema_sql,
    get_public_schema_name,
    get_schema_name_validator,
    get_tenant_domain_model,
    get_tenant_model,
    schema_exists,
    schema_rename,
)

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


@mysql_only
class MySQLUtilsDispatchTestCase(TransactionTestCase):
    def test_schema_exists_true_for_public(self):
        self.assertTrue(schema_exists(get_public_schema_name()))

    def test_schema_exists_false_for_missing_database(self):
        self.assertFalse(schema_exists('does_not_exist_db'))

    def test_schema_rename_raises_not_implemented(self):
        class _Tenant:
            schema_name = 'whatever'
        with self.assertRaises(NotImplementedError):
            schema_rename(_Tenant(), 'new_name')

    def test_get_schema_name_validator_returns_mysql_validator(self):
        from django_tenants.mysql_backend.base import _check_schema_name
        self.assertIs(get_schema_name_validator(), _check_schema_name)

    def test_get_schema_name_validator_rejects_invalid_name(self):
        validator = get_schema_name_validator()
        with self.assertRaises(ValidationError):
            validator('invalid/name')

    def test_create_schema_sql_uses_create_database(self):
        self.assertEqual(create_schema_sql('my_tenant', connection), 'CREATE DATABASE `my_tenant`')

    def test_drop_schema_sql_uses_drop_database(self):
        self.assertEqual(drop_schema_sql('my_tenant', connection), 'DROP DATABASE `my_tenant`')


@mysql_only
class MySQLTenantLifecycleTestCase(BaseTestCase):
    def test_create_and_drop_tenant_creates_real_database(self):
        Tenant = get_tenant_model()
        Domain = get_tenant_domain_model()

        tenant = Tenant(schema_name='mysql_lifecycle_test')
        tenant.save()
        domain = Domain(tenant=tenant, domain='mysql-lifecycle.test.com')
        domain.save()

        self.assertTrue(schema_exists('mysql_lifecycle_test'))

        domain.delete()
        tenant.delete(force_drop=True)

        self.assertFalse(schema_exists('mysql_lifecycle_test'))

    def test_fake_migrations_cloning_raises_not_implemented(self):
        from django.test.utils import override_settings

        Tenant = get_tenant_model()
        with override_settings(TENANT_CREATION_FAKES_MIGRATIONS=True, TENANT_BASE_SCHEMA=get_public_schema_name()):
            tenant = Tenant(schema_name='mysql_clone_attempt')
            with self.assertRaises(NotImplementedError):
                tenant.save()


@mysql_only
class MySQLGuardedCommandsTestCase(BaseTestCase):
    def test_clone_tenant_command_raises_not_implemented(self):
        Tenant = get_tenant_model()
        Domain = get_tenant_domain_model()
        tenant = Tenant(schema_name='mysql_clone_source')
        tenant.save()
        self.addCleanup(tenant.delete, force_drop=True)
        domain = Domain(tenant=tenant, domain='mysql-clone-source.test.com')
        domain.save()
        self.addCleanup(domain.delete)

        with self.assertRaises(NotImplementedError):
            call_command(
                'clone_tenant',
                clone_from='mysql_clone_source',
                clone_tenant_fields=False,
                schema_name='mysql_clone_target',
                name='Cloned',
                domain_domain='mysql-clone-target.test.com',
                domain_is_primary=True,
            )

    def test_rename_schema_command_raises_not_implemented(self):
        Tenant = get_tenant_model()
        Domain = get_tenant_domain_model()
        tenant = Tenant(schema_name='mysql_rename_source')
        tenant.save()
        self.addCleanup(tenant.delete, force_drop=True)
        domain = Domain(tenant=tenant, domain='mysql-rename-source.test.com')
        domain.save()
        self.addCleanup(domain.delete)

        with self.assertRaises(NotImplementedError):
            call_command('rename_schema', rename_from='mysql_rename_source', rename_to='mysql_rename_target')
