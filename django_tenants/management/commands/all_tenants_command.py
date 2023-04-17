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
        if len(argv) <= 2:
            return
        
        no_public = "--no-public" in argv
        
        command_args = [argv[0]]
        
        command_args.extend(argv[3:] if no_public else argv[2:])
        
        try:
            app_name = get_commands()[command_args[1]]
        except KeyError:
            raise CommandError("Unknown command: %r" % command_args[1])

        if isinstance(app_name, BaseCommand):
            # if the command is already loaded, use it directly.
            klass = app_name
        else:
            klass = load_command_class(app_name, command_args[1])

        schema_parser = argparse.ArgumentParser()
        schema_namespace, args = schema_parser.parse_known_args(command_args)
        print(args)

        tenant_model = get_tenant_model()
        tenants = tenant_model.objects.all()
        if no_public:
            tenants = tenants.exclude(schema_name=get_public_schema_name())
        for tenant in tenants:
            self.stdout.write("Applying command to: %s" % tenant.schema_name)
            connection.set_tenant(tenant)
            klass.run_from_argv(args)

