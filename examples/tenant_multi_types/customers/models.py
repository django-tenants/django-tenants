from django.db import models
from django_tenants.models import TenantMixin, DomainMixin
from django_tenants.utils import get_tenant_type_choices


class Client(TenantMixin):
    type = models.CharField(max_length=100, choices=get_tenant_type_choices())
    name = models.CharField(max_length=100)
    description = models.TextField(max_length=200)
    created_on = models.DateField(auto_now_add=True)

    def __str__(self):
        return self.schema_name


class Domain(DomainMixin):
    pass
