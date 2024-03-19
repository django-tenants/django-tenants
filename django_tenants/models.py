from django.conf import settings
from django.contrib.sites.shortcuts import get_current_site
from django.core.management import call_command
from django.db import models, connections, transaction
from django.urls import reverse

from django_tenants.clone import CloneSchema
from .postgresql_backend.base import _check_schema_name
from .signals import post_schema_sync, schema_needs_to_be_sync
from .utils import get_creation_fakes_migrations, get_tenant_base_schema
from .utils import schema_exists, get_tenant_domain_model, get_public_schema_name, get_tenant_database_alias


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

    clone_mode = "DATA"
    """
    One of "DATA", "NODATA".
    When using TENANT_BASE_SCHEMA, controls whether only the database
    structure will be copied, or if data will be copied along with it.
    """

    schema_name = models.CharField(max_length=63, unique=True, db_index=True,
                                   validators=[_check_schema_name])

    domain_url = None
    """
    Leave this as None. Stores the current domain url so it can be used in the logs
    """
    domain_subfolder = None
    """
    Leave this as None. Stores the subfolder in subfolder routing was used
    """

    _previous_tenant = []

    class Meta:
        abstract = True

    def __str__(self):
        return self.schema_name

    def __enter__(self):
        """
        Syntax sugar which helps in celery tasks, cron jobs, and other scripts

        Usage:
            with Tenant.objects.get(schema_name='test') as tenant:
                # run some code in tenant test
            # run some code in previous tenant (public probably)
        """
        connection = connections[get_tenant_database_alias()]
        self._previous_tenant.append(connection.tenant)
        self.activate()

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        connection = connections[get_tenant_database_alias()]

        connection.set_tenant(self._previous_tenant.pop())

    def activate(self):
        """
        Syntax sugar that helps at django shell with fast tenant changing

        Usage:
            Tenant.objects.get(schema_name='test').activate()
        """
        connection = connections[get_tenant_database_alias()]
        connection.set_tenant(self)

    @classmethod
    def deactivate(cls):
        """
        Syntax sugar, return to public schema

        Usage:
            test_tenant.deactivate()
            # or simpler
            Tenant.deactivate()
        """
        connection = connections[get_tenant_database_alias()]
        connection.set_schema_to_public()

    def save(self, verbosity=1, *args, **kwargs):
        connection = connections[get_tenant_database_alias()]
        is_new = self._state.adding
        has_schema = hasattr(connection, 'schema_name')
        if has_schema and is_new and connection.schema_name != get_public_schema_name():
            raise Exception("Can't create tenant outside the public schema. "
                            "Current schema is %s." % connection.schema_name)
        elif has_schema and not is_new and connection.schema_name not in (self.schema_name, get_public_schema_name()):
            raise Exception("Can't update tenant outside it's own schema or "
                            "the public schema. Current schema is %s."
                            % connection.schema_name)

        super().save(*args, **kwargs)

        if has_schema and is_new and self.auto_create_schema:
            try:
                self.create_schema(check_if_exists=True, verbosity=verbosity)
                post_schema_sync.send(sender=TenantMixin, tenant=self.serializable_fields())
            except Exception:
                # We failed creating the tenant, delete what we created and
                # re-raise the exception
                self.delete(force_drop=True)
                raise
        elif is_new:
            # although we are not using the schema functions directly, the signal might be registered by a listener
            schema_needs_to_be_sync.send(sender=TenantMixin, tenant=self.serializable_fields())
        elif not is_new and self.auto_create_schema and not schema_exists(self.schema_name):
            # Create schemas for existing models, deleting only the schema on failure
            try:
                self.create_schema(check_if_exists=True, verbosity=verbosity)
                post_schema_sync.send(sender=TenantMixin, tenant=self.serializable_fields())
            except Exception:
                # We failed creating the schema, delete what we created and
                # re-raise the exception
                self._drop_schema()
                raise

    def serializable_fields(self):
        """ in certain cases the user model isn't serializable so you may want to only send the id """
        return self

    def _drop_schema(self, force_drop=False):
        """ Drops the schema"""
        connection = connections[get_tenant_database_alias()]
        has_schema = hasattr(connection, 'schema_name')
        if has_schema and connection.schema_name not in (self.schema_name, get_public_schema_name()):
            raise Exception("Can't delete tenant outside it's own schema or "
                            "the public schema. Current schema is %s."
                            % connection.schema_name)

        if has_schema and schema_exists(self.schema_name) and (self.auto_drop_schema or force_drop):
            self.pre_drop()
            cursor = connection.cursor()
            cursor.execute('DROP SCHEMA "%s" CASCADE' % self.schema_name)

    def pre_drop(self):
        """
        This is a routine which you could override to backup the tenant schema before dropping.
        :return:
        """

    def delete(self, force_drop=False, *args, **kwargs):
        """
        Deletes this row. Drops the tenant's schema if the attribute
        auto_drop_schema set to True.
        """
        self._drop_schema(force_drop)
        return super().delete(*args, **kwargs)

    def create_schema(self, check_if_exists=False, sync_schema=True,
                      verbosity=1):
        """
        Creates the schema 'schema_name' for this tenant. Optionally checks if
        the schema already exists before creating it. Returns true if the
        schema was created, false otherwise.
        """

        # safety check
        connection = connections[get_tenant_database_alias()]
        _check_schema_name(self.schema_name)
        cursor = connection.cursor()

        if check_if_exists and schema_exists(self.schema_name):
            return False

        fake_migrations = get_creation_fakes_migrations()

        if sync_schema:
            if fake_migrations:
                # copy tables and data from provided model schema
                base_schema = get_tenant_base_schema()
                clone_schema = CloneSchema()
                clone_schema.clone_schema(
                    base_schema, self.schema_name, self.clone_mode
                )

                call_command('migrate_schemas',
                             tenant=True,
                             fake=True,
                             schema_name=self.schema_name,
                             interactive=False,
                             verbosity=verbosity)
            else:
                # create the schema
                cursor.execute('CREATE SCHEMA "%s"' % self.schema_name)
                call_command('migrate_schemas',
                             tenant=True,
                             schema_name=self.schema_name,
                             interactive=False,
                             verbosity=verbosity)

        connection.set_schema_to_public()

    def get_primary_domain(self):
        """
        Returns the primary domain of the tenant
        """
        try:
            domain = self.domains.get(is_primary=True)
            return domain
        except get_tenant_domain_model().DoesNotExist:
            return None

    def reverse(self, request, view_name):
        """
        Returns the URL of this tenant.
        """
        http_type = 'https://' if request.is_secure() else 'http://'

        domain = get_current_site(request).domain

        url = ''.join((http_type, self.schema_name, '.', domain, reverse(view_name)))

        return url

    def get_tenant_type(self):
        """
        Get the type of tenant. Will only work for multi type tenants
        :return: str
        """
        return getattr(self, settings.MULTI_TYPE_DATABASE_FIELD)


class DomainMixin(models.Model):
    """
    All models that store the domains must inherit this class
    """
    domain = models.CharField(max_length=253, unique=True, db_index=True)
    tenant = models.ForeignKey(settings.TENANT_MODEL, db_index=True, related_name='domains',
                               on_delete=models.CASCADE)

    # Set this to true if this is the primary domain
    is_primary = models.BooleanField(default=True, db_index=True)

    @transaction.atomic
    def save(self, *args, **kwargs):
        # Get all other primary domains with the same tenant
        domain_list = self.__class__.objects.filter(tenant=self.tenant, is_primary=True).exclude(pk=self.pk)
        # If we have no primary domain yet, set as primary domain by default
        self.is_primary = self.is_primary or (not domain_list.exists())
        if self.is_primary:
            # Remove primary status of existing domains for tenant
            domain_list.update(is_primary=False)
        super().save(*args, **kwargs)

    class Meta:
        abstract = True

    def __str__(self):
        return self.domain
