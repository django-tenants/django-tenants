from django.db.models.signals import post_delete
from django.dispatch import Signal, receiver
from django_tenants.utils import get_tenant_model, schema_exists

post_schema_sync = Signal(providing_args=['tenant'])
post_schema_sync.__doc__ = """
Sent after a tenant has been saved, its schema created and synced
"""

schema_needs_to_be_sync = Signal(providing_args=['tenant'])
schema_needs_to_be_sync.__doc__ = """
Schema needs to be synced
"""

schema_migrated = Signal(providing_args=['schema_name'])
schema_migrated.__doc__ = """
Sent after migration has finished on a schema
"""

schema_migrate_message = Signal(providing_args=['message'])
schema_migrate_message.__doc__ = """
Sent when a message is generated in run migration
"""


@receiver(post_delete)
def tenant_delete_callback(sender, instance, **kwargs):
    if not isinstance(instance, get_tenant_model()):
        return

    if instance.auto_drop_schema and schema_exists(instance.schema_name):
        instance._drop_schema(True)

