import unittest

from django.core.exceptions import ValidationError

from django_tenants.postgresql_backend import base
from django_tenants.utils import quote_schema_name


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

    def test_check_schema_name_with_quote_or_statement_characters_is_invalid(self):
        for schema_name in ("tenant1', 'other", 'tenant1"; DROP SCHEMA other; --',
                            'tenant1\\', 'tenant1;', 'tenant\x001', 'tenant1\n'):
            with self.subTest(schema_name=schema_name):
                with self.assertRaisesRegex(ValidationError,
                                            'Invalid string used for the schema name.'):
                    base._check_schema_name(schema_name)

    def test_quote_schema_name_escapes_double_quotes(self):
        self.assertEqual(quote_schema_name('Tenant 1'), '"Tenant 1"')
        self.assertEqual(quote_schema_name('a"b'), '"a""b"')

    def test_quote_schema_name_rejects_nul(self):
        with self.assertRaises(ValidationError):
            quote_schema_name('a\x00b')
