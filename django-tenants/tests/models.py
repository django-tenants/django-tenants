from django.db import models
from tenant_schemas.models import TenantMixin


# as TenantMixin is an abstract model, it needs to be created
class Tenant(TenantMixin):
    pass

    class Meta:
        app_label = 'tenant_schemas'


class NonAutoSyncTenant(TenantMixin):
    auto_create_schema = False

    class Meta:
        app_label = 'tenant_schemas'
