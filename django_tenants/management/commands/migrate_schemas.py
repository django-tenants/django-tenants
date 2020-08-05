from django_tenants.migration_executors import get_executor
from django_tenants.utils import get_tenant_model, get_public_schema_name, schema_exists, get_tenant_database_alias
from django_tenants.management.commands import SyncCommon


class MigrateSchemasCommand(SyncCommon):
    help = "Updates database schema. Manages both apps with migrations and those without."

    def add_arguments(self, parser):
        super().add_arguments(parser)
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
                            default=get_tenant_database_alias(), help='Nominates a database to synchronize. '
                            'Defaults to the "default" database.')
        parser.add_argument('--fake', action='store_true', dest='fake', default=False,
                            help='Mark migrations as run without actually running them')
        parser.add_argument('--fake-initial', action='store_true', dest='fake_initial', default=False,
                            help='Detect if tables already exist and fake-apply initial migrations if so. Make sure '
                                 'that the current database schema matches your initial migration before using this '
                                 'flag. Django will only check for an existing table name.')
        parser.add_argument('--list', '-l', action='store_true', dest='list', default=False,
                            help='Show a list of all known migrations and which are applied')
        parser.add_argument('--plan', action='store_true',
                            help='Shows a list of the migration actions that will be performed.',
        )
        parser.add_argument('--run-syncdb', action='store_true', dest='run_syncdb',
                            help='Creates tables for apps without migrations.')
        parser.add_argument('--check', action='store_true', dest='check_unapplied',
                            help='Exits with a non-zero status if unapplied migrations exist.')

    def handle(self, *args, **options):
        super().handle(*args, **options)
        self.PUBLIC_SCHEMA_NAME = get_public_schema_name()

        if self.sync_public and not self.schema_name:
            self.schema_name = self.PUBLIC_SCHEMA_NAME

        executor = get_executor(codename=self.executor)(self.args, self.options)

        if self.sync_public:
            executor.run_migrations(tenants=[self.PUBLIC_SCHEMA_NAME])
        if self.sync_tenant:
            if self.schema_name and self.schema_name != self.PUBLIC_SCHEMA_NAME:
                if not schema_exists(self.schema_name, self.options.get('database', None)):
                    raise RuntimeError('Schema "{}" does not exist'.format(
                        self.schema_name))
                else:
                    tenants = [self.schema_name]
            else:
                tenants = get_tenant_model().objects.only(
                    'schema_name').exclude(
                    schema_name=self.PUBLIC_SCHEMA_NAME).values_list(
                    'schema_name', flat=True)

            executor.run_migrations(tenants=tenants)


Command = MigrateSchemasCommand
