from django.test import RequestFactory

from django_tenants import utils
from django_tenants.middleware import TenantMainMiddleware
from django_tenants.test.cases import TenantTestCase
from django.core.management.commands.migrate import Command as MigrateCommand
from django.test.utils import override_settings

from django_tenants.utils import get_tenant


class CustomMigrateCommand(MigrateCommand):
    pass


class ConfigStringParsingTestCase(TenantTestCase):
    def test_static_string(self):
        self.assertEqual(
            utils.parse_tenant_config_path("foo"),
            "foo/{}".format(self.tenant.schema_name),
        )

    def test_format_string(self):
        self.assertEqual(
            utils.parse_tenant_config_path("foo/%s/bar"),
            "foo/{}/bar".format(self.tenant.schema_name),
        )

        # Preserve trailing slash
        self.assertEqual(
            utils.parse_tenant_config_path("foo/%s/bar/"),
            "foo/{}/bar/".format(self.tenant.schema_name),
        )

    def test_get_tenant_base_migrate_command_class_default(self):
        self.assertEqual(
            utils.get_tenant_base_migrate_command_class(),
            MigrateCommand,
        )

    def test_get_tenant_base_migrate_command_class_custom(self):
        command_path = 'django_tenants.tests.test_utils.CustomMigrateCommand'
        with override_settings(TENANT_BASE_MIGRATE_COMMAND=command_path):
            self.assertEqual(
                utils.get_tenant_base_migrate_command_class(),
                CustomMigrateCommand,
            )

    def test_get_tenant(self):
        tenant_domain = 'tenant.test.com'
        factory = RequestFactory()
        tm = TenantMainMiddleware(lambda r: r)
        request = factory.get('/any/request/', HTTP_HOST=tenant_domain)
        tm.process_request(request)
        self.assertEqual(get_tenant(request).schema_name, 'test')
