import unittest

from django.core.exceptions import ValidationError

from django_tenants.mysql_backend import base


class TestMySQLValidationUtils(unittest.TestCase):
    def test_check_schema_name_with_valid_name(self):
        self.assertIsNone(base._check_schema_name('tenant1'))

    def test_check_schema_name_underscore_is_valid(self):
        self.assertIsNone(base._check_schema_name('tenant_1'))

    def test_check_schema_name_upper_case_is_valid(self):
        self.assertIsNone(base._check_schema_name('Tenant1'))

    def test_check_schema_name_hyphen_is_valid(self):
        self.assertIsNone(base._check_schema_name('my-tenant'))

    def test_check_schema_name_64_chars_is_valid(self):
        schema_name = 'a' * 64
        self.assertIsNone(base._check_schema_name(schema_name))

    def test_check_schema_name_65_chars_is_invalid(self):
        schema_name = 'a' * 65
        with self.assertRaisesRegex(ValidationError,
                                    'Invalid string used for the schema name.'):
            base._check_schema_name(schema_name)

    def test_check_schema_name_with_slash_is_invalid(self):
        with self.assertRaisesRegex(ValidationError,
                                    'Invalid string used for the schema name.'):
            base._check_schema_name('tenant/1')

    def test_check_schema_name_with_backslash_is_invalid(self):
        with self.assertRaisesRegex(ValidationError,
                                    'Invalid string used for the schema name.'):
            base._check_schema_name('tenant\\1')

    def test_check_schema_name_with_dot_is_invalid(self):
        with self.assertRaisesRegex(ValidationError,
                                    'Invalid string used for the schema name.'):
            base._check_schema_name('tenant.1')

    def test_check_schema_name_with_backtick_is_invalid(self):
        with self.assertRaisesRegex(ValidationError,
                                    'Invalid string used for the schema name.'):
            base._check_schema_name('tenant`1')

    def test_check_schema_name_with_trailing_space_is_invalid(self):
        with self.assertRaisesRegex(ValidationError,
                                    'Invalid string used for the schema name.'):
            base._check_schema_name('tenant1 ')

    def test_check_schema_name_empty_is_invalid(self):
        with self.assertRaisesRegex(ValidationError,
                                    'Invalid string used for the schema name.'):
            base._check_schema_name('')
