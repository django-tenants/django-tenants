import re
import sys

from django.db import connection
from django.conf import settings
from django.urls import URLResolver, reverse as reverse_default
from django.utils.functional import lazy
from django_tenants.utils import (
    get_tenant_domain_model,
    get_subfolder_prefix,
    clean_tenant_url, has_multi_type_tenants, get_tenant_types,
)


def reverse(viewname, urlconf=None, args=None, kwargs=None, current_app=None):
    url = reverse_default(viewname, urlconf, args, kwargs, current_app=current_app)
    return clean_tenant_url(url)


reverse_lazy = lazy(reverse, str)


class TenantPrefixPattern:
    converters = {}

    @property
    def tenant_prefix(self):
        _DomainModel = get_tenant_domain_model()
        subfolder_prefix = get_subfolder_prefix()
        try:
            domain = _DomainModel.objects.get(
                tenant__schema_name=connection.schema_name,
                domain=connection.tenant.domain_subfolder,
            )
            return (
                "{}/{}/".format(subfolder_prefix, domain.domain)
                if subfolder_prefix
                else "{}/".format(domain.domain)
            )
        except _DomainModel.DoesNotExist:
            return "/"

    @property
    def regex(self):
        # This is only used by reverse() and cached in _reverse_dict.
        # Note: This caching must actually be bypassed elsewhere in order to effectively switch tenants.
        return re.compile(self.tenant_prefix)

    def match(self, path):
        tenant_prefix = self.tenant_prefix
        if path.startswith(tenant_prefix):
            return path[len(tenant_prefix):], (), {}
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


def get_dynamic_tenant_prefixed_urlconf(urlconf, dynamic_path):
    """
    Generates a new URLConf module with all patterns prefixed with tenant.
    """
    from types import ModuleType
    from django.utils.module_loading import import_string

    class LazyURLConfModule(ModuleType):
        def __getattr__(self, attr):
            imported = import_string("{}.{}".format(urlconf, attr))
            if attr == "urlpatterns":
                return tenant_patterns(*imported)
            return imported

    return LazyURLConfModule(dynamic_path)


def get_subfolder_urlconf(tenant):
    """
    Creates and returns a subfolder URLConf for tenant.
    """
    if has_multi_type_tenants():
        urlconf = get_tenant_types()[tenant.get_tenant_type()]['URLCONF']
    else:
        urlconf = settings.ROOT_URLCONF
    dynamic_path = urlconf + "_dynamically_tenant_prefixed"
    if not sys.modules.get(dynamic_path):
        sys.modules[dynamic_path] = get_dynamic_tenant_prefixed_urlconf(urlconf, dynamic_path)
    return dynamic_path
