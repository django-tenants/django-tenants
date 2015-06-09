
from django.core.management.commands.migrate import Command as MigrateCommand
from django.db import connection, DEFAULT_DB_ALIAS
from django.conf import settings

from django_tenants.utils import get_tenant_model, get_public_schema_name, schema_exists
from django_tenants.management.commands import SyncCommon


class MigrateSchemasCommand(SyncCommon):
    help = "Updates database schema. Manages both apps with migrations and those without."

    def add_arguments(self, parser):
        super(MigrateSchemasCommand, self).add_arguments(parser)
        parser.add_argument('app_label', nargs='?',
                            help='App label of an application to synchronize the state.')
        parser.add_argument('migration_name', nargs='?',
                            help=(
                                'Database state will be brought to the state after that '
                                'migration. Use the name "zero" to unapply all migrations.'
                            ),)
        parser.add_argument('--noinput', action='store_false', dest='interactive', default=True,
                            help='Tells Django to NOT prompt the user for input of any kind.')
        parser.add_argument('--no-initial-data', action='store_false', dest='load_initial_data', default=True,
                            help='Tells Django not to load any initial data after database synchronization.')
        parser.add_argument('--database', action='store', dest='database',
                            default=DEFAULT_DB_ALIAS, help='Nominates a database to synchronize. '
                            'Defaults to the "default" database.')
        parser.add_argument('--fake', action='store_true', dest='fake', default=False,
                            help='Mark migrations as run without actually running them')
        parser.add_argument('--fake-initial', action='store_true', dest='fake_initial', default=False,
                            help='Detect if tables already exist and fake-apply initial migrations if so. Make sure '
                                 'that the current database schema matches your initial migration before using this '
                                 'flag. Django will only check for an existing table name.')
        parser.add_argument('--list', '-l', action='store_true', dest='list', default=False,
                            help='Show a list of all known migrations and which are applied')

    def handle(self, *args, **options):
        super(MigrateSchemasCommand, self).handle(*args, **options)
        self.PUBLIC_SCHEMA_NAME = get_public_schema_name()

        if self.sync_public and not self.schema_name:
            self.schema_name = self.PUBLIC_SCHEMA_NAME

        if self.sync_public:
            self.run_migrations(self.schema_name, settings.SHARED_APPS, options)
        if self.sync_tenant:
            if self.schema_name and self.schema_name != self.PUBLIC_SCHEMA_NAME:
                if not schema_exists(self.schema_name):
                    raise RuntimeError('Schema "{}" does not exist'.format(
                        self.schema_name))
                else:
                    self.run_migrations(self.schema_name, settings.TENANT_APPS, options)
            else:
                all_tenants = get_tenant_model().objects.exclude(schema_name=get_public_schema_name())
                for tenant in all_tenants:
                    self.run_migrations(tenant.schema_name, settings.TENANT_APPS, options)

    def run_migrations(self, schema_name, included_apps, options):
        self._notice("=== Running migrate for schema %s" % schema_name)
        connection.set_schema(schema_name)
        command = MigrateCommand()

        command.execute(*self.args, **options)
        connection.set_schema_to_public()
