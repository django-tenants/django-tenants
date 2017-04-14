from django.core.management import call_command
from django.conf import settings
from django.db import connection
from django.test import TestCase

from django_tenants.utils import get_tenant_model, get_tenant_domain_model, get_public_schema_name

ALLOWED_TEST_DOMAIN = '.test.com'


class TenantTestCase(TestCase):

    @classmethod
    def add_allowed_test_domain(cls):
        # ALLOWED_HOSTS is a special setting of Django setup_test_environment so we can't modify it with helpers
        if ALLOWED_TEST_DOMAIN not in settings.ALLOWED_HOSTS:
            settings.ALLOWED_HOSTS += [ALLOWED_TEST_DOMAIN]

    @classmethod
    def remove_allowed_test_domain(cls):
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

    @classmethod
    def setUpClass(cls):
        cls.sync_shared()
        cls.add_allowed_test_domain()
        cls.tenant = get_tenant_model()(schema_name=cls.get_test_schema_name())
        connection.setup_tenant(cls.tenant)
        cls.tenant.save(verbosity=0)  # todo: is there any way to get the verbosity from the test command here?

        # Set up domain
        tenant_domain = cls.get_test_tenant_domain()
        cls.domain = get_tenant_domain_model()(tenant=cls.tenant, domain=tenant_domain)
        connection.setup_domain(cls.domain)
        cls.domain.save()

        connection.set_tenant(cls.tenant)

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

    @classmethod
    def setUpClass(cls):
        cls.sync_shared()
        cls.add_allowed_test_domain()
        tenant_model = get_tenant_model()

        test_schema_name = cls.get_test_schema_name()
        test_tenant_domain_name = cls.get_test_tenant_domain()

        if tenant_model.objects.filter(schema_name=test_schema_name).exists():
            cls.tenant = tenant_model.objects.filter(schema_name=test_schema_name).first()
        else:
            cls.tenant = tenant_model(schema_name=test_schema_name)
            cls.tenant.save(verbosity=0)

            cls.domain = get_tenant_domain_model()(tenant=cls.tenant, domain=test_tenant_domain_name)
            connection.setup_domain(cls.domain)
            cls.domain.save()

        connection.set_tenant(cls.tenant)

    @classmethod
    def tearDownClass(cls):
        connection.set_schema_to_public()
        cls.remove_allowed_test_domain()

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
