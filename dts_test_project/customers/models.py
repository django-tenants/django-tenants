from django.db import models
from django_tenants.models import TenantMixin, DomainMixin


class Client(TenantMixin):
    name = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(max_length=200, blank=True, null=True)
    created_on = models.DateField(auto_now_add=True)
    type = models.CharField(max_length=100, default='type1')

    def reverse(self, request, view_name):
        """
        If you have a different implementation of reverse from what the
        Django-Tenants library uses (A.k.a. Sites Framework) then you can write
        your own override here.
        """
        # Write your own custom code else use existing code.
        return super().reverse(request, view_name)


class Domain(DomainMixin):
    pass
