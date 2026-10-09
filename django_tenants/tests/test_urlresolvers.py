from asgiref.sync import async_to_sync
from django.conf import settings
from django.db import connection
from django.http import HttpResponse, HttpResponseNotFound
from django.test import AsyncClient, Client, override_settings
from django.urls import path, reverse

from django_tenants.tests.testcases import BaseTestCase
from django_tenants.urlresolvers import get_subfolder_urlconf

from django_tenants.utils import get_tenant_model, get_tenant_domain_model


def whoami(request):
    return HttpResponse("{} {}".format(connection.schema_name, reverse("whoami")))


def custom_404(request, exception):
    return HttpResponseNotFound("custom 404")


# The root URLConf for the request tests below.
urlpatterns = [path("whoami/", whoami, name="whoami")]
handler404 = custom_404


class SubfolderTenantsTestCase(BaseTestCase):
    """
    Three tenants, each with a domain used as its subfolder.
    """

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
            urlconf = get_subfolder_urlconf(tenant)
            reverse_response = reverse(name, urlconf=urlconf)
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



class URLResolversTestCase(SubfolderTenantsTestCase):
    def test_tenant_prefix(self):
        from django.db import connection

        for tenant in get_tenant_model().objects.all():
            domain = tenant.domains.first()
            tenant.domain_subfolder = domain.domain  # Normally done by middleware
            connection.set_tenant(tenant)
            subfolder_url_conf = get_subfolder_urlconf(tenant)
            url_resolver = subfolder_url_conf.urlpatterns[0]
            self.assertEqual(
                url_resolver.pattern.describe(),
                "'clients/{}/'".format(tenant.domain_subfolder),
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

    def test_reverse_without_a_subfolder_tenant(self):
        """
        schema_context() and set_schema_to_public() leave a FakeTenant, which has
        no domain_subfolder. Creating a tenant from a subfolder request does that,
        and the next reverse() raised AttributeError. The prefix no longer comes
        from the connection. #1005
        """
        from django_tenants.utils import schema_context

        tenant = get_tenant_model().objects.get(schema_name="tenant1")
        tenant.domain_subfolder = "tenant1"  # Normally done by middleware
        with schema_context("tenant2"):
            self.assertEqual(self.reverser("public", tenant), "/clients/tenant1/public/")
        connection.set_schema_to_public()
        self.assertEqual(self.reverser("public", tenant), "/clients/tenant1/public/")

@override_settings(
    ROOT_URLCONF=__name__,
    MIDDLEWARE=["django_tenants.middleware.subfolder.TenantSubfolderMiddleware"],
)
class SubfolderRequestTestCase(SubfolderTenantsTestCase):
    """
    Requests through TenantSubfolderMiddleware, which builds the URLConf.
    """

    def test_asgi_request_resolves_under_its_tenant(self):
        """
        Under ASGI the URL is resolved on the event loop, not the thread the
        middleware set the tenant on, so a prefix read from the connection was
        lost. #820
        """
        async_client = AsyncClient()

        async def fetch(subfolder):
            return await async_client.get("/clients/{}/whoami/".format(subfolder))

        for subfolder in ("tenant1", "tenant2", "tenant1"):
            response = async_to_sync(fetch)(subfolder)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.content.decode(), "{0} /clients/{0}/whoami/".format(subfolder))

    def test_root_urlconf_error_handlers_are_used(self):
        response = Client().get("/clients/tenant1/missing/")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.content.decode(), "custom 404")
