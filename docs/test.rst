=====
Tests
=====
Running the tests
-----------------
Run these tests from the project ``dts_test_project``, it comes prepacked with the correct settings file and extra apps to enable tests to ensure different apps can exist in ``SHARED_APPS`` and ``TENANT_APPS``.

.. code-block:: bash

    ./manage.py test django_tenants.tests

If you want to run with custom migration executor then do

.. code-block:: bash

    EXECUTOR=multiprocessing ./manage.py test django_tenants.tests

Updating your app's tests to work with django_tenants
-----------------------------------------------------
Because django will not create tenants for you during your tests, we have packed some custom test cases and other utilities. If you want a test to happen at any of the tenant's domain, you can use the test case ``TenantTestCase``. It will automatically create a tenant for you, set the connection's schema to tenant's schema and make it available at ``self.tenant``. We have also included a ``TenantRequestFactory`` and a ``TenantClient`` so that your requests will all take place at the tenant's domain automatically. Here's an example

.. code-block:: python

    from django_tenants.test.cases import TenantTestCase
    from django_tenants.test.client import TenantClient

    class BaseSetup(TenantTestCase):

        def setUp(self):
            super(BaseSetup, self).setUp()
            self.c = TenantClient(self.tenant)
            
        def test_user_profile_view(self):
            response = self.c.get(reverse('user_profile'))
            self.assertEqual(response.status_code, 200)


Additional information
----------------------

You may have other fields on your tenant or domain model which are required fields.
If you have there are two routines to look at ``setup_tenant`` and ``setup_domain``

.. code-block:: python

    from django_tenants.test.cases import TenantTestCase
    from django_tenants.test.client import TenantClient

    class BaseSetup(TenantTestCase):

        def setup_tenant(self, tenant):
            """
            Add any additional setting to the tenant before it get saved. This is required if you have
            required fields.
            """
            tenant.company_name = "Test Company"

        def setup_domain(self, tenant):
            """
            Add any additional setting to the domain before it get saved. This is required if you have
            required fields.
            """
            domain.ssl = True

        def setUp(self):
            super(BaseSetup, self).setUp()
            self.c = TenantClient(self.tenant)

        def test_user_profile_view(self):
            response = self.c.get(reverse('user_profile'))
            self.assertEqual(response.status_code, 200)
