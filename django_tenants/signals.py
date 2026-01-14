from django.conf import settings
from django.db.models.signals import post_delete, post_save
from django.dispatch import Signal, receiver

from django_tenants.middleware.main import TENANTS_CACHE_DATA
from django_tenants.utils import get_tenant_model, schema_exists, get_tenant_domain_model

post_schema_sync = Signal()
post_schema_sync.__doc__ = """

Sent after a tenant has been saved, its schema created and synced

Argument Required = tenant

"""

schema_needs_to_be_sync = Signal()
schema_needs_to_be_sync.__doc__ = """
Schema needs to be synced

Argument Required = tenant

"""

schema_migrated = Signal()
schema_migrated.__doc__ = """
Sent after migration has finished on a schema

Argument Required = schema_name
"""


schema_pre_migration = Signal()
schema_pre_migration.__doc__ = """
Sent before migrations start on a schema

Argument Required = schema_name
"""


schema_migrate_message = Signal()
schema_migrate_message.__doc__ = """
Sent when a message is generated in run migration

Argument Required = message
"""

TENANT_CACHE_ENABLE = getattr(settings, 'TENANT_CACHE_ENABLE', False)


@receiver(post_delete)
def tenant_delete_callback(sender, instance, **kwargs):
    if not isinstance(instance, get_tenant_model()):
        return

    if instance.auto_drop_schema and schema_exists(instance.schema_name):
        instance._drop_schema(True)


@receiver(post_save)
def change_domain(sender, instance, **kwargs):
    """Change domain in cache."""
    if TENANT_CACHE_ENABLE is not True or not isinstance(
        instance, get_tenant_domain_model()
    ):
        return

    if TENANT_CACHE_ENABLE is True:
        TENANTS_CACHE_DATA[instance.domain] = instance.tenant


@receiver(post_delete)
def delete_domain(sender, instance, **kwargs):
    """Delete domain from cache."""
    if TENANT_CACHE_ENABLE is not True or not isinstance(
        instance, get_tenant_domain_model()
    ):
        return

    try:
        del TENANTS_CACHE_DATA[instance.domain]
    except KeyError:
        ...


@receiver([post_delete, post_save])
def delete_or_change_client(sender, instance, **kwargs):
    """Delete client from cache."""
    if TENANT_CACHE_ENABLE is not True or not isinstance(
        instance, get_tenant_domain_model()
    ):
        return

    # copy() is required
    # (RuntimeError: dictionary changed size during iteration)
    for hostname, tenant in TENANTS_CACHE_DATA.copy().items():
        if tenant is None or tenant == instance:
            try:
                del TENANTS_CACHE_DATA[hostname]
            except KeyError:
                ...
