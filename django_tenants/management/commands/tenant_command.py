
from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command, get_commands, load_command_class
from django.db import connection
from . import InteractiveTenantOption


class Command(InteractiveTenantOption, BaseCommand):
    help = "Wrapper around django commands for use with an individual tenant"

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)

        parser.add_argument('command_name', nargs='+', help='The command name you want to run')

    def run_from_argv(self, argv):
        """
        Changes the option_list to use the options from the wrapped command.
        Adds schema parameter to specify which schema will be used when
        executing the wrapped command.
        """
        # load the command object.
        if len(argv) <= 2:
            return

        try:
            app_name = get_commands()[argv[2]]
        except KeyError:
            raise CommandError("Unknown command: %r" % argv[2])


        if isinstance(app_name, BaseCommand):
            # if the command is already loaded, use it directly.
            klass = app_name
        else:
            klass = load_command_class(app_name, argv[2])

        super(Command, self).run_from_argv(argv)

    def handle(self, *args, **options):
        tenant = self.get_tenant_from_options_or_interactive(**options)
        connection.set_tenant(tenant)

        command = options.pop('command_name')
        command_name = command[0]
        command_argv = command[1:]
        
        call_command(command_name, *command_argv, **options)