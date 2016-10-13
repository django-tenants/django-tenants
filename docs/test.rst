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



Running tests faster
--------------------
Using the ``TenantTestCase`` can make running your tests really slow quite early in your project. This is due to the fact that it drops, recreates the test schema and runs migrations for every ``TenantTestCase`` you have. If you want to gain speed, there's a ``FastTenantTestCase`` where the test schema will be created and migrations ran only one time. The gain in speed is noticiable but be aware that by using this you will be perpertraiting state between your test cases, please make sure your they wont be affected by this.

Running tests using ``TenantTestCase`` can start being a bottleneck once the number of tests grow. If you do not care that the state between tests is kept, an alternative is to use the class ``FastTenantTestCase``. Unlike ``TenantTestCase``, the test schema and its migrations will only be created and ran once. This is a significant improvement in speed coming at the cost of shared state.

.. code-block:: python

    from django_tenants.test.cases import FastTenantTestCase


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



You can also change the test domain name and the test schema name by using ``get_test_schema_name`` and ``get_test_tenant_domain``.
by default the domain name is ``tenant.test.com`` and the schema name is ``test``.

.. code-block:: python

    from django_tenants.test.cases import TenantTestCase
    from django_tenants.test.client import TenantClient

    class BaseSetup(TenantTestCase):
        @staticmethod
        def get_test_tenant_domain():
            return 'tenant.my_domain.com'


        @staticmethod
        def get_test_schema_name():
            return 'tester'
