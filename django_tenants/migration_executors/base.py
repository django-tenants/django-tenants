import sys

from django.db import transaction

from django.db.migrations.recorder import MigrationRecorder

from django_tenants.signals import schema_migrated, schema_migrate_message, schema_pre_migration
from django_tenants.utils import (
    get_public_schema_name,
    get_tenant_base_migrate_command_class,
    get_tenant_database_alias,
)


def run_migrations(args, options, executor_codename, schema_name, tenant_type='',
                   allow_atomic=True, idx=None, count=None):
    from django.core.management import color
    from django.core.management.base import OutputWrapper
    from django.db import connections
    style = color.color_style()

    def style_func(msg):
        percent_str = ''
        if idx is not None and count is not None and count > 0:
            percent_str = '%d/%d (%s%%) ' % (idx + 1, count, int(100 * (idx + 1) / count))

        message = '[%s%s:%s] %s' % (
            percent_str,
            style.NOTICE(executor_codename),
            style.NOTICE(schema_name),
            msg
        )
        signal_message = '[%s%s:%s] %s' % (
            percent_str,
            executor_codename,
            schema_name,
            msg
        )
        schema_migrate_message.send(run_migrations, message=signal_message)
        return message

    schema_pre_migration.send(run_migrations, schema_name=schema_name)

    connection = connections[options.get('database', get_tenant_database_alias())]
    connection.set_schema(schema_name, tenant_type=tenant_type, include_public=False)

    # ensure that django_migrations table is created in the schema before migrations run, otherwise the migration
    # table in the public schema gets picked and no migrations are applied.   For psycopg3, need to explicitly
    # set include_public to false during schema check
    migration_recorder = MigrationRecorder(connection)
    migration_recorder.ensure_schema()
    connection.set_schema(schema_name, tenant_type=tenant_type)
                       
    stdout = OutputWrapper(sys.stdout)
    stdout.style_func = style_func
    stderr = OutputWrapper(sys.stderr)
    stderr.style_func = style_func
    if int(options.get('verbosity', 1)) >= 1:
        stdout.write(style.NOTICE("=== Starting migration"))
    migrate_command_class = get_tenant_base_migrate_command_class()
    migrate_command_class(stdout=stdout, stderr=stderr).execute(*args, **options)

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
    schema_migrated.send(run_migrations, schema_name=schema_name)


class MigrationExecutor:
    codename = None

    def __init__(self, args, options):
        self.args = args
        self.options = options

        self.PUBLIC_SCHEMA_NAME = get_public_schema_name()
        self.TENANT_DB_ALIAS = get_tenant_database_alias()

    def run_migrations(self, tenants=None):
        raise NotImplementedError

    def run_multi_type_migrations(self, tenants):
        raise NotImplementedError
