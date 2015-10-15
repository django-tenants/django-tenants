from django.core.management import call_command
from django.db import connection
from django.test import TransactionTestCase

from django_tenants.utils import get_tenant_model, get_tenant_domain_model, get_public_schema_name


class TenantTestCase(TransactionTestCase):
    def setUp(self):
        self.sync_shared()
        self.tenant = get_tenant_model()(schema_name='test')
        self.tenant.save(verbosity=0)  # todo: is there any way to get the verbosity from the test command here?

        # Set up domain
        tenant_domain = 'tenant.test.com'
        self.domain = get_tenant_domain_model()(tenant=self.tenant, domain=tenant_domain)
        self.domain.save()

        connection.set_tenant(self.tenant)

    def tearDown(self):
        connection.set_schema_to_public()
        self.domain.delete()
        self.tenant.delete(force_drop=True)

    @classmethod
    def sync_shared(cls):
        call_command('migrate_schemas',
                     schema_name=get_public_schema_name(),
                     interactive=False,
                     verbosity=0)

