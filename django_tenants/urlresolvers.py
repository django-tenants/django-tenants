from types import ModuleType

from django.conf import settings
from django.urls import reverse as reverse_default, path, include
from django.utils.functional import lazy
from django_tenants.utils import (
    get_subfolder_prefix,
    clean_tenant_url,
    has_multi_type_tenants,
    get_tenant_types,
)


def reverse(viewname, urlconf=None, args=None, kwargs=None, current_app=None):
    url = reverse_default(viewname, urlconf, args, kwargs, current_app=current_app)
    return clean_tenant_url(url)


reverse_lazy = lazy(reverse, str)


def get_subfolder_urlconf(tenant):
    if has_multi_type_tenants():
        urlconf = get_tenant_types()[tenant.get_tenant_type()]["URLCONF"]
    else:
        urlconf = settings.ROOT_URLCONF

    subfolder_prefix = get_subfolder_prefix()

    class TenantUrlConf(ModuleType):
        urlpatterns = [
            path(
                f"{subfolder_prefix}/{tenant.domain_subfolder}/",
                include(urlconf),
            )
        ]

    return TenantUrlConf(tenant.domain_subfolder)
