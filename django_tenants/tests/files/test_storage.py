import os
import shutil
import tempfile
import warnings

from django.db import connection
from django.core.files.base import ContentFile

from django_tenants import utils
from django_tenants.files.storage import TenantFileSystemStorage
from django_tenants.files.storages import (
    TenantFileSystemStorage as OldTenantFileSystemStorage,
)
from django_tenants.tests.testcases import BaseTestCase


class TenantFileSystemStorageTestCase(BaseTestCase):
    storage_class = TenantFileSystemStorage

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.storage = self.storage_class(
            location="{}/{}".format(self.temp_dir, connection.schema_name), base_url="/test_media_url/"
        )
        # Set up a second temporary directory which is ensured to have a mixed
        # case name.
        self.temp_dir2 = tempfile.mkdtemp(suffix="aBc")

    def tearDown(self):
        shutil.rmtree(self.temp_dir)
        shutil.rmtree(self.temp_dir2)

    def test_deprecated_module_raises_warning(self):
        with warnings.catch_warnings(record=True) as warns:
            deprecation_warning = (
                "TenantFileSystemStorage has been moved from django_tenants.files.storages "
                "to django_tenants.files.storage."
            )

            OldTenantFileSystemStorage()
            self.assertTrue(any(deprecation_warning in str(w.message) for w in warns))

    def test_file_path(self):
        """
        File storage returns the full path of a file
        """
        self.assertFalse(self.storage.exists("test.file"))

        f = ContentFile("custom contents")
        f_name = self.storage.save("test.file", f)

        self.assertEqual(
            os.path.join(self.temp_dir, connection.schema_name, f_name),
            self.storage.path(f_name),
        )

        self.storage.delete(f_name)

    def test_file_save_with_path(self):
        """
        Saving a pathname should create intermediate directories as necessary.
        """
        self.assertFalse(self.storage.exists("path/to"))
        self.storage.save("path/to/test.file", ContentFile("file saved with path"))

        self.assertTrue(self.storage.exists("path/to"))
        with self.storage.open("path/to/test.file") as f:
            self.assertEqual(f.read(), b"file saved with path")

        self.assertTrue(
            os.path.exists(
                os.path.join(
                    self.temp_dir, connection.schema_name, "path", "to", "test.file"
                )
            )
        )

        self.storage.delete("path/to/test.file")

    def test_file_url(self):
        """
        File storage returns a url to access a given file from the Web.
        """
        self.assertEqual(
            self.storage.url("test.file"), self.storage.base_url + "test.file"
        )

        # should encode special chars except ~!*()'
        # like encodeURIComponent() JavaScript function do
        self.assertEqual(
            self.storage.url(r"~!*()'@#$%^&*abc`+ =.file"),
            "/test_media_url/{}/~!*()'%40%23%24%25%5E%26*abc%60%2B%20%3D.file".format(connection.schema_name),
        )
        self.assertEqual(
            self.storage.url("ab\0c"),
            "/test_media_url/{}/ab%00c".format(connection.schema_name),
        )

        # should translate os path separator(s) to the url path separator
        self.assertEqual(
            self.storage.url("""a/b\\c.file"""),
            "/test_media_url/{}/a/b/c.file".format(connection.schema_name),
        )

        # remove leading slashes from file names to prevent unsafe url output
        self.assertEqual(
            self.storage.url("/evil.com"),
            "/test_media_url/{}/evil.com".format(connection.schema_name),
        )
        self.assertEqual(
            self.storage.url(r"\evil.com"),
            "/test_media_url/{}/evil.com".format(connection.schema_name),
        )
        self.assertEqual(
            self.storage.url("///evil.com"),
            "/test_media_url/{}/evil.com".format(connection.schema_name),
        )
        self.assertEqual(
            self.storage.url(r"\\\evil.com"),
            "/test_media_url/{}/evil.com".format(connection.schema_name),
        )

        self.assertEqual(
            self.storage.url(None), "/test_media_url/{}/".format(connection.schema_name)
        )

    def test_base_url(self):
        """
        File storage returns a url even when its base_url is unset or modified.
        """
        self.storage._base_url = None

        # This standard Django test is no longer relevant since we don't make use of @cached_property
        # with self.assertRaises(ValueError):
        #     self.storage.url('test.file')

        self.assertEqual(
            self.storage.url("test.file"), "/{}/test.file".format(connection.schema_name)
        )

        # missing ending slash in base_url should be auto-corrected
        storage = self.storage_class(
            location=self.temp_dir, base_url="/no_ending_slash"
        )
        self.assertEqual(
            storage.url("test.file"), "%s%s" % (storage.base_url, "test.file")
        )

    def test_files_are_saved_under_subdirectories_per_tenant(self):
        # Create new tenants
        tenant1 = utils.get_tenant_model()(schema_name="tenant1")
        tenant1.save()

        domain1 = utils.get_tenant_domain_model()(
            tenant=tenant1, domain="something.test.com"
        )
        domain1.save()

        tenant2 = utils.get_tenant_model()(schema_name="tenant2")
        tenant2.save()

        domain2 = utils.get_tenant_domain_model()(tenant=tenant2, domain="example.com")
        domain2.save()

        connection.set_schema_to_public()

        # This file should be saved on the public schema
        public_file_name = self.storage.save("hello_world.txt", ContentFile("Hello World"))
        public_os_path = self.storage.path(public_file_name)
        public_url = self.storage.url(public_file_name)

        # Switch to tenant1
        with utils.tenant_context(tenant1):
            storage = self.storage_class(
                location="{}/{}".format(self.temp_dir, connection.schema_name), base_url="/test_media_url/"
            )
            t1_file_name = storage.save("hello_from_1.txt", ContentFile("Hello T1"))
            t1_os_path = storage.path(t1_file_name)
            t1_url = storage.url(t1_file_name)

        # Switch to tenant2
        with utils.tenant_context(tenant2):
            storage = self.storage_class(
                location="{}/{}".format(self.temp_dir, connection.schema_name), base_url="/test_media_url/"
            )
            t2_file_name = storage.save("hello_from_2.txt", ContentFile("Hello T2"))
            t2_os_path = storage.path(t2_file_name)
            t2_url = storage.url(t2_file_name)

        # Assert the paths are correct
        self.assertTrue(
            public_os_path.endswith("public/%s" % public_file_name)
        )
        self.assertTrue(t1_os_path.endswith("tenant1/%s" % t1_file_name))
        self.assertTrue(t2_os_path.endswith("tenant2/%s" % t2_file_name))

        # Assert urls are correct
        self.assertEqual(public_url, "/test_media_url/public/%s" % public_file_name)
        self.assertEqual(t1_url, "/test_media_url/tenant1/%s" % t1_file_name)
        self.assertEqual(t2_url, "/test_media_url/tenant2/%s" % t2_file_name)

        # Assert contents are correct
        with open(public_os_path, "r") as f:
            self.assertEqual(f.read(), "Hello World")

        with open(t1_os_path, "r") as f:
            self.assertEqual(f.read(), "Hello T1")

        with open(t2_os_path, "r") as f:
            self.assertEqual(f.read(), "Hello T2")
