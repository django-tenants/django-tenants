from django_tenants.cache import make_key
from django_tenants.test.cases import FastTenantTestCase


class TestFastTenant(FastTenantTestCase):
    """
    Test fast tenants more tests needed.
    """

    def test_fast1(self):
        key = make_key(key='foo', key_prefix='', version=1)
        tenant_prefix = key.split(':')[0]
        self.assertEqual(self.tenant.schema_name, tenant_prefix)

    def test_fast2(self):
        key = make_key(key='foo', key_prefix='', version=1)
        tenant_prefix = key.split(':')[0]
        self.assertEqual(self.tenant.schema_name, tenant_prefix)
