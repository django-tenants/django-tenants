import unittest

from django.core.exceptions import ValidationError

from django_tenants.postgresql_backend import base


class TestValidationUtils(unittest.TestCase):
    def test_check_schema_name_with_valid_name(self):
        self.assertIsNone(base._check_schema_name('tenant1'))

    def test_check_schema_name_underscore_is_valid(self):
        self.assertIsNone(base._check_schema_name('tenant_1'))

    def test_check_schema_name_upper_case_is_valid(self):
        self.assertIsNone(base._check_schema_name('Tenant1'))

    def test_check_schema_name_hyphen_is_valid(self):
        self.assertIsNone(base._check_schema_name('my-tenant'))

    def test_check_schema_name_64_is_invalid(self):
        schema_name = 'aaatenant7890tenant7890tenant7890tenant7890tenant7890tenant7890z'
        self.assertGreater(len(schema_name), 63)

        with self.assertRaisesRegex(ValidationError,
                                    'Invalid string used for the schema name.'):
            base._check_schema_name(schema_name)

    def test_check_schema_name_starting_with_pg_is_invalid(self):
        with self.assertRaisesRegex(ValidationError,
                                    'Invalid string used for the schema name.'):
            base._check_schema_name('pg_tenant1')
