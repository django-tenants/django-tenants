from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):

    def handle(self, *args, **options):
        raise CommandError("syncdb has been removed in django 1.9")
