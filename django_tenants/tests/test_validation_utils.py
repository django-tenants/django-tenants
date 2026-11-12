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

    def test_check_schema_name_with_path_traversal_is_invalid(self):
        for schema_name in ('x/../victim', '../../app', '..', '.', 'a/b', '/abs'):
            with self.subTest(schema_name=schema_name):
                with self.assertRaisesRegex(ValidationError,
                                            'Invalid string used for the schema name.'):
                    base._check_schema_name(schema_name)

    def test_check_schema_name_with_dots_is_valid(self):
        for schema_name in ('a.b', '.hidden', '...', 'tenant.'):
            with self.subTest(schema_name=schema_name):
                self.assertIsNone(base._check_schema_name(schema_name))

    def test_check_schema_name_over_63_bytes_is_invalid(self):
        # 33 characters but 64 bytes: PostgreSQL would truncate it to the
        # 63-byte name of another tenant.
        for schema_name in ('\u00e9' * 31 + 'ab', '\u00e9' * 32, '\U0001f600' * 16):
            with self.subTest(schema_name=schema_name):
                self.assertGreater(len(schema_name.encode('utf-8')), 63)
                with self.assertRaisesRegex(ValidationError,
                                            'Invalid string used for the schema name.'):
                    base._check_schema_name(schema_name)

    def test_check_schema_name_63_bytes_is_valid(self):
        for schema_name in ('\u00e9' * 31 + 'a', 'a' * 63, 'caf\u00e9'):
            with self.subTest(schema_name=schema_name):
                self.assertIsNone(base._check_schema_name(schema_name))

    def test_check_schema_name_lone_surrogate_is_invalid(self):
        with self.assertRaises(ValidationError):
            base._check_schema_name('tenant\ud800')

    def test_quote_schema_name_escapes_double_quotes(self):
        self.assertEqual(quote_schema_name('Tenant 1'), '"Tenant 1"')
        self.assertEqual(quote_schema_name('a"b'), '"a""b"')

    def test_quote_schema_name_rejects_nul(self):
        with self.assertRaises(ValidationError):
            quote_schema_name('a\x00b')
