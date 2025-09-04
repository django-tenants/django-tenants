from django.core.management.base import BaseCommand
from django_tenants.management.commands import InteractiveDomainOption


class Command(InteractiveDomainOption, BaseCommand):
    help = 'Deletes a domain from a tenant'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def add_arguments(self, parser):
        super().add_arguments(parser)

        parser.add_argument(
            "--noinput",
            "--no-input",
            action="store_false",
            dest="interactive",
            help=(
                "Tells Django to NOT prompt the user for input of any kind. "
                'You must use --schema_names and --domain-domain with --noinput'
            ),
        )

    def handle(self, *args, **options):
        # Pull the tenant and let the method validate we can continue
        tenant = self.get_tenant_from_options_or_interactive(**options)

        # Pull the domain and let the method validate we can continue
        domain = self.get_domain_from_options_or_interactive(tenant, **options)

        # Prompt the user when interactive mode is enabled
        if options["interactive"]:
            self.print_warning(f"Warning you are about to delete '{domain.domain}' for tenant '{tenant.schema_name}' there is no undo.")
            result = input(f"Are you sure you want to delete '{domain.domain}' for tenant '{tenant.schema_name}', yes/no?")
            while len(result) < 1 or result.lower() not in ["yes", "no"]:
                result = input("Please answer yes or no: ")
            if result.lower() == "yes":
                self.delete_domain(domain)
            elif result.lower() == "no":
                self.stderr.write("Canceled")
        else:
            self.delete_domain(domain)

    def delete_domain(self, domain):
        self.print_info(f"Deleting domain '{domain.domain}'")
        domain.delete()
        self.print_info(f"Deleted domain '{domain.domain}'")

    def print_warning(self, message):
        self.stderr.write(f"\033[91m{message}\033[0m")

    def print_info(self, message):
        self.stderr.write(f"\033[94m{message}\033[0m")
