import django

if django.VERSION >= (1, 7, 0):
    from django.core.management.commands.migrate import Command as MigrateCommand

from django_tenants.utils import get_public_schema_name


def run_migrations(args, options, schema_name):
    from .base import MigrateCommand

    from django.core.management import color
    from django.db import connection

    connection.close()

    if int(options.get('verbosity', 1)) >= 1:
        style = color.color_style()
        print style.NOTICE("=== Running migrate for schema %s" % schema_name)
    connection.set_schema(schema_name)
    MigrateCommand().execute(*args, **options)
    connection.set_schema_to_public()


class MigrationExecutor(object):
    codename = None

    def __init__(self, args, options):
        self.args = args
        self.options = options

        self.PUBLIC_SCHEMA_NAME = get_public_schema_name()

    def run_migrations(self, tenants=None):
        raise NotImplementedError

    """
    def public_apps(self):
        return settings.SHARED_APPS

    def tenant_apps(self):
        return settings.TENANT_APPS
    """
