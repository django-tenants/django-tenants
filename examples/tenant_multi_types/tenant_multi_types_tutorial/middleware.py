from django.http import Http404

from django_tenants.middleware import TenantMainMiddleware
from django_tenants.utils import remove_www_and_dev, get_public_schema_urlconf


class TenantTutorialMiddleware(TenantMainMiddleware):

    def no_tenant_found(self, request, hostname):
        hostname_without_port = remove_www_and_dev(request.get_host().split(':')[0])
        if hostname_without_port in ("127.0.0.1", "localhost"):
            request.urlconf = get_public_schema_urlconf()
            return
        else:
            raise Http404
