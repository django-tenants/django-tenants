import django
from django.conf import settings
from django.core.management import call_command
from django.db import connection
from django.test import TestCase

from django_tenants.utils import get_public_schema_name


class BaseTestCase(TestCase):
    """
    Base test case that comes packed with overloaded INSTALLED_APPS,
    custom public tenant, and schemas cleanup on tearDown.
    """
    @classmethod
    def setUpClass(cls):
        settings.TENANT_MODEL = 'django_tenants.Tenant'
        settings.SHARED_APPS = ('django_tenants', )
        settings.TENANT_APPS = ('dts_test_app',
                                'django.contrib.contenttypes',
                                'django.contrib.auth', )
        settings.INSTALLED_APPS = settings.SHARED_APPS + settings.TENANT_APPS

        # Django calls syncdb by default for the test database, but we want
        # a blank public schema for this set of tests.
        connection.set_schema_to_public()
        cursor = connection.cursor()
        cursor.execute('DROP SCHEMA %s CASCADE; CREATE SCHEMA %s;'
                       % (get_public_schema_name(), get_public_schema_name(), ))
        super(BaseTestCase, cls).setUpClass()

    def setUp(self):
        connection.set_schema_to_public()
        super(BaseTestCase, self).setUp()

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
