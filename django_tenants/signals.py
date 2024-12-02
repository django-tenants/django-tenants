from django.db.models.signals import post_delete
from django.dispatch import Signal, receiver
from django_tenants.utils import get_tenant_model, schema_exists

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


@receiver(post_delete)
def tenant_delete_callback(sender, instance, **kwargs):
    if not isinstance(instance, get_tenant_model()):
        return

    if instance.auto_drop_schema and schema_exists(instance.schema_name):
        instance._drop_schema(True)
