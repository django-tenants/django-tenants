import os
from contextlib import ContextDecorator
from functools import lru_cache, wraps
from types import ModuleType

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import DEFAULT_DB_ALIAS, connection, connections
from django.utils.module_loading import import_string

try:
    from django.apps import apps
    get_model = apps.get_model
except ImportError:
    from django.db.models.loading import get_model

from django.core import mail


def get_tenant_model():
    return get_model(settings.TENANT_MODEL)


def get_tenant_domain_model():
    return get_model(settings.TENANT_DOMAIN_MODEL)


def get_tenant_database_alias():
    return getattr(settings, 'TENANT_DB_ALIAS', DEFAULT_DB_ALIAS)


def get_public_schema_name():
    return getattr(settings, 'PUBLIC_SCHEMA_NAME', 'public')


def get_tenant_types():
    return getattr(settings, 'TENANT_TYPES', {})


def get_tenant_base_migrate_command_class():
    class_path = getattr(
        settings,
        'TENANT_BASE_MIGRATE_COMMAND',
        'django.core.management.commands.migrate.Command',
    )
    return import_string(class_path)


def has_multi_type_tenants():
    return getattr(settings, 'HAS_MULTI_TYPE_TENANTS', False)


def get_multi_type_database_field_name():
    return getattr(settings, 'MULTI_TYPE_DATABASE_FIELD', '')


def get_public_schema_urlconf():
    if has_multi_type_tenants():
        return get_tenant_types()[get_public_schema_name()]['URLCONF']
    else:
        return getattr(settings, 'PUBLIC_SCHEMA_URLCONF', 'urls_public')


def get_tenant_type_choices():
    """This is to allow a choice field for the type of tenant"""
    if not has_multi_type_tenants():
        assert False, 'get_tenant_type_choices should only be used for multi type tenants'

    tenant_types = get_tenant_types()

    return [(k, k) for k in tenant_types.keys()]


def get_limit_set_calls():
    return getattr(settings, 'TENANT_LIMIT_SET_CALLS', False)


def get_subfolder_prefix():
    subfolder_prefix = getattr(settings, 'TENANT_SUBFOLDER_PREFIX', '') or ''
    return subfolder_prefix.strip('/ ')


def get_creation_fakes_migrations():
    """
    If TENANT_CREATION_FAKES_MIGRATIONS, tenants will be created by cloning an
    existing schema specified by TENANT_CLONE_BASE.
    """
    faked = getattr(settings, 'TENANT_CREATION_FAKES_MIGRATIONS', False)
    if faked:
        if not getattr(settings, 'TENANT_BASE_SCHEMA', False):
            raise ImproperlyConfigured(
                'You must specify a schema name in TENANT_BASE_SCHEMA if '
                'TENANT_CREATION_FAKES_MIGRATIONS is enabled.'
            )
    return faked


def get_tenant_base_schema():
    """
    If TENANT_CREATION_FAKES_MIGRATIONS, tenants will be created by cloning an
    existing schema specified by TENANT_CLONE_BASE.
    """
    schema = getattr(settings, 'TENANT_BASE_SCHEMA', False)
    if schema:
        if not getattr(settings, 'TENANT_CREATION_FAKES_MIGRATIONS', False):
            raise ImproperlyConfigured(
                'TENANT_CREATION_FAKES_MIGRATIONS setting must be True to use '
                'TENANT_BASE_SCHEMA for cloning.'
            )
    return schema


def get_tenant_migration_order():
    return getattr(settings, 'TENANT_MIGRATION_ORDER', None)


class schema_context(ContextDecorator):
    # Please do not try and merge this with tenant_context as they are not the same. As pointed out in #501
    def __init__(self, *args, **kwargs):
        self.schema_name = args[0]
        self.database = kwargs.get("database", get_tenant_database_alias())
        super().__init__()

    def __enter__(self):
        self.connection = connections[self.database]
        self.previous_tenant = connection.tenant
        self.connection.set_schema(self.schema_name)

    def __exit__(self, *exc):
        if self.previous_tenant is None:
            self.connection.set_schema_to_public()
        else:
            self.connection.set_tenant(self.previous_tenant)


class tenant_context(ContextDecorator):
    # Please do not try and merge this with schema_context as they are not the same. As pointed out in #501
    def __init__(self, *args, **kwargs):
        self.tenant = args[0]
        self.database = kwargs.get("database", get_tenant_database_alias())
        super().__init__()

    def __enter__(self):
        self.connection = connections[self.database]
        self.previous_tenant = connection.tenant
        self.connection.set_tenant(self.tenant)

    def __exit__(self, *exc):
        if self.previous_tenant is None:
            self.connection.set_schema_to_public()
        else:
            self.connection.set_tenant(self.previous_tenant)


def clean_tenant_url(url_string):
    """
    Removes the TENANT_TOKEN from a particular string
    """
    if hasattr(settings, 'PUBLIC_SCHEMA_URLCONF'):
        if (settings.PUBLIC_SCHEMA_URLCONF and
                url_string.startswith(settings.PUBLIC_SCHEMA_URLCONF)):
            url_string = url_string[len(settings.PUBLIC_SCHEMA_URLCONF):]
    return url_string


def remove_www_and_dev(hostname):
    """
    Legacy function - just in case someone is still using the old name
    """
    return remove_www(hostname)


