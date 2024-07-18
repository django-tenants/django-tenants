from django.core.management.base import BaseCommand
from django_tenants.management.commands import InteractiveTenantOption


class Command(InteractiveTenantOption, BaseCommand):
    help = 'deletes a tenant'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def add_arguments(self, parser):
        parser.add_argument(
            "-s", "--schema", dest="schema_name", help="specify tenant schema"
        )
        parser.add_argument(
            "--noinput",
            "--no-input",
            action="store_false",
            dest="interactive",
            help=(
                "Tells Django to NOT prompt the user for input of any kind. "
                "You must use --schema_names with --noinput"
            ),
        )

    def handle(self, *args, **options):
        tenant = self.get_tenant_from_options_or_interactive(**options)

        schema_name = tenant.schema_name
        if options["interactive"]:
            self.print_warning(f"Warning you are about to delete '{schema_name}' there is no undo.")
            result = input(f"Are you sure you want to delete '{schema_name}'?")
            while len(result) < 1 or result.lower() not in ["yes", "no"]:
                result = input("Please answer yes or no: ")
                if result.lower() == "yes":
                    self.delete_tenant(tenant)
                elif result.lower() == "no":
                    self.stderr.write("Canceled")
        else:
            self.delete_tenant(tenant)

    def delete_tenant(self, tenant):
        self.print_info(f"Deleting '{tenant.schema_name}'" )
        tenant.auto_drop_schema = True
        tenant.delete()
        self.print_info(f"Deleted '{tenant.schema_name}'")

    def print_warning(self, message):
        self.stderr.write(f"\033[91m{message}\033[0m")

    def print_info(self, message):
        self.stderr.write(f"\033[94m{message}\033[0m")
