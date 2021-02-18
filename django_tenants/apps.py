from django.conf import settings
from django.apps import AppConfig
from django.core.exceptions import ImproperlyConfigured
from django_tenants.utils import get_public_schema_name, validate_extra_extensions


recommended_config = """
Warning: You should put 'django_tenants' at the end of INSTALLED_APPS:
INSTALLED_APPS = TENANT_APPS + SHARED_APPS + ('django_tenants',)
This is necessary to overwrite built-in django management commands with
their schema-aware implementations.
"""


class DjangoTenantsConfig(AppConfig):
    name = 'django_tenants'
    verbose_name = "Django tenants"

    def ready(self):
        from django.db import connection

        # Test for configuration recommendations. These are best practices,
        # they avoid hard to find bugs and unexpected behaviour.

        if hasattr(settings, 'HAS_MULTI_TYPE_TENANTS') and settings.HAS_MULTI_TYPE_TENANTS:
            if not hasattr(settings, 'TENANT_TYPES'):
                raise ImproperlyConfigured('Using multi type you must setup TENANT_TYPES setting')
            if get_public_schema_name() not in settings.TENANT_TYPES:
                raise ImproperlyConfigured('get_public_schema_name() value not found as a key in TENANTS')
            if not hasattr(settings, 'MULTI_TYPE_DATABASE_FIELD'):
                raise ImproperlyConfigured('Using multi type you must setup MULTI_TYPE_DATABASE_FIELD setting')
        else:
            if not hasattr(settings, 'TENANT_APPS'):
                raise ImproperlyConfigured('TENANT_APPS setting not set')

            if not settings.TENANT_APPS:
                raise ImproperlyConfigured("TENANT_APPS is empty. "
                                           "Maybe you don't need this app?")

        if not hasattr(settings, 'TENANT_MODEL'):
            raise ImproperlyConfigured('TENANT_MODEL setting not set')

        if 'django_tenants.routers.TenantSyncRouter' not in settings.DATABASE_ROUTERS:
            raise ImproperlyConfigured("DATABASE_ROUTERS setting must contain "
                                       "'django_tenants.routers.TenantSyncRouter'.")

        validate_extra_extensions()
