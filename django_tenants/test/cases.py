from django.core.management import call_command
from django.conf import settings
from django.db import connection
from django.test import TestCase

from django_tenants.utils import get_tenant_model, get_tenant_domain_model, get_public_schema_name

ALLOWED_TEST_DOMAIN = '.test.com'


class TenantTestCase(TestCase):

    @staticmethod
    def add_allowed_test_domain():
        # ALLOWED_HOSTS is a special setting of Django setup_test_environment so we can't modify it with helpers
        if ALLOWED_TEST_DOMAIN not in settings.ALLOWED_HOSTS:
            settings.ALLOWED_HOSTS += [ALLOWED_TEST_DOMAIN]

    @staticmethod
    def remove_allowed_test_domain():
        if ALLOWED_TEST_DOMAIN in settings.ALLOWED_HOSTS:
            settings.ALLOWED_HOSTS.remove(ALLOWED_TEST_DOMAIN)

    # noinspection PyMethodMayBeStatic
    def setup_tenant(self, tenant):
        """
        Add any additional setting to the tenant before it get saved. This is required if you have
        required fields.
        :param tenant:
        :return:
        """
        pass

    # noinspection PyMethodMayBeStatic
    def setup_domain(self, domain):
        """
        Add any additional setting to the domain before it get saved. This is required if you have
        required fields.
        :param domain:
        :return:
        """
        pass

    def setUpClass(self):
        self.sync_shared()
        self.add_allowed_test_domain()
        self.tenant = get_tenant_model()(schema_name=self.get_test_schema_name())
        self.setup_tenant(self.tenant)
        self.tenant.save(verbosity=0)  # todo: is there any way to get the verbosity from the test command here?

        # Set up domain
        tenant_domain = self.get_test_tenant_domain()
        self.domain = get_tenant_domain_model()(tenant=self.tenant, domain=tenant_domain)
        self.setup_domain(self.domain)
        self.domain.save()

        connection.set_tenant(self.tenant)

    def tearDownClass(self):
        connection.set_schema_to_public()
        self.remove_allowed_test_domain()
        cursor = connection.cursor()
        cursor.execute('DROP SCHEMA IF EXISTS %s CASCADE' % self.get_test_schema_name())

    @staticmethod
    def sync_shared():
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

    def setUpClass(self):
        self.sync_shared()
        self.add_allowed_test_domain()
        tenant_model = get_tenant_model()

        test_schema_name = self.get_test_schema_name()
        test_tenant_domain_name = self.get_test_tenant_domain()

        if tenant_model.objects.filter(schema_name=test_schema_name).exists():
            self.tenant = tenant_model.objects.filter(schema_name=test_schema_name).first()
        else:
            self.tenant = tenant_model(schema_name=test_schema_name)
            self.tenant.save(verbosity=0)
            self.domain = get_tenant_domain_model()(tenant=self.tenant, domain=test_tenant_domain_name)
            self.domain.save()

        connection.set_tenant(self.tenant)

    def tearDownClass(self):
        connection.set_schema_to_public()
        self.remove_allowed_test_domain()

    def tearDown(self):
        """
        We need to prevent these from being called in TenantTestCase, or it will
        double the schema logic calls, and cause integrity errors, because they
        work on instances, and with FastTenantTestCase our logic happens in the
        class level functions above.
        :return:
        """
        pass

    def setUp(self):
        """
        We need to prevent these from being called in TenantTestCase, or it will
        double the schema logic calls, and cause integrity errors, because they
        work on instances, and with FastTenantTestCase our logic happens in the
        class level functions above.
        :return:
        """
        pass
