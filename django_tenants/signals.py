from django.db.models.signals import post_delete, pre_delete
from django.dispatch import Signal, receiver
from django_tenants.utils import (
    check_tenant_data_change_allowed, get_current_schema_name, get_public_schema_name,
    get_tenant_model, schema_exists,
)

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


@receiver(pre_delete)
def tenant_or_domain_pre_delete_guard(sender, instance, **kwargs):
    # Covers QuerySet.delete() and cascades (e.g. the admin's "delete
    # selected"), which never go through the model's own delete().
    current = get_current_schema_name()
    if current is None or current == get_public_schema_name():
        return
    if isinstance(instance, get_tenant_model()):
        check_tenant_data_change_allowed(instance.schema_name, 'delete')
        return
    # Any DomainMixin model, whether or not it is TENANT_DOMAIN_MODEL (which
    # is optional for projects that resolve tenants without the stock
    # middleware), so a domain can't be deleted and then claimed.
    from django_tenants.models import DomainMixin
    if isinstance(instance, DomainMixin):
        if instance.tenant_id is not None:
            check_tenant_data_change_allowed(instance.tenant.schema_name, 'delete a domain of')


@receiver(post_delete)
def tenant_delete_callback(sender, instance, **kwargs):
    if not isinstance(instance, get_tenant_model()):
        return

    if instance.auto_drop_schema and schema_exists(instance.schema_name):
        instance._drop_schema(True)
