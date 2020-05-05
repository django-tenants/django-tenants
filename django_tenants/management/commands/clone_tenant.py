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
    # noinspection PyProtectedMember
    domain_fields = [field for field in get_tenant_domain_model()._meta.fields
                     if field.editable and not field.primary_key]

    def add_arguments(self, parser):

        parser.add_argument('--clone_from',
                            help='Specifies which schema to clone.')

        parser.add_argument('--clone_tenant_fields',
                            help='Clone the tenant fields.')

        parser.add_argument('--db_user',
                            help='the user for the database the default is postgres')

        for field in self.tenant_fields:
            parser.add_argument('--%s' % field.attname,
                                help='Specifies the %s for tenant.' % field.attname)

        for field in self.domain_fields:
            parser.add_argument('--domain-%s' % field.attname,
                                help="Specifies the %s for the tenant's domain." % field.attname)

        parser.add_argument('-s', action="store_true",
                            help='Create a superuser afterwards.')

    def _input(self, question):
        """Wrapper around 'input' for overriding while testing"""
        return input(question)

    def handle(self, *args, **options):
        tenant_model = get_tenant_model()
        all_tenants = tenant_model.objects.all()
        tenant_data = {}
        for field in self.tenant_fields:
            input_value = options.get(field.attname, None)
            tenant_data[field.attname] = input_value

        domain_data = {}
        for field in self.domain_fields:
            input_value = options.get('domain_%s' % field.attname, None)
            domain_data[field.attname] = input_value

        clone_schema_from = options.get('clone_from')
        while clone_schema_from == '' or clone_schema_from is None:

            while True:
                clone_schema_from = self._input("Clone Tenant Schema ('?' to list schemas): ")
                if clone_schema_from == '?':
                    self.stdout.write('\n'.join(["%s" % t.schema_name for t in all_tenants]))
                else:
                    break

        clone_tenant_fields = options.get('clone_tenant_fields')
        while clone_tenant_fields is None or clone_tenant_fields.lower() not in ['no', 'yes', 'true', 'false']:
            clone_tenant_fields = self._input("Clone Tenant tenant fields: ")

        if clone_tenant_fields.lower() in ['yes', 'true']:
            new_schema_name = options.get('schema_name')
            while new_schema_name == '' or new_schema_name is None:
                new_schema_name = self._input("New tenant schema name: ")
            tenant_data['schema_name'] = new_schema_name

            tenant = self.store_tenant(clone_schema_from=clone_schema_from,
                                       clone_tenant_fields=True,
                                       **tenant_data)
        else:
            while True:
                for field in self.tenant_fields:
                    if tenant_data.get(field.attname, '') == '':
                        input_msg = field.verbose_name
                        default = field.get_default()
                        if default:
                            input_msg = "%s (leave blank to use '%s')" % (input_msg, default)

                        input_value = self._input(force_str('%s: ' % input_msg)) or default
                        tenant_data[field.attname] = input_value
                tenant = self.store_tenant(clone_schema_from=clone_schema_from,
                                           clone_tenant_fields=False,
                                           **tenant_data)
                if tenant is not None:
                    break
                tenant_data = {}

        while True:
            domain_data['tenant_id'] = tenant.id
            for field in self.domain_fields:
                if domain_data.get(field.attname, '') == '':
                    input_msg = field.verbose_name
                    default = field.get_default()
                    if default:
                        input_msg = "%s (leave blank to use '%s')" % (input_msg, default)

                    input_value = self._input(force_str('%s: ' % input_msg)) or default
                    domain_data[field.attname] = input_value
            domain = self.store_tenant_domain(**domain_data)
            if domain is not None:
                break
            domain_data = {}

    def store_tenant(self, clone_schema_from, clone_tenant_fields, **fields):

        connection.set_schema_to_public()
        try:
            if clone_tenant_fields:
                tenant = get_tenant_model().objects.get(schema_name=clone_schema_from)
                tenant.pk = None
                tenant.schema_name = fields['schema_name']
            else:
                tenant = get_tenant_model()(**fields)
            tenant.auto_create_schema = False
            tenant.save()
            clone_schema = CloneSchema()
            clone_schema.clone_schema(clone_schema_from, tenant.schema_name, set_connection=False)
            return tenant
        except exceptions.ValidationError as e:
            self.stderr.write("Error: %s" % '; '.join(e.messages))
            return None
        except IntegrityError as e:
            self.stderr.write("Error: " + str(e))
            return None

    def store_tenant_domain(self, **fields):
        try:
            domain = get_tenant_domain_model().objects.create(**fields)
            domain.save()
            return domain
        except exceptions.ValidationError as e:
            self.stderr.write("Error: %s" % '; '.join(e.messages))
            return None
        except IntegrityError as e:
            self.stderr.write("Error: " + str(e))
            return None
