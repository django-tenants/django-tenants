from django.conf import settings
from django.apps import apps as django_apps

from django_tenants.utils import has_multi_type_tenants, get_tenant_types


class TenantSyncRouter(object):
    """
    A router to control which applications will be synced,
    depending if we are syncing the shared apps or the tenant apps.
    """

    def app_in_list(self, app_label, apps_list):
        """
        Is 'app_label' present in 'apps_list'?

        apps_list is either settings.SHARED_APPS or settings.TENANT_APPS, a
        list of app names.

        We check the presence of the app's name or the full path to the apps's
        AppConfig class.
        https://docs.djangoproject.com/en/1.8/ref/applications/#configuring-applications
        """
        appconfig = django_apps.get_app_config(app_label)
        appconfig_full_name = '{}.{}'.format(
            appconfig.__module__, appconfig.__class__.__name__)
        return (appconfig.name in apps_list) or (appconfig_full_name in apps_list)

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        # the imports below need to be done here else django <1.5 goes crazy
        # https://code.djangoproject.com/ticket/20704
        from django.db import connections
        from django_tenants.utils import get_public_schema_name, get_tenant_database_alias

        if db != get_tenant_database_alias():
            return False

        connection = connections[db]
        public_schema_name = get_public_schema_name()
        if has_multi_type_tenants():
            tenant_types = get_tenant_types()
            if connection.schema_name == public_schema_name:
                installed_apps = tenant_types[public_schema_name]['APPS']
            else:
                tenant_type = connection.tenant.get_tenant_type()
                installed_apps = tenant_types[tenant_type]['APPS']
        else:
            if connection.schema_name == public_schema_name:
                installed_apps = settings.SHARED_APPS
            else:
                installed_apps = settings.TENANT_APPS
        if not self.app_in_list(app_label, installed_apps):
            return False
        return None
