import django
import warnings
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from tenant_schemas.utils import get_public_schema_name, get_tenant_model


recommended_config = """
Warning: You should put 'tenant_schemas' at the end of INSTALLED_APPS:
INSTALLED_APPS = TENANT_APPS + SHARED_APPS + ('tenant_schemas',)
This is necessary to overwrite built-in django management commands with
their schema-aware implementations.
"""
# Test for configuration recommendations. These are best practices,
# they avoid hard to find bugs and unexpected behaviour.
if not hasattr(settings, 'TENANT_APPS'):
    raise ImproperlyConfigured('TENANT_APPS setting not set')

if not settings.TENANT_APPS:
    raise ImproperlyConfigured("TENANT_APPS is empty. "
                               "Maybe you don't need this app?")

if not hasattr(settings, 'TENANT_MODEL'):
    raise ImproperlyConfigured('TENANT_MODEL setting not set')

if django.VERSION < (1, 7, 0) and settings.INSTALLED_APPS[-1] != 'tenant_schemas':
    warnings.warn(recommended_config, SyntaxWarning)

if 'tenant_schemas.routers.TenantSyncRouter' not in settings.DATABASE_ROUTERS:
    raise ImproperlyConfigured("DATABASE_ROUTERS setting must contain "
                               "'tenant_schemas.routers.TenantSyncRouter'.")

if hasattr(settings, 'PG_EXTRA_SEARCH_PATHS'):
    if get_public_schema_name() in settings.PG_EXTRA_SEARCH_PATHS:
        raise ImproperlyConfigured(
            "%s can not be included on PG_EXTRA_SEARCH_PATHS."
            % get_public_schema_name())

    # make sure no tenant schema is in settings.PG_EXTRA_SEARCH_PATHS
    invalid_schemas = set(settings.PG_EXTRA_SEARCH_PATHS).intersection(
        get_tenant_model().objects.all().values_list('schema_name', flat=True))
    if invalid_schemas:
        raise ImproperlyConfigured(
            "Do not include tenant schemas (%s) on PG_EXTRA_SEARCH_PATHS."
            % list(invalid_schemas))
