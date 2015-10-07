import sys

from django.core.management.commands.migrate import Command as MigrateCommand
from django_tenants.utils import get_public_schema_name


def run_migrations(args, options, schema_name):
    from django.core.management import color
    from django.core.management.base import OutputWrapper
    from django.db import connection

    connection.close()

    style = color.color_style()

    def style_func(msg):
        return '[%s] %s' % (
            style.NOTICE(schema_name),
            msg
        )

    connection.set_schema(schema_name)
    stdout = OutputWrapper(sys.stdout)
    stdout.style_func = style_func
    stderr = OutputWrapper(sys.stderr)
    stderr.style_func = style_func
    if int(options.get('verbosity', 1)) >= 1:
        stdout.write(style.NOTICE("=== Starting migration"))
    MigrateCommand(stdout=stdout, stderr=stderr).execute(*args, **options)
    connection.set_schema_to_public()


class MigrationExecutor(object):
    codename = None

    def __init__(self, args, options):
        self.args = args
        self.options = options

        self.PUBLIC_SCHEMA_NAME = get_public_schema_name()

    def run_migrations(self, tenants=None):
        raise NotImplementedError
