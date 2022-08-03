import argparse

from django.core.management.base import BaseCommand, CommandError
from django.core.management import get_commands, load_command_class
from django.db import connection
from django_tenants.utils import get_tenant_model, get_public_schema_name


class Command(BaseCommand):

    help = "Wrapper around django commands for use with an all tenant"

    def add_arguments(self, parser):
        super().add_arguments(parser)
           
        parser.add_argument('--no-public', nargs='?', const=True, default=False, help='Exclude the public schema')
        parser.add_argument('command_name', nargs='+', help='The command name you want to run')

    def run_from_argv(self, argv):
        """
        Changes the option_list to use the options from the wrapped command.
        """
        # load the command object.
        if len(argv) <= 3:
            return
        try:
            app_name = get_commands()[argv[3]]
        except KeyError:
            raise CommandError("Unknown command: %r" % argv[3])

        if isinstance(app_name, BaseCommand):
            # if the command is already loaded, use it directly.
            klass = app_name
        else:
            klass = load_command_class(app_name, argv[3])

        # Ugly, but works. Delete tenant_command from the argv, parse the schema manually
        # and forward the rest of the arguments to the actual command being wrapped.
        del argv[1]
        del argv[2]
        schema_parser = argparse.ArgumentParser()
        schema_namespace, args = schema_parser.parse_known_args(argv)
        print(args)

        tenant_model = get_tenant_model()
        tenants = tenant_model.objects.all()
        if argv[2]:
            tenants = tenants.exclude(schema_name=get_public_schema_name())
        for tenant in tenants:
            self.stdout.write("Applying command to: %s" % tenant.schema_name)
            connection.set_tenant(tenant)
            klass.run_from_argv(args)

