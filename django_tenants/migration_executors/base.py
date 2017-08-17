import sys

from django.db import transaction

from django.core.management.commands.migrate import Command as MigrateCommand
from django_tenants.utils import get_public_schema_name


def run_migrations(args, options, executor_codename, schema_name, allow_atomic=True, percent=None):
    from django.core.management import color
    from django.core.management.base import OutputWrapper
    from django.db import connection

    style = color.color_style()

    def style_func(msg):
        percent_str = ''
        if percent is not None:
            percent_str = '%s%% ' % int(100*percent)
        return '[%s%s:%s] %s' % (
            percent_str,
            style.NOTICE(executor_codename),
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

    try:
        transaction.commit()
        connection.close()
        connection.connection = None
    except transaction.TransactionManagementError:
        if not allow_atomic:
            raise

        # We are in atomic transaction, don't close connections
        pass

    connection.set_schema_to_public()


class MigrationExecutor(object):
    codename = None

    def __init__(self, args, options):
        self.args = args
        self.options = options

        self.PUBLIC_SCHEMA_NAME = get_public_schema_name()

    def run_migrations(self, tenants=None):
        raise NotImplementedError
