from django.core.urlresolvers import reverse as reverse_default
from django.utils.functional import lazy
from django_tenants.utils import clean_tenant_url


def reverse(viewname, urlconf=None, args=None, kwargs=None, prefix=None,
            current_app=None):
    url = reverse_default(viewname, urlconf, args, kwargs, prefix, current_app)
    return clean_tenant_url(url)

reverse_lazy = lazy(reverse, str)
