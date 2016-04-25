from django.conf import settings
from django.db import models, transaction, connections, DEFAULT_DB_ALIAS
from django.core.management import call_command

from .postgresql_backend.base import _check_schema_name
from .signals import post_schema_sync, schema_needs_to_be_sync
from .utils import schema_exists, get_tenant_domain_model
from .utils import get_public_schema_name

public_db = connections[DEFAULT_DB_ALIAS]
tenant_db = connections[settings.TENANT_DATABASE]


class TenantMixin(models.Model):
    """
    All tenant models must inherit this class.
    """

    auto_drop_schema = False
    """
    USE THIS WITH CAUTION!
    Set this flag to true on a parent class if you want the schema to be
    automatically deleted if the tenant row gets deleted.
    """

    auto_create_schema = True
    """
    Set this flag to false on a parent class if you don't want the schema
    to be automatically created upon save.
    """

    schema_name = models.CharField(max_length=63, unique=True,
                                   validators=[_check_schema_name])

    class Meta:
        abstract = True

    def __enter__(self):
        """
        Syntax sugar which helps in celery tasks, cron jobs, and other scripts

        Usage:
            with Tenant.objects.get(schema_name='test') as tenant:
                # run some code in tenant test
            # run some code in previous tenant (public probably)
        """
        self._previous_tenant = tenant_db.tenant
        self.activate()

    def __exit__(self, exc_type, exc_val, exc_tb):
        tenant_db.set_tenant(self._previous_tenant)

    def activate(self):
        """
        Syntax sugar that helps at django shell with fast tenant changing

        Usage:
            Tenant.objects.get(schema_name='test').activate()
        """
        tenant_db.set_tenant(self)

    @classmethod
    def deactivate(cls):
        """
        Syntax sugar, return to public schema

        Usage:
            test_tenant.deactivate()
            # or simpler
            Tenant.deactivate()
        """
        tenant_db.set_schema_to_public()

    def save(self, verbosity=1, *args, **kwargs):
        is_new = self.pk is None

        if is_new and public_db.schema_name != get_public_schema_name():
            raise Exception("Can't create tenant outside the public schema. "
                            "Current schema is %s." % public_db.schema_name)
        elif not is_new and tenant_db not in (self.schema_name, get_public_schema_name()):
            raise Exception("Can't update tenant outside it's own schema or "
                            "the public schema. Current schema is %s."
                            % tenant_db.schema_name)

        super(TenantMixin, self).save(*args, **kwargs)

        if is_new and self.auto_create_schema:
            try:
                self.create_schema(check_if_exists=True, verbosity=verbosity)
                post_schema_sync.send(sender=TenantMixin, tenant=self)
            except Exception as e:
                # We failed creating the tenant, delete what we created and
                # re-raise the exception
                self.delete(force_drop=True)
                raise
        elif is_new:
            schema_needs_to_be_sync.send(sender=TenantMixin, tenant=self)

    def delete(self, force_drop=False, *args, **kwargs):
        """
        Deletes this row. Drops the tenant's schema if the attribute
        auto_drop_schema set to True.
        """
        if tenant_db.schema_name not in (self.schema_name, get_public_schema_name()):
            raise Exception("Can't delete tenant outside it's own schema or "
                            "the public schema. Current schema is %s."
                            % tenant_db.schema_name)

        if schema_exists(self.schema_name) and (self.auto_drop_schema or force_drop):
            cursor = tenant_db.cursor()
            cursor.execute('DROP SCHEMA %s CASCADE' % self.schema_name)

        super(TenantMixin, self).delete(*args, **kwargs)

    def create_schema(self, check_if_exists=False, sync_schema=True,
                      verbosity=1):
        """
        Creates the schema 'schema_name' for this tenant. Optionally checks if
        the schema already exists before creating it. Returns true if the
        schema was created, false otherwise.
        """

        # safety check
        _check_schema_name(self.schema_name)
        cursor = tenant_db.cursor()

        if check_if_exists and schema_exists(self.schema_name):
            return False

        # create the schema
        cursor.execute('CREATE SCHEMA %s' % self.schema_name)

        if sync_schema:
            call_command('migrate_schemas',
                         schema_name=self.schema_name,
                         interactive=False,
                         verbosity=verbosity)

        tenant_db.set_schema_to_public()

    def get_primary_domain(self):
        """
        Returns the primary domain of the tenant
        """
        try:
            domain = self.domains.get(is_primary=True)
            return domain
        except get_tenant_domain_model().DoesNotExist:
            return None


class DomainMixin(models.Model):
    """
    All models that store the domains must inherit this class
    """
    domain = models.CharField(max_length=253, unique=True, db_index=True)
    tenant = models.ForeignKey(settings.TENANT_MODEL, db_index=True, related_name='domains')

    # Set this to true if this is the primary domain
    is_primary = models.BooleanField(default=True)

    @transaction.atomic
    def save(self, *args, **kwargs):
        # Get all other primary domains with the same tenant
        domain_list = self.__class__.objects.filter(tenant=self.tenant, is_primary=True).exclude(pk=self.pk)
        # If we have no primary domain yet, set as primary domain by default
        self.is_primary = self.is_primary or (not domain_list.exists())
        if self.is_primary:
            # Remove primary status of existing domains for tenant
            domain_list.update(is_primary=False)
        super(DomainMixin, self).save(*args, **kwargs)

    class Meta:
        abstract = True
