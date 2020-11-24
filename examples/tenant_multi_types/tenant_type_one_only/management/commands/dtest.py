from django.core.management.base import BaseCommand

from tenant_only.models import TableTwo


class Command(BaseCommand):
    help = 'Test table two'

    def add_arguments(self, parser):
        parser.add_argument('--id', nargs='+', type=int)

    def handle(self, *args, **options):
        print(options['id'])
        table_two = TableTwo.objects.filter(pk__in=options['id'])
        print(table_two)


