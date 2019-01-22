from django.core.management import call_command
from django.conf import settings
from django.db import connection
from django.test import TestCase
from django_tenants.utils import get_tenant_model, get_tenant_domain_model, get_public_schema_name

ALLOWED_TEST_DOMAIN = '.test.com'


class TenantTestCase(TestCase):
    tenant = None
    domain = None

    @classmethod
    def setup_tenant(cls, tenant):
        """
        Add any additional setting to the tenant before it get saved. This is required if you have
        required fields.
        :param tenant:
        :return:
        """
        pass

    @classmethod
    def setup_domain(cls, domain):
        """
        Add any additional setting to the domain before it get saved. This is required if you have
        required fields.
        :param domain:
        :return:
        """
        pass

    @classmethod
    def setUpClass(cls):
        cls.sync_shared()
        cls.add_allowed_test_domain()
        cls.tenant = get_tenant_model()(schema_name=cls.get_test_schema_name())
        cls.setup_tenant(cls.tenant)
        cls.tenant.save(verbosity=cls.get_verbosity())

        # Set up domain
        tenant_domain = cls.get_test_tenant_domain()
        cls.domain = get_tenant_domain_model()(tenant=cls.tenant, domain=tenant_domain)
        cls.setup_domain(cls.domain)
        cls.domain.save()

        connection.set_tenant(cls.tenant)

    @classmethod
    def tearDownClass(cls):
        connection.set_schema_to_public()
        cls.domain.delete()
        cls.tenant.delete(force_drop=True)
        cls.remove_allowed_test_domain()

    @classmethod
    def get_verbosity(cls):
        return 0

    @classmethod
    def add_allowed_test_domain(cls):
        # ALLOWED_HOSTS is a special setting of Django setup_test_environment so we can't modify it with helpers
        if ALLOWED_TEST_DOMAIN not in settings.ALLOWED_HOSTS:
            settings.ALLOWED_HOSTS += [ALLOWED_TEST_DOMAIN]

    @classmethod
    def remove_allowed_test_domain(cls):
        if ALLOWED_TEST_DOMAIN in settings.ALLOWED_HOSTS:
            settings.ALLOWED_HOSTS.remove(ALLOWED_TEST_DOMAIN)

    @classmethod
    def sync_shared(cls):
        call_command('migrate_schemas',
                     schema_name=get_public_schema_name(),
                     interactive=False,
                     verbosity=0)

    @classmethod
    def get_test_tenant_domain(cls):
        return 'tenant.test.com'

    @classmethod
    def get_test_schema_name(cls):
        return 'test'


class FastTenantTestCase(TenantTestCase):

    @classmethod
    def flush_data(cls):
        """
        Do you want to flush the data out of the tenant database.
        :return: bool
        """
        return True

    @classmethod
    def use_existing_tenant(cls):
        """
        Gets called if a existing tenant is found in the database
        """
        pass

    @classmethod
    def use_new_tenant(cls):
        """
        Gets called if a new tenant is created in the database
        """
        pass

    @classmethod
    def setup_test_tenant_and_domain(cls):
        cls.tenant = get_tenant_model()(schema_name=cls.get_test_schema_name())
        cls.setup_tenant(cls.tenant)
        cls.tenant.save(verbosity=cls.get_verbosity())

        # Set up domain
        tenant_domain = cls.get_test_tenant_domain()
        cls.domain = get_tenant_domain_model()(tenant=cls.tenant, domain=tenant_domain)
        cls.setup_domain(cls.domain)
        cls.domain.save()
        cls.use_new_tenant()

    @classmethod
    def setUpClass(cls):
        tenant_model = get_tenant_model()

        test_schema_name = cls.get_test_schema_name()
        if tenant_model.objects.filter(schema_name=test_schema_name).exists():
            cls.tenant = tenant_model.objects.filter(schema_name=test_schema_name).first()
            cls.use_existing_tenant()
        else:
            cls.setup_test_tenant_and_domain()

        connection.set_tenant(cls.tenant)

    @classmethod
    def tearDownClass(cls):
        connection.set_schema_to_public()

    def _fixture_teardown(self):
        if self.flush_data():
            super(FastTenantTestCase, self)._fixture_teardown()
