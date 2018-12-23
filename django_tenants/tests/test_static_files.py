import os
import warnings

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from django.template import Engine

from django_tenants import utils
from django_tenants.files.storage import TenantFileSystemStorage
from django_tenants.files.storages import TenantFileSystemStorage as OldTenantFileSystemStorage
from django_tenants.staticfiles.finders import TenantFileSystemFinder
from django_tenants.staticfiles.storage import TenantStaticFilesStorage
from django_tenants.template.loaders.filesystem import Loader
from django_tenants.test.cases import TenantTestCase


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


class TemplateLoaderTest(TenantTestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = Engine(
            loaders=["django_tenants.template.loaders.filesystem.Loader"]
        )

        super().setUpClass()

    def setUp(self):
        super().setUp()

        root = os.path.dirname(os.path.abspath(__file__))
        settings.MULTITENANT_TEMPLATE_DIRS = [
            os.path.join(root, "tenants/%s/templates")
        ]

    def tearDown(self):
        # Reset directories
        loader = self.engine.template_loaders[0]
        loader._dirs = {}

    def test_dirs_getter(self):
        loader = self.engine.template_loaders[0]

        self.assertEqual(len(loader.dirs), 1)
        self.assertEqual(loader.dirs[0], settings.MULTITENANT_TEMPLATE_DIRS[0] % self.tenant.schema_name)

    def test_dirs_getter_improperly_configured_exception(self):
        with self.assertRaises(ImproperlyConfigured):
            del settings.MULTITENANT_TEMPLATE_DIRS
            loader = Loader(self.engine)

            loader.dirs

    def test_dirs_setter(self):
        loader = self.engine.template_loaders[0]

        loader.dirs = ["test/tenant/dir"]
        self.assertEqual(len(loader.dirs), 1)
        self.assertEqual(loader._dirs[connection.schema_name], ["test/tenant/dir"])

    def test_get_template_based_on_tenant(self):
        template = self.engine.get_template("index.html")
        TEMPLATE_DIR = settings.MULTITENANT_TEMPLATE_DIRS[0] % self.tenant.schema_name

        self.assertEqual(template.origin.name, os.path.join(TEMPLATE_DIR, "index.html"))
        self.assertEqual(template.origin.template_name, "index.html")

        # Simulate switching to antoher tenant
        connection.schema_name = "another_test"

        template = self.engine.get_template("index.html")
        TEMPLATE_DIR = settings.MULTITENANT_TEMPLATE_DIRS[0] % connection.schema_name

        self.assertEqual(template.origin.name, os.path.join(TEMPLATE_DIR, "index.html"))
        self.assertEqual(template.origin.template_name, "index.html")


class TenantFileSystemStorageTestCase(TenantTestCase):
    def setUp(self):
        super().setUp()
        settings.MEDIA_ROOT = "apps_dir/media"
        settings.MEDIA_URL = "/media/"

    def test_default(self):
        storage = TenantFileSystemStorage()

        # location
        path_suffix = "{}/{}".format(settings.MEDIA_ROOT, self.tenant.schema_name)
        self.assertEqual(storage.location[-len(path_suffix) :], path_suffix)

        # path
        path_suffix = "{}/{}/foo.txt".format(
            settings.MEDIA_ROOT, self.tenant.schema_name
        )
        self.assertEqual(storage.path("foo.txt")[-len(path_suffix) :], path_suffix)

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
        self.assertEqual(storage.location[-len(path_suffix) :], path_suffix)

        # path
        path_suffix = "{}/{}/other_dir/foo.txt".format(
            settings.MEDIA_ROOT, self.tenant.schema_name
        )
        self.assertEqual(storage.path("foo.txt")[-len(path_suffix) :], path_suffix)

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


class TenantStaticFilesStorageTestCase(TenantTestCase):
    def setUp(self):
        super().setUp()
        settings.MEDIA_ROOT = "apps_dir/media"
        settings.MEDIA_URL = "/media/"
        settings.STATIC_ROOT = "/staticfiles"
        settings.STATIC_URL = "/static/"

    def test_default(self):
        storage = TenantStaticFilesStorage()

        # location
        path_suffix = "/staticfiles/{}".format(self.tenant.schema_name)
        self.assertEqual(storage.location[-len(path_suffix) :], path_suffix)

        # path
        path_suffix = "/staticfiles/{}/foo.txt".format(self.tenant.schema_name)
        self.assertEqual(storage.path("foo.txt")[-len(path_suffix) :], path_suffix)

        # base_url
        self.assertEqual(
            storage.base_url, "/static/{}/".format(self.tenant.schema_name)
        )

        # url
        self.assertEqual(
            storage.url("foo.txt"), "/static/{}/foo.txt".format(self.tenant.schema_name)
        )

    def test_format_string(self):
        settings.MULTITENANT_RELATIVE_STATIC_ROOT = "%s/other_dir"
        storage = TenantStaticFilesStorage()

        # location
        path_suffix = "/staticfiles/{}/other_dir".format(self.tenant.schema_name)
        self.assertEqual(storage.location[-len(path_suffix) :], path_suffix)

        # path
        path_suffix = "/staticfiles/{}/other_dir/foo.txt".format(
            self.tenant.schema_name
        )
        self.assertEqual(storage.path("foo.txt")[-len(path_suffix) :], path_suffix)

        # base_url
        self.assertEqual(
            storage.base_url, "/static/{}/other_dir/".format(self.tenant.schema_name)
        )

        # url
        self.assertEqual(
            storage.url("foo.txt"),
            "/static/{}/other_dir/foo.txt".format(self.tenant.schema_name),
        )

    def test_checks_media_url_config_collision(self):
        with self.assertRaises(ImproperlyConfigured):
            settings.MEDIA_URL = "/static/{}/".format(self.tenant.schema_name)
            TenantStaticFilesStorage()

    def test_checks_media_root_config_collision(self):
        with self.assertRaises(ImproperlyConfigured):
            settings.MEDIA_ROOT = settings.STATIC_ROOT = "/media/"
            TenantStaticFilesStorage()


class TenantFileSystemFinderTestCase(TenantTestCase):
    def setUp(self):
        super().setUp()
        settings.MULTITENANT_STATICFILES_DIRS = ["tenants/%s/static"]

    def tearDown(self):
        super().tearDown()
        connection.schema_name = self.tenant.schema_name

    def test_configuration_check(self):
        settings.MULTITENANT_STATICFILES_DIRS = "tenants/%s/static"  # Not a list.
        finder = TenantFileSystemFinder()

        errors = finder.check()
        self.assertEqual(len(errors), 1)
        self.assertTrue(errors[0].is_serious())

    def test_location_getter_empty_after_init(self):
        finder = TenantFileSystemFinder()
        self.assertTrue(len(finder._locations) == 0)

    def test_location_getter_lazy_loading(self):
        finder = TenantFileSystemFinder()
        self.assertNotIn(
            self.tenant.schema_name,
            finder._locations,
            "Locations should not be initialized during construction.",
        )
        locations = finder.locations
        self.assertIn(
            self.tenant.schema_name,
            finder._locations,
            "Lazy loading of locations failed!",
        )
        self.assertEqual(locations[0][1], "tenants/test/static")

    def test_location_getter_after_connection_change(self):
        finder = TenantFileSystemFinder()
        locations = finder.locations

        connection.schema_name = "another_test"
        locations = finder.locations

        self.assertTrue(len(finder._locations) == 2)
        self.assertIn("another_test", finder._locations)
        self.assertEqual(locations[0][1], "tenants/another_test/static")

    def test_location_setter(self):
        finder = TenantFileSystemFinder()

        self.assertTrue(
            len(finder._locations) == 0,
            "Locations should not be initialized during construction",
        )
        finder.locations = "/test/path"
        self.assertEqual(finder._locations[self.tenant.schema_name], "/test/path")

    def test_storages_getter_empty_after_init(self):
        finder = TenantFileSystemFinder()
        self.assertTrue(len(finder._storages) == 0)

    def test_storages_getter_lazy_loading(self):
        finder = TenantFileSystemFinder()
        self.assertNotIn(
            self.tenant.schema_name,
            finder._storages,
            "Storages should not be initialized during construction.",
        )
        storages = finder.storages
        self.assertIn(
            self.tenant.schema_name,
            finder._storages,
            "Lazy loading of storages failed!",
        )

    def test_storages_getter_after_connection_change(self):
        finder = TenantFileSystemFinder()
        storages = finder.storages

        connection.schema_name = "another_test"
        storages = finder.storages

        self.assertTrue(len(finder._storages) == 2)
        self.assertIn("another_test", finder._storages)

    def test_storages_setter(self):
        finder = TenantFileSystemFinder()

        self.assertTrue(
            len(finder._storages) == 0,
            "Locations should not be initialized during construction",
        )
        finder.storages = "/test/path"
        self.assertEqual(finder._storages[self.tenant.schema_name], "/test/path")


class TenantFileSystemLoaderTestCase(TenantTestCase):
    @classmethod
    def setUpClass(cls):
        root = os.path.dirname(os.path.abspath(__file__))
        settings.MULTITENANT_TEMPLATE_DIRS = [
            os.path.join(root, "tenants/%s/templates")
        ]
        cls.engine = Engine(
            loaders=["django_tenants.template.loaders.filesystem.Loader"]
        )

        super().setUpClass()

    def test_get_template_sources(self):
        loader = self.engine.template_loaders[0]
        sources = list(loader.get_template_sources("foo.html"))

        self.assertEqual(len(sources), 1)
        self.assertTrue(
            sources[0].name.endswith(
                "tenants/{}/templates/foo.html".format(self.tenant.schema_name)
            )
        )


class TenantCachedLoaderTestCase(TenantTestCase):
    @classmethod
    def setUpClass(cls):
        root = os.path.dirname(os.path.abspath(__file__))
        settings.MULTITENANT_TEMPLATE_DIRS = [
            os.path.join(root, "tenants/%s/templates")
        ]

        cls.engine = Engine(
            loaders=[
                (
                    "django_tenants.template.loaders.cached.Loader",
                    ["django_tenants.template.loaders.filesystem.Loader"],
                )
            ]
        )

        super().setUpClass()

    def test_cache_key(self):
        loader = self.engine.template_loaders[0]
        self.assertEqual(
            loader.cache_key("index.html"), "index.html-{}".format(self.tenant.pk)
        )

    def test_get_template(self):
        template = self.engine.get_template("index.html")
        TEMPLATE_DIR = settings.MULTITENANT_TEMPLATE_DIRS[0] % self.tenant.schema_name

        self.assertEqual(template.origin.name, os.path.join(TEMPLATE_DIR, "index.html"))
        self.assertEqual(template.origin.template_name, "index.html")
        self.assertEqual(
            template.origin.loader, self.engine.template_loaders[0].loaders[0]
        )

        cache = self.engine.template_loaders[0].get_template_cache
        self.assertEqual(cache["index.html-{}".format(self.tenant.pk)], template)

        # Run a second time from cache
        template = self.engine.get_template("index.html")
        self.assertEqual(template.origin.name, os.path.join(TEMPLATE_DIR, "index.html"))
        self.assertEqual(template.origin.template_name, "index.html")
        self.assertEqual(
            template.origin.loader, self.engine.template_loaders[0].loaders[0]
        )
