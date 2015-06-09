from django.dispatch import Signal

post_schema_sync = Signal(providing_args=['tenant'])
post_schema_sync.__doc__ = """
Sent after a tenant has been saved, its schema created and synced
"""

schema_needs_to_be_sync = Signal(providing_args=['tenant'])
schema_needs_to_be_sync.__doc__ = """
Schema needs to be synced
"""