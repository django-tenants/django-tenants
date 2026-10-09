from django.core import exceptions
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db.utils import IntegrityError
from django.utils.encoding import force_str

from django_tenants.management.commands import TenantWrappedCommand, InteractiveTenantOption
from django_tenants.utils import get_tenant_model, get_tenant_domain_model


class Command(InteractiveTenantOption, BaseCommand):
    help = 'Create a domain on an existing tenant'

    # Only use editable fields
    # noinspection PyProtectedMember
    domain_fields = [field for field in get_tenant_domain_model()._meta.fields
                     if field.editable and not field.primary_key]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def add_arguments(self, parser):
        super().add_arguments(parser)

        for field in self.domain_fields:
            parser.add_argument('--domain-%s' % field.attname,
                                help="Specifies the %s for the tenant's domain." % field.attname)

        parser.add_argument(
            '--noinput', '--no-input', action='store_false', dest='interactive',
            help=(
                'Tells Django to NOT prompt the user for input of any kind. '
                'You must use --schema_names and --domain-domain with --noinput, along with an option for '
                'any other required field.'
            ),
        )

    def handle(self, *args, **options):
        # Pull the tenant and let the method validate we can continue
        tenant = self.get_tenant_from_options_or_interactive(**options)
        # Populate domain data from command line arguments
        domain_data = {}
        for field in self.domain_fields:
            input_value = options.get('domain_%s' % field.attname, None)
            if input_value is not None:
                domain_data[field.attname] = field.clean(input_value, None)

        domain_data['tenant_id'] = tenant.pk

        # When interactive, prompt for missing fields until all are provided
        if options['interactive']:
            while True:
                for field in self.domain_fields:
                    if domain_data.get(field.attname, '') == '':
                        input_msg = field.verbose_name
                        default = field.get_default()
                        if default:
                            input_msg = "%s (leave blank to use '%s')" % (input_msg, default)

                        input_value = input(force_str('%s: ' % input_msg)) or default
                        domain_data[field.attname] = input_value
                domain = self.store_tenant_domain(**domain_data)
                if domain is not None:
                    break
                domain_data = {}
        else:
            domain = self.store_tenant_domain(**domain_data)
            if domain is None:
                raise CommandError("Missing required domain fields")

    def store_tenant_domain(self, **fields):
        try:
            domain = get_tenant_domain_model().objects.create(**fields)
            domain.save()
            return domain
        except exceptions.ValidationError as e:
            self.stderr.write("Error: %s" % '; '.join(e.messages))
            return None
        except IntegrityError as e:
            self.stderr.write("Error: %s" % e.args)
            return None
