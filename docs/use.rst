====================
Using django-tenants
====================
Creating a Tenant
-----------------
Creating a tenant works just like any other model in django. The first thing we should do is to create the ``public`` tenant to make our main website available. We'll use the previous model we defined for ``Client``.

.. code-block:: python

    from customers.models import Client, Domain

    # create your public tenant
    tenant = Client(schema_name='public',
                    name='Schemas Inc.',
                    paid_until='2016-12-05',
                    on_trial=False)
    tenant.save()

    # Add one or more domains for the tenant
    domain = Domain()
    domain.domain = 'my-domain.com' # don't add your port or www here! on a local server you'll want to use localhost here
    domain.tenant = tenant
    domain.is_primary = True
    domain.save()

Now we can create our first real tenant.

.. code-block:: python

    from customers.models import Client, Domain

    # create your first real tenant
    tenant = Client(schema_name='tenant1',
                    name='Fonzy Tenant',
                    paid_until='2014-12-05',
                    on_trial=True)
    tenant.save() # migrate_schemas automatically called, your tenant is ready to be used!

    # Add one or more domains for the tenant
    domain = Domain()
    domain.domain = 'tenant.my-domain.com' # don't add your port or www here!
    domain.tenant = tenant
    domain.is_primary = True
    domain.save()

Because you have the tenant middleware installed, any request made to ``tenant.my-domain.com`` will now automatically set your PostgreSQL's ``search_path`` to ``tenant1, public``, making shared apps available too. The tenant will be made available at ``request.tenant``. By the way, the current schema is also available at ``connection.schema_name``, which is useful, for example, if you want to hook to any of django's signals. 

Any call to the methods ``filter``, ``get``, ``save``, ``delete`` or any other function involving a database connection will now be done at the tenant's schema, so you shouldn't need to change anything at your views.

Deleting a tenant
-----------------

You can delete tenants by just deleting the entry via the Django ORM. There is a flag that can set on the tenant model called ``auto_drop_schema``. The default for ``auto_drop_schema`` is False. WARNING SETTING ``AUTO_DROP_SCHEMA`` TO TRUE WITH DELETE WITH TENANT!


Signals
-------


There are two signal one called ```post_schema_sync``` and the other called ```schema_needs_to_be_sync```

```post_schema_sync``` will get called after the schema been migrated.

```schema_needs_to_be_sync``` will get called if the schema needs to be migrated. ```auto_create_schema``` (on the tenant model) has to be set to False for this signal to get called. This signal is very useful when tenants are created via a background process such as celery.

Example

.. code-block:: python

    @receiver(schema_needs_to_be_sync, sender=TenantMixin)
    def created_user_client_in_background(sender, **kwargs):
        client = kwargs['tenant']
        print ("created_user_client_in_background %s" % client.schema_name)
        from clients.tasks import setup_tenant
        task = setup_tenant.delay(client)

    @receiver(post_schema_sync, sender=TenantMixin)
    def created_user_client(sender, **kwargs):

        client = kwargs['tenant']

        # send email to client to as tenant is ready to use

Management commands
-------------------
Every command except tenant_command runs by default on all tenants. You can also create your own commands that run on every tenant by inheriting ``BaseTenantCommand``. To run only a particular schema, there is an optional argument called ``--schema``.

.. code-block:: bash

    ./manage.py migrate_schemas --schema=customer1

migrate_schemas    
~~~~~~~~~~~~~~~

We've also packed the django migrate command in a compatible way with this app. It will also respect the ``SHARED_APPS`` and ``TENANT_APPS`` settings, so if you're migrating the ``public`` schema it will only migrate ``SHARED_APPS``. If you're migrating tenants, it will only migrate ``TENANT_APPS``.

.. code-block:: bash

    ./manage.py migrate_schemas

The options given to ``migrate_schemas`` are also passed to every ``migrate``. Hence you may find handy

.. code-block:: bash

    ./manage.py migrate_schemas --list

Or

.. code-block:: bash

    ./manage.py migrate_schemas myapp 0001_initial --fake

in case you're just switching your ``myapp`` application to use South migrations.


migrate_schemas in Parallel
~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can run tenant migrations in parallel like this:

.. code-block:: bash

    python manage.py migrate_schemas --executor=multiprocessing

In fact, you can write your own executor which will run tenant migrations in
any way you want, just take a look at ``django_tenants/migration_executors``.

The ``multiprocessing`` executor accepts the following settings:

* ``TENANT_MULTIPROCESSING_MAX_PROCESSES`` (default: 2) - maximum number of
  processes for migration pool (this is to avoid exhausting the database
  connection pool)
* ``TENANT_MULTIPROCESSING_CHUNKS`` (default: 2) - number of migrations to be
  sent at once to every worker


tenant_command    
~~~~~~~~~~~~~~

To run any command on an individual schema, you can use the special ``tenant_command``, which creates a wrapper around your command so that it only runs on the schema you specify. For example

.. code-block:: bash

    ./manage.py tenant_command loaddata

If you don't specify a schema, you will be prompted to enter one. Otherwise, you may specify a schema preemptively

.. code-block:: bash

    ./manage.py tenant_command loaddata --schema=customer1
    
create_tenant_superuser
~~~~~~~~~~~~~~~~~~~~~~~

The command ``create_tenant_superuser`` is already automatically wrapped to have a ``schema`` flag. Create a new super user with

.. code-block:: bash

    ./manage.py create_tenant_superuser --username='admin' --schema=customer1


create_tenant   
~~~~~~~~~~~~~

The command ``create_tenant`` creates a new schema

.. code-block:: bash

    ./manage.py create_tenant --domain_url=newtenant.net --schema_name=new_tenant --name=new_tenant --description="New tenant"

The argument are dynamic depending on the fields that are in the ``TenantMixin`` model.
For example if you have a field in the ``TenantMixin`` model called company you will be able to set this using --company=MyCompany.
If no argument are specified for a field then you be promted for the values.
There is an additional argument of -s which sets up a superuser for that tenant.

PostGIS
-------

If you want to run PostGIS add the following to your Django settings file

.. code-block:: python

    ORIGINAL_BACKEND = "django.contrib.gis.db.backends.postgis"


Performance Considerations
--------------------------

The hook for ensuring the ``search_path`` is set properly happens inside the ``DatabaseWrapper`` method ``_cursor()``, which sets the path on every database operation. However, in a high volume environment, this can take considerable time. A flag, ``TENANT_LIMIT_SET_CALLS``, is available to keep the number of calls to a minimum. The flag may be set in ``settings.py`` as follows:

.. code-block:: python

    #in settings.py:
    TENANT_LIMIT_SET_CALLS = True

When set, ``django-tenant-schemas`` will set the search path only once per request. The default is ``False``.


Running in Development
----------------------

If you want to use django-tenant in development you will have to fake a domain name. You can do this by editing the hosts file or using a program such as ``Acrylic DNS Proxy (Windows)``.


Third Party Apps
----------------

Celery
~~~~~~

Support for Celery is available at `tenant-schemas-celery <https://github.com/maciej-gol/tenant-schemas-celery>`_.


django-debug-toolbar
~~~~~~~~~~~~~~~~~~~~

`django-debug-toolbar <https://github.com/django-debug-toolbar/django-debug-toolbar>`_ routes need to be added to urls.py (both public and tenant) manually.

.. code-block:: python

    from django.conf import settings
    from django.conf.urls import include

    if settings.DEBUG:
        import debug_toolbar

        urlpatterns += patterns(
            '',
            url(r'^__debug__/', include(debug_toolbar.urls)),
        )
