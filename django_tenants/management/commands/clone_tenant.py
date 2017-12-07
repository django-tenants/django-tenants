from optparse import make_option
from django.core import exceptions
from django.core.management.base import BaseCommand
from django.utils.encoding import force_str
from django.db.utils import IntegrityError
from django.db import connection
from django_tenants.clone import CloneSchema
from django_tenants.utils import get_tenant_model, get_tenant_domain_model


class Command(BaseCommand):
    help = 'Clones a tenant'

    # Only use editable fields
    tenant_fields = [field for field in get_tenant_model()._meta.fields
                     if field.editable and not field.primary_key]
    domain_fields = [field for field in get_tenant_domain_model()._meta.fields
                     if field.editable and not field.primary_key]

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)

        self.option_list = ()
        self.option_list += (make_option('--clone_from',
                                         help='Specifies which schema to clone.'), )
        for field in self.tenant_fields:
            self.option_list += (make_option('--%s' % field.name,
                                             help='Specifies the %s for tenant.' % field.name), )
        for field in self.domain_fields:
            self.option_list += (make_option('--%s' % field.name,
                                             help="Specifies the %s for the tenant's domain." % field.name), )

    def handle(self, *args, **options):

        tenant_data = {}
        for field in self.tenant_fields:
            input_value = options.get(field.name, None)
            tenant_data[field.name] = input_value

        domain_data = {}
        for field in self.domain_fields:
            input_value = options.get(field.name, None)
            domain_data[field.name] = input_value

        clone_schema_from = options.get('clone_from')
        while clone_schema_from == '' or clone_schema_from is None:
            clone_schema_from = input(force_str('Clone schema from: '))

        while True:
            for field in self.tenant_fields:
                if tenant_data.get(field.name, '') == '':
                    input_msg = field.verbose_name
                    default = field.get_default()
                    if default:
                        input_msg = "%s (leave blank to use '%s')" % (input_msg, default)

                    input_value = input(force_str('%s: ' % input_msg)) or default
                    tenant_data[field.name] = input_value
            tenant = self.store_tenant(clone_schema_from, **tenant_data)
            if tenant is not None:
                break
            tenant_data = {}

        while True:
            domain_data['tenant'] = tenant
            for field in self.domain_fields:
                if domain_data.get(field.name, '') == '':
                    input_msg = field.verbose_name
                    default = field.get_default()
                    if default:
                        input_msg = "%s (leave blank to use '%s')" % (input_msg, default)

                    input_value = input(force_str('%s: ' % input_msg)) or default
                    domain_data[field.name] = input_value
            domain = self.store_tenant_domain(**domain_data)
            if domain is not None:
                break
            domain_data = {}

    def store_tenant(self, clone_schema_from, **fields):
        connection.set_schema_to_public()
        cursor = connection.cursor()

        try:
            tenant = get_tenant_model()(**fields)
            tenant.auto_create_schema = False
            tenant.save()

            clone_schema = CloneSchema(cursor)
            clone_schema.clone(clone_schema_from, tenant.schema_name)
            return tenant
        except exceptions.ValidationError as e:
            self.stderr.write("Error: %s" % '; '.join(e.messages))
            return None
        except IntegrityError:
            return None

    def store_tenant_domain(self, **fields):
        try:
            domain = get_tenant_domain_model().objects.create(**fields)
            domain.save()
            return domain
        except exceptions.ValidationError as e:
            self.stderr.write("Error: %s" % '; '.join(e.messages))
            return None
        except IntegrityError:
            return None
