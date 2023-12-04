
from django.core.management.base import CommandError
from django.contrib.staticfiles.management.commands import collectstatic
from django.db import connection

from django_tenants.management.commands import TenantWrappedCommand
from django_tenants.utils import get_tenant_model, tenant_context


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
        parser.add_argument(
            "-a",
            "--all-schemas",
            dest="all_schemas",
            action="store_true",
            help="collectstatic for all schemas",
        )

    def collect_tenant(self, tenant, *args, **options):
        with tenant_context(tenant):
            self.command_instance.execute(*args, **options)

    def handle(self, *args, **options):
        if options.get("all_schemas"):
            return self.handle_all_schemas(*args, **options)

        tenant = self.get_tenant_from_options_or_interactive(**options)
        self.collect_tenant(tenant, *args, **options)

    def handle_all_schemas(self, *args, **options):
        TenantModel = get_tenant_model()
        tenants = TenantModel.objects.all()

        if not tenants:
            raise CommandError(
                """There are no tenants in the system.
        To learn how create a tenant, see:
        https://django-tenants.readthedocs.org/en/latest/use.html#creating-a-tenant"""
            )

        for tenant in tenants:
            self.collect_tenant(tenant, *args, **options)

        return None
