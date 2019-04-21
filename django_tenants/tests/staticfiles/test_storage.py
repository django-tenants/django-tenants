from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from django_tenants.staticfiles.storage import TenantStaticFilesStorage
from django_tenants.test.cases import TenantTestCase


class TenantStaticFilesStorageTestCase(TenantTestCase):
    def setUp(self):
        super().setUp()
        settings.STATIC_ROOT = "/staticfiles"
        settings.STATIC_URL = "/static/"
        settings.MULTITENANT_RELATIVE_STATIC_ROOT = "%s/other_dir"

        self.storage = TenantStaticFilesStorage()

    def test_relative_static_root_raises_exception_if_no_static_root_configured(self):
        with self.assertRaises(ImproperlyConfigured):
            del settings.STATIC_ROOT

            self.storage.relative_static_root  # noqa Lookup static root

    def test_base_location(self):
        self.assertEqual(
            self.storage.base_location,
            "{}/{}/other_dir".format(settings.STATIC_ROOT, self.tenant.schema_name),
        )

    def test_base_location_defaults_to_appending_tenant_to_static_root(self):
        del settings.MULTITENANT_RELATIVE_STATIC_ROOT

        self.assertEqual(
            self.storage.base_location,
            "{}/{}".format(settings.STATIC_ROOT, self.tenant.schema_name),
        )

    def test_base_url_uses_static_url(self):
        self.assertEqual(self.storage.base_url, "/static/")

    def test_base_url_defaults_to_static_url(self):
        del settings.MULTITENANT_RELATIVE_STATIC_ROOT

        self.assertEqual(self.storage.base_url, "/static/")

    def test_path_raises_exception_if_no_static_root_configured(self):
        with self.assertRaises(ImproperlyConfigured):
            del settings.STATIC_ROOT

            self.storage.path("test")
