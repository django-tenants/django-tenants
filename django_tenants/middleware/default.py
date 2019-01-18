from django_tenants.middleware.suspicious import SuspiciousTenantMiddleware
from django_tenants.utils import get_public_schema_name, get_tenant_model


class DefaultTenantMiddleware(SuspiciousTenantMiddleware):
    """
    Extend the SuspiciousTenantMiddleware in scenario where you want to
    configure a tenant to be served if the hostname does not match any of the
    existing tenants.
    Subclass and override DEFAULT_SCHEMA_NAME to use a schema other than the
    public schema.
        class MyTenantMiddleware(DefaultTenantMiddleware):
            DEFAULT_SCHEMA_NAME = 'default'
    """
    DEFAULT_SCHEMA_NAME = None

    def get_tenant(self, domain_model, hostname):
        try:
            return super().get_tenant(domain_model, hostname)
        except domain_model.DoesNotExist:
            schema_name = self.DEFAULT_SCHEMA_NAME
            if not schema_name:
                schema_name = get_public_schema_name()
            tenant_model = get_tenant_model()
            return tenant_model.objects.get(schema_name=schema_name)
