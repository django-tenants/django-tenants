from django.db import models
from django_tenants.models import TenantMixin, DomainMixin


class Client(TenantMixin):
    name = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(max_length=200, blank=True, null=True)
    created_on = models.DateField(auto_now_add=True)


class Domain(DomainMixin):
    pass
