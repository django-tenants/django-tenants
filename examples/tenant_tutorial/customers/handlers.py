from django.dispatch import receiver

from django_tenants.migration_executors.base import run_migrations
from django_tenants.models import TenantMixin
from django_tenants.signals import schema_migrated, schema_needs_to_be_sync, post_schema_sync


@receiver(schema_migrated, sender=run_migrations)
def check_schema_migrated(**kwargs):
    schema_name = kwargs['schema_name']
    print('------------------')
    print('check_schema_migrated')


# @receiver(schema_migrate_message, sender=run_migrations)
# def check_schema_migrate_message(**kwargs):
#     message = kwargs['message']
#     print('------------------')
#     print('schema_migrate_message')
#     print(message)


@receiver(schema_needs_to_be_sync, sender=TenantMixin)
def check_schema_needs_to_be_sync(**kwargs):
    client = kwargs['tenant']
    print('------------------')
    print('check_schema_needs_to_be_sync')


@receiver(post_schema_sync, sender=TenantMixin)
def check_post_schema_sync(**kwargs):
    client = kwargs['tenant']
    print('------------------')
    print('check_post_schema_sync')

