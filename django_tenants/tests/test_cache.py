
from django_tenants.cache import make_key, reverse_key
from django_tenants.test.cases import TenantTestCase


class CacheHelperTestCase(TenantTestCase):
    def test_make_key(self):
        key = make_key(key='foo', key_prefix='', version=1)
        tenant_prefix = key.split(':')[0]
        self.assertEqual(self.tenant.schema_name, tenant_prefix)

    def test_reverse_key(self):
        key = 'foo'
        self.assertEqual(key, reverse_key(make_key(key=key, key_prefix='', version=1)))
