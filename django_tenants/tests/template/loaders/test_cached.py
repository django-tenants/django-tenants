import os

from django.conf import settings
from django.template import Engine

from django_tenants.test.cases import TenantTestCase


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
