import os

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from django.template import Engine

from django_tenants.template.loaders.filesystem import Loader
from django_tenants.test.cases import TenantTestCase


class TemplateLoaderTest(TenantTestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = Engine(
            loaders=["django_tenants.template.loaders.filesystem.Loader"]
        )

        super().setUpClass()

    def setUp(self):
        super().setUp()

        test_app_root = settings.TENANT_APPS_DIR
        settings.MULTITENANT_TEMPLATE_DIRS = [
            os.path.join(test_app_root, "tenants/%s/templates")
        ]

    def tearDown(self):
        # Reset directories
        loader = self.engine.template_loaders[0]
        loader._dirs = {}

    def test_dirs_getter(self):
        loader = self.engine.template_loaders[0]

        self.assertEqual(len(loader.dirs), 1)
        self.assertEqual(
            loader.dirs[0],
            settings.MULTITENANT_TEMPLATE_DIRS[0] % self.tenant.schema_name,
        )

    def test_dirs_getter_improperly_configured_exception(self):
        with self.assertRaises(ImproperlyConfigured):
            del settings.MULTITENANT_TEMPLATE_DIRS
            loader = Loader(self.engine)

            loader.dirs  # noqa Trigger dirs getter

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

        # Simulate switching to another tenant
        connection.schema_name = "other"

        template = self.engine.get_template("index.html")
        TEMPLATE_DIR = settings.MULTITENANT_TEMPLATE_DIRS[0] % connection.schema_name

        self.assertEqual(template.origin.name, os.path.join(TEMPLATE_DIR, "index.html"))
        self.assertEqual(template.origin.template_name, "index.html")


class TenantFileSystemLoaderTestCase(TenantTestCase):
    @classmethod
    def setUpClass(cls):
        test_app_root = settings.TENANT_APPS_DIR
        settings.MULTITENANT_TEMPLATE_DIRS = [
            os.path.join(test_app_root, "tenants/%s/templates")
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
        test_app_root = settings.TENANT_APPS_DIR
        settings.MULTITENANT_TEMPLATE_DIRS = [
            os.path.join(test_app_root, "tenants/%s/templates")
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
