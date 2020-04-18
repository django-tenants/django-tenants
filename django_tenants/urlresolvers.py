import re
import sys

from django_tenants.utils import clean_tenant_url
from django.conf import settings
from django.db import connection
from django.urls import reverse as reverse_default
from django.urls import URLResolver
from django.utils.functional import lazy
from django.utils.module_loading import import_string
from importlib.util import find_spec, module_from_spec

from .utils import get_tenant_model
from .postgresql_backend.base import SQL_IDENTIFIER


def reverse(viewname, urlconf=None, args=None, kwargs=None, current_app=None):
    url = reverse_default(viewname, urlconf, args, kwargs, current_app=current_app)
    return clean_tenant_url(url)


reverse_lazy = lazy(reverse, str)


SUBFOLDER_PREFIX = getattr(settings, "SUBFOLDER_PREFIX", "..")
subfolder_matcher = re.compile(
    r"^/" + SUBFOLDER_PREFIX + r"/(?P<schema_name>" + SQL_IDENTIFIER[1:-1] + r")/"
)


class TenantPrefixPattern:
    converters = {}

    @property
    def tenant_prefix(self):
        TenantModel = get_tenant_model()
        try:
            tenant = TenantModel.objects.get(schema_name=connection.schema_name)
            return "{}/{}/".format(SUBFOLDER_PREFIX, tenant.schema_name)
        except TenantModel.DoesNotExist:
            return "/"

    @property
    def regex(self):
        # This is only used by reverse() and cached in _reverse_dict.
        return re.compile(self.tenant_prefix)

    def match(self, path):
        tenant_prefix = self.tenant_prefix
        if path.startswith(tenant_prefix):
            return path[len(tenant_prefix) :], (), {}
        return None

    def check(self):
        return []

    def describe(self):
        return "'{}'".format(self)

    def __str__(self):
        return self.tenant_prefix


def tenant_patterns(*urls):
    """
    Add the tenant prefix to every URL pattern within this function.
    This may only be used in the root URLconf, not in an included URLconf.
    """
    return [URLResolver(TenantPrefixPattern(), list(urls))]


def subfolder_dynamic_urlconf(tenant):
    urlconf = settings.ROOT_URLCONF + "_dynamically_tenant_prefixed"
    if not sys.modules.get(urlconf):
        spec = find_spec(settings.ROOT_URLCONF)
        prefixed_url_module = module_from_spec(spec)
        spec.loader.exec_module(prefixed_url_module)
        prefixed_url_module.urlpatterns = tenant_patterns(
            *import_string(settings.ROOT_URLCONF + ".urlpatterns")
        )
        sys.modules[urlconf] = prefixed_url_module
        del spec
    return urlconf
