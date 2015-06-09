import django
from django.core.management import call_command
from django.db import connection
from django.test import TestCase

from tenant_schemas.utils import get_tenant_model
from tenant_schemas.utils import get_public_schema_name


class TenantTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sync_shared()
        tenant_domain = 'tenant.test.com'
        cls.tenant = get_tenant_model()(domain_url=tenant_domain, schema_name='test')
        cls.tenant.save(verbosity=0)  # todo: is there any way to get the verbosity from the test command here?

        connection.set_tenant(cls.tenant)

    @classmethod
    def tearDownClass(cls):
        connection.set_schema_to_public()
        cls.tenant.delete()

        cursor = connection.cursor()
        cursor.execute('DROP SCHEMA test CASCADE')

    @classmethod
    def sync_shared(cls):
        if django.VERSION >= (1, 7, 0):
            call_command('migrate_schemas',
                         schema_name=get_public_schema_name(),
                         interactive=False,
                         verbosity=0)
        else:
            call_command('sync_schemas',
                         schema_name=get_public_schema_name(),
                         tenant=False,
                         public=True,
                         interactive=False,
                         migrate_all=True,
                         verbosity=0,
                         )
