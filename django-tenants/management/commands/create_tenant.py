from optparse import make_option
from django.core import exceptions
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils.encoding import force_str
from django.utils.six.moves import input
from django.db.utils import IntegrityError
from tenant_schemas.utils import get_tenant_model


class Command(BaseCommand):
    help = 'Create a tenant'

    # Only use editable fields
    fields = [field for field in get_tenant_model()._meta.fields if field.editable and not field.primary_key]

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)

        self.option_list = BaseCommand.option_list

        for field in self.fields:
            self.option_list += (make_option('--%s' % field.name,
                                             help='Specifies the %s for tenant.' % field.name), )
        self.option_list += (make_option('-s', action="store_true",
                                         help='Create a superuser afterwards.'),)



    def handle(self, *args, **options):

        tenant = {}
        for field in self.fields:
            tenant[field.name] = options.get(field.name, None)

        saved = False
        while not saved:
            for field in self.fields:
                if tenant.get(field.name, '') == '':
                    input_msg = field.verbose_name
                    default = field.get_default()
                    if default:
                        input_msg = "%s (leave blank to use '%s')" % (input_msg, default)
                    tenant[field.name] = input(force_str('%s: ' % input_msg)) or default

            saved = self.store_tenant(**tenant)
            if not saved:
                tenant = {}
                continue

        if options.get('s', None):
            self.stdout.write("Create superuser for %s" % tenant['schema_name'])
            call_command('create_tenant_superuser', schema_name=tenant['schema_name'], interactive=True)

    def store_tenant(self, **fields):
        try:
            tenant = get_tenant_model().objects.create(**fields)
            tenant.save()
            return True
        except exceptions.ValidationError as e:
            self.stderr.write("Error: %s" % '; '.join(e.messages))
            return False
        except IntegrityError:
            self.stderr.write("Error: Invalid value(s).")
            return False
