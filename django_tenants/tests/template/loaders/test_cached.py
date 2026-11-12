import os
import shutil
import tempfile

from django.conf import settings
from django.db import connection
from django.template import Context, Engine
from django.test.utils import override_settings

from django_tenants.test.cases import TenantTestCase
from django_tenants.tests.testcases import BaseTestCase
from django_tenants.utils import get_tenant_domain_model, get_tenant_model, schema_context


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
            loader.cache_key("index.html"), "{}/index.html".format(self.tenant.schema_name)
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
        self.assertEqual(cache["{}/index.html".format(self.tenant.schema_name)], template)

        # Run a second time from cache
        template = self.engine.get_template("index.html")
        self.assertEqual(template.origin.name, os.path.join(TEMPLATE_DIR, "index.html"))
        self.assertEqual(template.origin.template_name, "index.html")
        self.assertEqual(
            template.origin.loader, self.engine.template_loaders[0].loaders[0]
        )


class TenantCachedLoaderIsolationTestCase(BaseTestCase):
    """Two tenants must never share a cached template entry."""

    def _make_tenant(self, schema_name, domain):
        connection.set_schema_to_public()
        tenant = get_tenant_model()(schema_name=schema_name)
        tenant.save()
        get_tenant_domain_model()(tenant=tenant, domain=domain).save()
        return tenant

    def _drop_tenant(self, tenant):
        connection.set_schema_to_public()
        tenant.domains.all().delete()
        tenant.delete(force_drop=True)

    def test_hyphenated_schema_name_does_not_share_cache_entry(self):
        # With '-' as the separator, tenant 'acme-base' rendering 'x.html' and
        # tenant 'acme' rendering 'base-x.html' both used the key
        # 'acme-base-x.html', so 'acme' was served 'acme-base's template.
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root)
        for schema_name, template_name, content in (('acme', 'base-x.html', 'acme template'),
                                                     ('acme-base', 'x.html', 'acme-base template')):
            os.makedirs(os.path.join(root, schema_name))
            with open(os.path.join(root, schema_name, template_name), 'w') as f:
                f.write(content)

        acme = self._make_tenant('acme', 'acme.test.com')
        self.addCleanup(self._drop_tenant, acme)
        acme_base = self._make_tenant('acme-base', 'acme-base.test.com')
        self.addCleanup(self._drop_tenant, acme_base)

        with override_settings(MULTITENANT_TEMPLATE_DIRS=[os.path.join(root, '%s')]):
            engine = Engine(loaders=[('django_tenants.template.loaders.cached.Loader',
                                      ['django_tenants.template.loaders.filesystem.Loader'])])
            connection.set_tenant(acme_base)
            self.assertEqual(engine.get_template('x.html').render(Context()), 'acme-base template')
            connection.set_tenant(acme)
            self.assertEqual(engine.get_template('base-x.html').render(Context()), 'acme template')

    def test_tenant_does_not_share_cache_entry_with_schema_context(self):
        # FakeTenant contexts (schema_context(), the public schema, commands)
        # must be prefixed too: unprefixed, tenant 'admin' + 'login.html' and a
        # FakeTenant rendering 'admin/login.html' shared one entry.
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root)
        os.makedirs(os.path.join(root, 'admin'))
        os.makedirs(os.path.join(root, 'other', 'admin'))
        with open(os.path.join(root, 'admin', 'login.html'), 'w') as f:
            f.write('tenant admin template')
        with open(os.path.join(root, 'other', 'admin', 'login.html'), 'w') as f:
            f.write('other schema template')

        admin = self._make_tenant('admin', 'admin.test.com')
        self.addCleanup(self._drop_tenant, admin)

        with override_settings(MULTITENANT_TEMPLATE_DIRS=[os.path.join(root, '%s')]):
            engine = Engine(loaders=[('django_tenants.template.loaders.cached.Loader',
                                      ['django_tenants.template.loaders.filesystem.Loader'])])
            with schema_context('other'):
                self.assertEqual(engine.get_template('admin/login.html').render(Context()),
                                 'other schema template')
            connection.set_tenant(admin)
            self.assertEqual(engine.get_template('login.html').render(Context()), 'tenant admin template')
