import os
from contextlib import ContextDecorator

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import connections, DEFAULT_DB_ALIAS, connection

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


def get_limit_set_calls():
    return getattr(settings, 'TENANT_LIMIT_SET_CALLS', False)


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


class schema_context(ContextDecorator):
    def __init__(self, *args, **kwargs):
        self.schema_name = args[0]
        super().__init__()

    def __enter__(self):
        self.connection = connections[get_tenant_database_alias()]
        self.previous_tenant = connection.tenant
        self.connection.set_schema(self.schema_name)

    def __exit__(self, *exc):
        if self.previous_tenant is None:
            self.connection.set_schema_to_public()
        else:
            self.connection.set_tenant(self.previous_tenant)


class tenant_context(schema_context):
    def __init__(self, *args, **kwargs):
        super().__init__(args[0].schema_name, **kwargs)


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


def app_labels(apps_list):
    """
    Returns a list of app labels of the given apps_list
    """
    return [app.split('.')[-1] for app in apps_list]


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
