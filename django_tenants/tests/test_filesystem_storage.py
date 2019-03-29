import warnings

from django.conf import settings

from django_tenants.files.storage import TenantFileSystemStorage
from django_tenants.files.storages import TenantFileSystemStorage as OldTenantFileSystemStorage
from django_tenants.test.cases import TenantTestCase


class TenantFileSystemStorageTestCase(TenantTestCase):
    def setUp(self):
        super().setUp()
        settings.MEDIA_ROOT = "apps_dir/media"
        settings.MEDIA_URL = "/media/"

    def test_default(self):
        storage = TenantFileSystemStorage()

        # location
        path_suffix = "{}/{}".format(settings.MEDIA_ROOT, self.tenant.schema_name)
        self.assertEqual(storage.location[-len(path_suffix):], path_suffix)

        # path
        path_suffix = "{}/{}/foo.txt".format(
            settings.MEDIA_ROOT, self.tenant.schema_name
        )
        self.assertEqual(storage.path("foo.txt")[-len(path_suffix):], path_suffix)

        # base_url
        self.assertEqual(storage.base_url, "/media/{}/".format(self.tenant.schema_name))

        # url
        self.assertEqual(
            storage.url("foo.txt"), "/media/{}/foo.txt".format(self.tenant.schema_name)
        )

    def test_format_string(self):
        settings.MULTITENANT_RELATIVE_MEDIA_ROOT = "%s/other_dir"
        storage = TenantFileSystemStorage()

        # location
        path_suffix = "{}/{}/other_dir".format(
            settings.MEDIA_ROOT, self.tenant.schema_name
        )
        self.assertEqual(storage.location[-len(path_suffix):], path_suffix)

        # path
        path_suffix = "{}/{}/other_dir/foo.txt".format(
            settings.MEDIA_ROOT, self.tenant.schema_name
        )
        self.assertEqual(storage.path("foo.txt")[-len(path_suffix):], path_suffix)

        # base_url
        self.assertEqual(
            storage.base_url, "/media/{}/other_dir/".format(self.tenant.schema_name)
        )

        # url
        self.assertEqual(
            storage.url("foo.txt"),
            "/media/{}/other_dir/foo.txt".format(self.tenant.schema_name),
        )

    def test_deprecated_module_raises_warning(self):
        with warnings.catch_warnings(record=True) as warns:
            deprecation_warning = "TenantFileSystemStorage has been moved from django_tenants.files.storages " \
                                  "to django_tenants.files.storage."

            OldTenantFileSystemStorage()
            self.assertTrue(any(deprecation_warning in str(w.message) for w in warns))
