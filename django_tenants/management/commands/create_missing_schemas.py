from django.core.management.base import BaseCommand

from django_tenants.utils import get_tenant_model, schema_exists


class Command(BaseCommand):
    help = 'Create missing tenants'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        tenants = get_tenant_model().objects.all()
        for tenant in tenants:
            if not schema_exists(schema_name=tenant.schema_name):
                self.stdout.write(self.style.NOTICE("Missing '%s' schema lets create it" % tenant.schema_name))
                tenant.create_schema()

        self.stdout.write("Done")
