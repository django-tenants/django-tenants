from django.core.management import call_command
from django.conf import settings
from django.db import connection
from django.test import TestCase
from django_tenants.utils import get_tenant_model, get_tenant_domain_model, get_public_schema_name


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
        tenant_domain = cls.get_test_tenant_domain()

        # ALLOWED_HOSTS is a special setting of Django setup_test_environment so we can't modify it with helpers
        if tenant_domain not in settings.ALLOWED_HOSTS:
            settings.ALLOWED_HOSTS += [tenant_domain]

    @classmethod
    def remove_allowed_test_domain(cls):
        tenant_domain = cls.get_test_tenant_domain()

        if tenant_domain in settings.ALLOWED_HOSTS:
            settings.ALLOWED_HOSTS.remove(tenant_domain)

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
    """
    A faster variant of `TenantTestCase`: the test schema and its migrations will only be created and ran once.

    WARNING: although this does produce significant improvements in speed it also means that these type of tests
             are not fully encapsulated and that some state will be shared between tests.

    See: https://github.com/tomturner/django-tenants/issues/100
    """

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
    def get_test_tenant_domain(cls):
        return 'tenant.fast-test.com'

    @classmethod
    def get_test_schema_name(cls):
        return 'fast_test'

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
        cls.add_allowed_test_domain()
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
            super()._fixture_teardown()


class SubfolderTenantTestCase(TenantTestCase):
    """Adds a public tenant to support tests against TenantSubfolderMiddleware
    """

    @classmethod
    def setUpClass(cls):
        # Set up public tenant
        cls.public_tenant = get_tenant_model()(schema_name=get_public_schema_name())
        cls.public_tenant.save()

        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.public_tenant.delete()
