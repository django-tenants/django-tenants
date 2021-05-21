from . import TenantWrappedCommand
from django.contrib.staticfiles.management.commands import collectstatic


class Command(TenantWrappedCommand):
    requires_system_checks = []
    COMMAND = collectstatic.Command
