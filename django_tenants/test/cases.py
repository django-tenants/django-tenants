from django.core.management import call_command
from django.db import connection
from django.test import TransactionTestCase

from django_tenants.utils import get_tenant_model, get_tenant_domain_model, get_public_schema_name


class TenantTestCase(TransactionTestCase):
    def setup_tenant(self, tenant):
        """
        Add any additional setting to the tenant before it get saved. This is required if you have
        required fields.
        :param tenant:
        :return:
        """
        pass

    def setup_domain(self, domain):
        """
        Add any additional setting to the domain before it get saved. This is required if you have
        required fields.
        :param domain:
        :return:
        """
        pass

    def setUp(self):
        self.sync_shared()
        self.tenant = get_tenant_model()(schema_name=self.get_test_schema_name())
        self.setup_tenant(self.tenant)
        self.tenant.save(verbosity=0)  # todo: is there any way to get the verbosity from the test command here?

        # Set up domain
        tenant_domain = self.get_test_tenant_domain()
        self.domain = get_tenant_domain_model()(tenant=self.tenant, domain=tenant_domain)
        self.setup_domain(self.domain)
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

    @staticmethod
    def get_test_tenant_domain():
        return 'tenant.test.com'

    @staticmethod
    def get_test_schema_name():
        return 'test'


class FastTenantTestCase(TenantTestCase):

    @classmethod
    def setUpClass(cls):
        cls.sync_shared()
        tenant_model = get_tenant_model()

        test_schema_name = cls.get_test_schema_name()
        test_tenant_domain_name = cls.get_test_tenant_domain()

        if tenant_model.objects.filter(schema_name=test_schema_name).exists():
            cls.tenant = tenant_model.objects.filter(schema_name=test_schema_name).first()
        else:
            cls.tenant = tenant_model(schema_name=test_schema_name)
            cls.tenant.save(verbosity=0)
            cls.domain = get_tenant_domain_model()(tenant=cls.tenant, domain=test_tenant_domain_name)
            cls.domain.save()

        connection.set_tenant(cls.tenant)

    @classmethod
    def tearDownClass(cls):
        connection.set_schema_to_public()
