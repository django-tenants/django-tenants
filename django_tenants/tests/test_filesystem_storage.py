import warnings

from django.conf import settings
from django.db import connection
from django.core.files.base import ContentFile

from django_tenants import utils
from django_tenants.files.storage import TenantFileSystemStorage
from django_tenants.files.storages import TenantFileSystemStorage as OldTenantFileSystemStorage
from django_tenants.test.cases import TenantTestCase


class TenantFileSystemStorageTestCase(TenantTestCase):
    def setUp(self):
        super().setUp()
        settings.MEDIA_ROOT = "apps_dir/media"
        settings.MEDIA_URL = "/media/"

    def test_deprecated_module_raises_warning(self):
        with warnings.catch_warnings(record=True) as warns:
            deprecation_warning = "TenantFileSystemStorage has been moved from django_tenants.files.storages " \
                                  "to django_tenants.files.storage."

            OldTenantFileSystemStorage()
            self.assertTrue(any(deprecation_warning in str(w.message) for w in warns))

    def test_files_are_saved_under_subdirectories_per_tenant(self):
        storage = TenantFileSystemStorage()

        connection.set_schema_to_public()
        tenant1 = utils.get_tenant_model()(schema_name='tenant1')
        tenant1.save()

        domain1 = utils.get_tenant_domain_model()(tenant=tenant1, domain='something.test.com')
        domain1.save()

        connection.set_schema_to_public()
        tenant2 = utils.get_tenant_model()(schema_name='tenant2')
        tenant2.save()

        domain2 = utils.get_tenant_domain_model()(tenant=tenant2, domain='example.com')
        domain2.save()

        # this file should be saved on the public schema
        public_file_name = storage.save('hello_world.txt', ContentFile('Hello World'))
        public_os_path = storage.path(public_file_name)
        public_url = storage.url(public_file_name)

        # switch to tenant1
        with utils.tenant_context(tenant1):
            t1_file_name = storage.save('hello_from_1.txt', ContentFile('Hello T1'))
            t1_os_path = storage.path(t1_file_name)
            t1_url = storage.url(t1_file_name)

        # switch to tenant2
        with utils.tenant_context(tenant2):
            t2_file_name = storage.save('hello_from_2.txt', ContentFile('Hello T2'))
            t2_os_path = storage.path(t2_file_name)
            t2_url = storage.url(t2_file_name)

        # assert the paths are correct
        self.assertTrue(public_os_path.endswith('apps_dir/media/public/%s' % public_file_name))
        self.assertTrue(t1_os_path.endswith('apps_dir/media/tenant1/%s' % t1_file_name))
        self.assertTrue(t2_os_path.endswith('apps_dir/media/tenant2/%s' % t2_file_name))

        # assert urls are correct
        self.assertEqual(public_url, '/media/public/%s' % public_file_name)
        self.assertEqual(t1_url, '/media/tenant1/%s' % t1_file_name)
        self.assertEqual(t2_url, '/media/tenant2/%s' % t2_file_name)

        # assert contents are correct
        with open(public_os_path, 'r') as f:
            self.assertEqual(f.read(), 'Hello World')

        with open(t1_os_path, 'r') as f:
            self.assertEqual(f.read(), 'Hello T1')

        with open(t2_os_path, 'r') as f:
            self.assertEqual(f.read(), 'Hello T2')
