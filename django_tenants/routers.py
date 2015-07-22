from django.conf import settings


class TenantSyncRouter(object):
    """
    A router to control which applications will be synced,
    depending if we are syncing the shared apps or the tenant apps.
    """

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        # the imports below need to be done here else django <1.5 goes crazy
        # https://code.djangoproject.com/ticket/20704
        from django.db import connection
        from django_tenants.utils import get_public_schema_name

        # for INSTALLED_APPS we need a name
        from django.apps import apps
        app_name = apps.get_app_config(app_label).name

        if connection.schema_name == get_public_schema_name():
            if app_name not in settings.SHARED_APPS:
                return False
        else:
            if app_name not in settings.TENANT_APPS:
                return False

        return None
