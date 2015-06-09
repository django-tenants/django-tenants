from django_tenants.management.commands import TenantWrappedCommand
from django.contrib.auth.management.commands import createsuperuser


class Command(TenantWrappedCommand):
    COMMAND = createsuperuser.Command
