from django.test import RequestFactory, Client
from django.http import HttpRequest
from django.contrib.auth import authenticate

from django_tenants.utils import remove_www


class BaseTenantRequestFactory:
    def __init__(self, tenant, **defaults):
        super().__init__(**defaults)
        self.tenant = tenant

    def generic(self, *args, **kwargs):
        if "HTTP_HOST" not in kwargs:
            kwargs["HTTP_HOST"] = self.tenant.get_primary_domain().domain
        return super().generic(*args, **kwargs)


class TenantRequestFactory(BaseTenantRequestFactory, RequestFactory):

    def generic(self, *args, **kwargs):
        request = super().generic(*args, **kwargs)
        # Set what TenantMainMiddleware would, without looking the domain up:
        # the request carries the factory's tenant, and its domain_url is the
        # host the request was made to.
        self.tenant.domain_url = remove_www(request.META['HTTP_HOST'].split(':')[0])
        request.tenant = self.tenant
        return request


class TenantClient(BaseTenantRequestFactory, Client):
    def login(self, **credentials):
        # Create a dummy HttpRequest object and add HTTP_HOST

        request = HttpRequest()
        request.META['HTTP_HOST'] = self.tenant.get_primary_domain().domain
        request.tenant = self.tenant
        
        # Authenticate using django contrib's authenticate which passes the request on 
        # to custom backends

        user = authenticate(request, **credentials)
        if user:
            super(TenantClient, self)._login(user)
            return True
        else:
            return False
