import sys

from django.db import transaction

from django.core.management.commands.migrate import Command as MigrateCommand
from django_tenants.utils import get_public_schema_name, get_tenant_database_alias


def run_migrations(args, options, executor_codename, schema_name, allow_atomic=True, idx=None, count=None):
    from django.core.management import color
    from django.core.management.base import OutputWrapper
    from django.db import connections

    style = color.color_style()

    def style_func(msg):
        percent_str = ''
        if idx is not None and count is not None and count > 0:
            percent_str = '%d/%d (%s%%) ' % (idx + 1, count, int(100 * (idx + 1) / count))
        return '[%s%s:%s] %s' % (
            percent_str,
            style.NOTICE(executor_codename),
            style.NOTICE(schema_name),
            msg
        )

    connection = connections[options.get('database', get_tenant_database_alias())]
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


class MigrationExecutor:
    codename = None

    def __init__(self, args, options):
        self.args = args
        self.options = options

        self.PUBLIC_SCHEMA_NAME = get_public_schema_name()
        self.TENANT_DB_ALIAS = get_tenant_database_alias()

    def run_migrations(self, tenants=None):
        raise NotImplementedError
