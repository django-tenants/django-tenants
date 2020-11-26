import sys
from importlib import import_module

from django.conf import settings
from django.urls import reverse

from django_tenants.tests.testcases import BaseTestCase
from django_tenants.urlresolvers import TenantPrefixPattern, get_subfolder_urlconf
from django_tenants.utils import get_tenant_model, get_tenant_domain_model


class URLResolversTestCase(BaseTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        settings.SHARED_APPS = ("django_tenants", "customers")
        settings.TENANT_APPS = (
            "dts_test_app",
            "django.contrib.contenttypes",
            "django.contrib.auth",
        )
        settings.INSTALLED_APPS = settings.SHARED_APPS + settings.TENANT_APPS
        settings.TENANT_SUBFOLDER_PREFIX = "clients/"
        cls.available_apps = settings.INSTALLED_APPS

        def reverser_func(self, name, tenant):
            """
            Reverses `name` in the urlconf returned from `tenant`.
            """

            urlconf_path = get_subfolder_urlconf(tenant)
            urlconf = import_module(urlconf_path)
            reverse_response = reverse(name, urlconf=urlconf)
            del sys.modules[urlconf_path]  # required to simulate new thread next time
            return reverse_response

        cls.reverser = reverser_func
        # This comes from dts_test_project/dts_test_project/urls.py
        cls.paths = {"public": "/public/", "private": "/private/"}

    def setUp(self):
        self.sync_shared()
        super().setUp()
        for i in range(1, 4):
            schema_name = "tenant{}".format(i)
            tenant = get_tenant_model()(schema_name=schema_name)
            tenant.save(verbosity=0)
            domain = get_tenant_domain_model()(tenant=tenant, domain=schema_name)
            domain.save()

    def tearDown(self):
        from django.db import connection

        connection.set_schema_to_public()
        for domain in get_tenant_domain_model().objects.all():
            domain.delete()
        for tenant in get_tenant_model().objects.all():
            tenant.delete(force_drop=True)
        super().tearDown()

    def test_tenant_prefix(self):
        from django.db import connection

        tpp = TenantPrefixPattern()
        for tenant in get_tenant_model().objects.all():
            domain = tenant.domains.first()
            tenant.domain_subfolder = domain.domain  # Normally done by middleware
            connection.set_tenant(tenant)
            self.assertEqual(
                tpp.tenant_prefix, "clients/{}/".format(tenant.domain_subfolder)
            )

    def test_prefixed_reverse(self):
        from django.db import connection

        for tenant in get_tenant_model().objects.all():
            domain = tenant.domains.first()
            tenant.domain_subfolder = domain.domain  # Normally done by middleware
            connection.set_tenant(tenant)
            for name, path in self.paths.items():
                self.assertEqual(
                    self.reverser(name, tenant),
                    "/clients/{}{}".format(domain.domain, path),
                )
