from importlib import import_module
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
    """
    Returns a URLConf module for tenant, with every pattern of the root URLConf
    under the tenant's subfolder.

    The prefix is fixed in the module rather than read from the connection when
    a URL is resolved, so it holds wherever resolving happens: under ASGI that
    is not the thread the middleware set the tenant on. #820
    """
    if has_multi_type_tenants():
        urlconf = get_tenant_types()[tenant.get_tenant_type()]["URLCONF"]
    else:
        urlconf = settings.ROOT_URLCONF
    root_urlconf = import_module(urlconf)

    subfolder_prefix = get_subfolder_prefix()
    prefix = "{}/{}/".format(subfolder_prefix, tenant.domain_subfolder) if subfolder_prefix \
        else "{}/".format(tenant.domain_subfolder)

    class TenantUrlConf(ModuleType):
        urlpatterns = [path(prefix, include(root_urlconf.urlpatterns))]

        def __getattr__(self, attr):
            # handler400, handler403, handler404 and handler500 come from the root URLConf.
            return getattr(root_urlconf, attr)

    return TenantUrlConf(urlconf + "_tenant_" + tenant.domain_subfolder)
