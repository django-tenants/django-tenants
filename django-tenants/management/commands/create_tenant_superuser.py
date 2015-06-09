from tenant_schemas.management.commands import TenantWrappedCommand
from django.contrib.auth.management.commands import createsuperuser


class Command(TenantWrappedCommand):
    COMMAND = createsuperuser.Command
