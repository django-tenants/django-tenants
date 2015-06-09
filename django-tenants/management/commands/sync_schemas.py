import django
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ImproperlyConfigured
from django.db.models import get_apps, get_models
if "south" in settings.INSTALLED_APPS:
    from south.management.commands.syncdb import Command as SyncdbCommand
else:
    from django.core.management.commands.syncdb import Command as SyncdbCommand
from django.db import connection
from tenant_schemas.utils import get_tenant_model, get_public_schema_name
from tenant_schemas.management.commands import SyncCommon


class Command(SyncCommon):
    help = "Sync schemas based on TENANT_APPS and SHARED_APPS settings"
    option_list = SyncdbCommand.option_list + SyncCommon.option_list

    def handle(self, *args, **options):
        if django.VERSION >= (1, 7, 0):
            raise RuntimeError('This command is only meant to be used for 1.6'
                               ' and older version of django. For 1.7, use'
                               ' `migrate_schemas` instead.')
        super(Command, self).handle(*args, **options)

        if "south" in settings.INSTALLED_APPS:
            self.options["migrate"] = False

        # Content types may be different on tenants, so reset the cache
        ContentType.objects.clear_cache()

        if self.sync_public:
            self.sync_public_apps()
        if self.sync_tenant:
            self.sync_tenant_apps(self.schema_name)

    def _sync_tenant(self, tenant):
        self._notice("=== Running syncdb for schema: %s" % tenant.schema_name)
        connection.set_tenant(tenant, include_public=False)
        SyncdbCommand().execute(**self.options)

    def sync_tenant_apps(self, schema_name=None):
        if schema_name:
            tenant = get_tenant_model().objects.filter(schema_name=schema_name).get()
            self._sync_tenant(tenant)
        else:
            all_tenants = get_tenant_model().objects.exclude(schema_name=get_public_schema_name())
            if not all_tenants:
                self._notice("No tenants found!")

            for tenant in all_tenants:
                self._sync_tenant(tenant)

    def sync_public_apps(self):
        SyncdbCommand().execute(**self.options)
        self._notice("=== Running syncdb for schema public")
