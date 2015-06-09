from django.core.management.base import CommandError
from django.conf import settings
from django_tenants.utils import django_is_in_test_mode

from django.core.management.commands import syncdb


class Command(syncdb.Command):

    def handle(self, *args, **options):
        database = options.get('database', 'default')
        if (settings.DATABASES[database]['ENGINE'] == 'django_tenants.postgresql_backend' and not
                django_is_in_test_mode()):
            raise CommandError("syncdb has been disabled, for database '{0}'. "
                               "Use sync_schemas instead. Please read the "
                               "documentation if you don't know why "
                               "you shouldn't call syncdb directly!".format(database))
        super(Command, self).handle(*args, **options)
