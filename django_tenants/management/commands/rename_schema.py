from django.core.management.base import BaseCommand
from django_tenants.utils import get_tenant_model, schema_rename


class Command(BaseCommand):
    help = 'Renames a schema'

    def add_arguments(self, parser):

        parser.add_argument('--rename_from',
                            help='Specifies which schema to rename (schema_name of tenant)')

        parser.add_argument('--rename_to',
                            help='New schema name')

    def _input(self, question):
        """Wrapper around 'input' for overriding while testing"""
        return input(question)

    def handle(self, *args, **options):
        tenant_model = get_tenant_model()
        all_tenants = tenant_model.objects.all()

        rename_from = options.get("rename_from")
        while rename_from == '' or rename_from is None:
            while True:
                rename_from = self._input("Rename Schema ('?' to list schemas): ")
                if rename_from == '?':
                    self.stdout.write('\n'.join(["%s" % t.schema_name for t in all_tenants]))
                else:
                    break
        if tenant_model.objects.filter(schema_name=rename_from).count() == 0:
            self.stdout.write(self.style.ERROR("Tenant does not exist"))
            return
        rename_to = options.get("rename_to")
        while rename_to == '' or rename_to is None:
            rename_to = self._input("Rename to: ")
        schema_rename(tenant_model.objects.get(schema_name=rename_from), rename_to)
