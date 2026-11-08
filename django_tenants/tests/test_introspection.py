"""
Tests for ``DatabaseSchemaIntrospection``.

A tenant connection's search_path is the tenant's schema followed by public, so
Django's introspection queries, which look at the tables visible on the
search_path, would also describe the tables that exist only in the public
schema. The backend runs them with the search_path set to the connection's
schema alone, so that a tenant connection describes the tenant's tables and
nothing else.
"""

from django.db import connection

from django_tenants.tests.testcases import BaseTestCase
from django_tenants.utils import (
    get_public_schema_name,
    get_tenant_model,
    schema_context,
    tenant_context,
)

# Only in the tenant schema: dts_test_app is a tenant app. Its foreign key is to the
# tenant's own auth_user, since BaseTestCase makes auth a tenant app as well.
TENANT_TABLE = 'dts_test_app_modelwithfktopublicuser'
# Only in the public schema: customers is a shared app.
PUBLIC_TABLE = 'customers_domain'


def get_relations(cursor, table_name):
    # Django 6.1 added the ON DELETE action as a third element of each relation.
    return {
        column: relation[:2]
        for column, relation in connection.introspection.get_relations(cursor, table_name).items()
    }


class IntrospectionTest(BaseTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.sync_shared()

    def setUp(self):
        super().setUp()
        self.tenant = get_tenant_model()(schema_name='introspection_tenant')
        self.tenant.save()

    def tearDown(self):
        connection.set_schema_to_public()
        self.tenant.delete(force_drop=True)
        super().tearDown()

    def test_get_relations_returns_the_tenant_tables_foreign_keys(self):
        with tenant_context(self.tenant), connection.cursor() as cursor:
            cursor.execute('SHOW search_path')
            search_path = cursor.fetchone()[0]

            self.assertEqual(get_relations(cursor, TENANT_TABLE), {'user_id': ('id', 'auth_user')})

            cursor.execute('SHOW search_path')
            self.assertEqual(cursor.fetchone()[0], search_path)

    def test_get_relations_does_not_see_public_tables_from_a_tenant(self):
        with schema_context(get_public_schema_name()), connection.cursor() as cursor:
            self.assertEqual(get_relations(cursor, PUBLIC_TABLE), {'tenant_id': ('id', 'customers_client')})

        with tenant_context(self.tenant), connection.cursor() as cursor:
            # The other introspection methods do not see the public table either.
            self.assertNotIn(PUBLIC_TABLE, connection.introspection.table_names(cursor))
            self.assertEqual(connection.introspection.get_constraints(cursor, PUBLIC_TABLE), {})

            self.assertEqual(get_relations(cursor, PUBLIC_TABLE), {})