def remove_www(hostname):
    """
    Removes www. from the beginning of the address. Only for
    routing purposes. www.test.com/login/ and test.com/login/ should
    find the same tenant.
    """
    if hostname.startswith("www."):
        return hostname[4:]

    return hostname


def django_is_in_test_mode():
    """
    I know this is very ugly! I'm looking for more elegant solutions.
    See: http://stackoverflow.com/questions/6957016/detect-django-testing-mode
    """
    return hasattr(mail, 'outbox')


def schema_exists(schema_name, database=get_tenant_database_alias()):
    _connection = connections[database]
    cursor = _connection.cursor()

    # check if this schema already exists in the db
    sql = 'SELECT EXISTS(SELECT 1 FROM pg_catalog.pg_namespace WHERE LOWER(nspname) = LOWER(%s))'
    cursor.execute(sql, (schema_name, ))

    row = cursor.fetchone()
    if row:
        exists = row[0]
    else:
        exists = False

    cursor.close()

    return exists


def schema_rename(tenant, new_schema_name, database=get_tenant_database_alias(), save=True):
    """
    This renames a schema to a new name. It checks to see if it exists first
    """
    from django_tenants.postgresql_backend.base import is_valid_schema_name
    _connection = connections[database]
    cursor = _connection.cursor()

    if schema_exists(new_schema_name):
        raise ValidationError("New schema name already exists")
    if not is_valid_schema_name(new_schema_name):
        raise ValidationError("Invalid string used for the schema name.")
    sql = 'ALTER SCHEMA {0} RENAME TO {1}'.format(connection.ops.quote_name(tenant.schema_name),
                                                  connection.ops.quote_name(new_schema_name))
    cursor.execute(sql)
    cursor.close()
    tenant.schema_name = new_schema_name
    if save:
        tenant.save()


@lru_cache(maxsize=128)
def get_app_label(app):
    from django.apps import apps  # Ensure app registry is imported

    candidate = app.split(".")[-1]

    try:
        imported_app = import_string(app)
    except ImportError:
        return candidate

    app_name = app if isinstance(imported_app, ModuleType) else imported_app.name

    app_label = [
        app_config.label
        for app_config in apps.get_app_configs()
        if app_config.name == app_name
    ]

    if len(app_label) != 1:
        return candidate

    return app_label[0]


def app_labels(apps_list):
    """
    Returns a list of app labels of the given apps_list
    """
    return [get_app_label(app) for app in apps_list]


def parse_tenant_config_path(config_path):
    """
    Convenience function for parsing django-tenants' path configuration strings.

    If the string contains '%s', then the current tenant's schema name will be inserted at that location. Otherwise
    the schema name will be appended to the end of the string.

    :param config_path: A configuration path string that optionally contains '%s' to indicate where the tenant
    schema name should be inserted.

    :return: The formatted string containing the schema name
    """
    try:
        # Insert schema name
        return config_path % connection.schema_name
    except (TypeError, ValueError):
        # No %s in string; append schema name at the end
        return os.path.join(config_path, connection.schema_name)


def validate_extra_extensions():
    skip_validation = getattr(settings, 'SKIP_PG_EXTRA_VALIDATION', False)
    extra_extensions = getattr(settings, 'PG_EXTRA_SEARCH_PATHS', [])

    if not skip_validation and extra_extensions:
        if get_public_schema_name() in extra_extensions:
            raise ImproperlyConfigured(
                "%s can not be included on PG_EXTRA_SEARCH_PATHS."
                % get_public_schema_name())

        # make sure no tenant schema is in settings.PG_EXTRA_SEARCH_PATHS

        # first check that the model table is created
        model = get_tenant_model()
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT 1 FROM information_schema.tables WHERE table_name = %s;',
                [model._meta.db_table]
            )
            if cursor.fetchone():
                invalid_schemas = set(extra_extensions).intersection(
                    model.objects.all().values_list('schema_name', flat=True))
                if invalid_schemas:
                    raise ImproperlyConfigured(
                        "Do not include tenant schemas (%s) on PG_EXTRA_SEARCH_PATHS."
                        % list(invalid_schemas))

        # Make sure the connection used for the check is not reused and doesn't stay idle.
        connection.close()


def tenant_migration(*args, tenant_schema=True, public_schema=False):
    """
    Decorator to control which schemas a data migration will execute on.
    
    :param tenant_schema: If True (default), the data migration will execute on the tenant schema(s).
    :param public_schema: If True, the data migration will execute on the public schema.

    :return: None
    """

    def _tenant_migration(func):
        @wraps(func)
        def wrapper(*_args, **kwargs):
            try:
                _, schema_editor = _args  # noqa
            except Exception as excp:
                raise Exception(f'Decorator requires apps & schema_editor as positional arguments: {excp}')

            if ((tenant_schema and schema_editor.connection.schema_name != get_public_schema_name()) or
                    (public_schema and schema_editor.connection.schema_name == get_public_schema_name())):
                func(*_args, **kwargs)

        return wrapper

    if len(args) == 1 and callable(args[0]):
        return _tenant_migration(args[0])

    return _tenant_migration


def get_tenant(request):
    """This gets the tenant object from the request"""
    if hasattr(request, 'tenant'):
        return request.tenant
    return None
