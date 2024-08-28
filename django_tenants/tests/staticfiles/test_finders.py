import os

from django.conf import settings
from django.db import connection

from django_tenants.staticfiles import finders
from django_tenants.test.cases import TenantTestCase


class TenantFileSystemFinderTestCase(TenantTestCase):
    """
    Based on Django's TestFileSystemFinder.

    On Windows, sometimes the case of the path we ask the finders for and the
    path(s) they find can differ. Compare them using os.path.normcase() to
    avoid false negatives.

    """

    def setUp(self):
        super().setUp()
        self.test_app_root = settings.TENANT_APPS_DIR

        self.finder = finders.TenantFileSystemFinder()

        self.source_path = os.path.join("css", "project.css")
        self.test_file_path = os.path.join(
            self.test_app_root,
            "tenants",
            connection.schema_name,
            "static",
            "css",
            "project.css",
        )

    def tearDown(self):
        super().tearDown()
        connection.schema_name = self.tenant.schema_name

    def test_location_getter_empty_after_init(self):
        self.assertTrue(len(self.finder._locations) == 0)

    def test_location_getter_lazy_loading(self):
        self.assertNotIn(
            self.tenant.schema_name,
            self.finder._locations,
            "Locations should not be initialized during construction.",
        )
        locations = self.finder.locations
        self.assertIn(
            self.tenant.schema_name,
            self.finder._locations,
            "Lazy loading of locations failed!",
        )
        self.assertTrue(locations[0][1].endswith(f"tenants/{self.tenant.schema_name}/static"))

    def test_location_getter_after_connection_change(self):
        locations = self.finder.locations

        self.assertTrue(len(self.finder._locations) == 1)
        self.assertIn(self.tenant.schema_name, self.finder._locations)
        self.assertTrue(locations[0][1].endswith(f"tenants/{self.tenant.schema_name}/static"))

        connection.schema_name = "other"
        locations = self.finder.locations

        self.assertTrue(len(self.finder._locations) == 2)
        self.assertIn("other", self.finder._locations)
        self.assertTrue(locations[0][1].endswith("tenants/other/static"))

    def test_location_setter(self):
        self.assertTrue(
            len(self.finder._locations) == 0,
            "Locations should not be initialized during construction",
        )
        self.finder.locations = "/test/path"
        self.assertEqual(self.finder._locations[self.tenant.schema_name], "/test/path")

    def test_storages_getter_empty_after_init(self):
        self.assertTrue(len(self.finder._storages) == 0)

    def test_storages_getter_lazy_loading(self):
        self.assertNotIn(
            self.tenant.schema_name,
            self.finder._storages,
            "Storages should not be initialized during construction.",
        )
        self.finder.storages  # noqa Lazy load storages

        self.assertIn(
            self.tenant.schema_name,
            self.finder._storages,
            "Lazy loading of storages failed!",
        )

    def test_storages_getter_after_connection_change(self):
        self.finder.storages  # noqa Lazy load storages

        connection.schema_name = "other"
        self.finder.storages  # noqa Lazy load storages

        self.assertTrue(len(self.finder._storages) == 2)
        self.assertIn("other", self.finder._storages)

    def test_storages_setter(self):

        self.assertTrue(
            len(self.finder._storages) == 0,
            "Locations should not be initialized during construction",
        )
        self.finder.storages = "/test/path"
        self.assertEqual(self.finder._storages[self.tenant.schema_name], "/test/path")

    def test_configuration_check(self):
        old_settings = settings.MULTITENANT_STATICFILES_DIRS

        settings.MULTITENANT_STATICFILES_DIRS = "tenants/%s/static"  # Not a list.

        errors = self.finder.check()
        self.assertEqual(len(errors), 1)
        self.assertTrue(errors[0].is_serious())

        settings.MULTITENANT_STATICFILES_DIRS = old_settings

    def test_find_first(self):
        found = self.finder.find(self.source_path)

        self.assertEqual(os.path.normcase(found), os.path.normcase(self.test_file_path))

    def test_find_all(self):
        found = self.finder.find(self.source_path, all=True)
        found = [os.path.normcase(f) for f in found]

        self.assertEqual(found, [os.path.normcase(self.test_file_path)])

    def test_find_does_not_traverse_global_path(self):
        source_path = os.path.join("css", "global.css")
        found = self.finder.find(source_path)

        self.assertEqual(found, [])
