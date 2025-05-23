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
