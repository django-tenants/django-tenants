import sys

from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command, get_commands, load_command_class
from django.db import connection
from django_tenants.utils import get_tenant_model, get_public_schema_name


class Command(BaseCommand):

    help = "Wrapper around django commands for use with an all tenant"

    def add_arguments(self, parser):
        super().add_arguments(parser)

        parser.add_argument('--no-public', nargs='?', const=True, default=False, help='Exclude the public schema')
        parser.add_argument('command_name', nargs='+', help='The command name you want to run')

    def get_tenants(self, no_public):
        tenants = get_tenant_model().objects.all()
        if no_public:
            tenants = tenants.exclude(schema_name=get_public_schema_name())
        return tenants

    def handle(self, *args, **options):
        """
        Runs the wrapped command on every tenant.

        This is the path call_command() takes. The command line goes through
        run_from_argv() instead, so that options belonging to the wrapped command
        can be passed through without this command having to declare them. #627
        """
        command_name, *command_args = options['command_name']

        if command_name not in get_commands():
            raise CommandError("Unknown command: %r" % command_name)

        for tenant in self.get_tenants(options['no_public']):
            self.stdout.write("Applying command to: %s" % tenant.schema_name)
            connection.set_tenant(tenant)
            call_command(command_name, *command_args)

    def run_from_argv(self, argv):
        """
        Changes the option_list to use the options from the wrapped command.
        """
        try:
            self.run_wrapped_command_from_argv(argv)
        except CommandError as e:
            self.stderr.write("%s: %s" % (e.__class__.__name__, e))
            sys.exit(1)

    def run_wrapped_command_from_argv(self, argv):
        original_argv = list(argv)

        # --no-public is ours, so take it out wherever it appears -- what is left
        # belongs to the wrapped command.
        argv = list(argv)
        no_public = "--no-public" in argv
        if no_public:
            argv.remove("--no-public")

        if len(argv) <= 2 or argv[2] in ("-h", "--help"):
            # There is no command to wrap, so hand back to Django's own parser to
            # report the missing command name or print this command's help.
            return super().run_from_argv(original_argv)

        command_name = argv[2]

        try:
            app_name = get_commands()[command_name]
        except KeyError:
            raise CommandError("Unknown command: %r" % command_name)

        if isinstance(app_name, BaseCommand):
            # if the command is already loaded, use it directly.
            klass = app_name
        else:
            klass = load_command_class(app_name, command_name)

        for tenant in self.get_tenants(no_public):
            self.stdout.write("Applying command to: %s" % tenant.schema_name)
            connection.set_tenant(tenant)
            klass.run_from_argv([argv[0], command_name] + argv[3:])
