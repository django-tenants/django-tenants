from django.apps import apps
from django.db import connection
from django.test import TestCase
from django.test.utils import override_settings

from django_tenants.utils import get_public_schema_name


class TestSettings(TestCase):
    def tearDown(self):
        apps.unset_installed_apps()

        super().tearDown()

    @override_settings(PG_EXTRA_SEARCH_PATHS=['hstore'])
    def test_PG_EXTRA_SEARCH_PATHS(self):
        del apps.all_models['django_tenants']
        c = connection.cursor()
        c.execute('DROP SCHEMA {0} CASCADE; CREATE SCHEMA {0};'.format(
            get_public_schema_name()
        ))
        apps.set_installed_apps(['customers', 'django_tenants'])
