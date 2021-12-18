from . import TenantWrappedCommand
from django.contrib.staticfiles.management.commands import collectstatic


class Command(TenantWrappedCommand):
    requires_system_checks = []
    COMMAND = collectstatic.Command

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--skip-checks",
            action="store_true",
            dest="skip_checks",
            default=False,
            help="Skip the checks.",
        )
