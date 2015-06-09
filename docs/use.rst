===========================
Using django-tenant-schemas
===========================
Creating a Tenant
-----------------
Creating a tenant works just like any other model in django. The first thing we should do is to create the ``public`` tenant to make our main website available. We'll use the previous model we defined for ``Client``.

.. code-block:: python

    from customers.models import Client

    # create your public tenant
    tenant = Client(domain_url='my-domain.com', # don't add your port or www here! on a local server you'll want to use localhost here
                    schema_name='public',
                    name='Schemas Inc.',
                    paid_until='2016-12-05',
                    on_trial=False)
    tenant.save()

Now we can create our first real tenant.

.. code-block:: python

    from customers.models import Client

    # create your first real tenant
    tenant = Client(domain_url='tenant.my-domain.com', # don't add your port or www here!
                    schema_name='tenant1',
                    name='Fonzy Tenant',
                    paid_until='2014-12-05',
                    on_trial=True)
    tenant.save() # sync_schemas automatically called, your tenant is ready to be used!
    
Because you have the tenant middleware installed, any request made to ``tenant.my-domain.com`` will now automatically set your PostgreSQL's ``search_path`` to ``tenant1, public``, making shared apps available too. The tenant will be made available at ``request.tenant``. By the way, the current schema is also available at ``connection.schema_name``, which is useful, for example, if you want to hook to any of django's signals. 

Any call to the methods ``filter``, ``get``, ``save``, ``delete`` or any other function involving a database connection will now be done at the tenant's schema, so you shouldn't need to change anything at your views.

Signals
-------


There are two signal one called ```post_schema_sync``` and the other called ```schema_needs_to_be_sync```

```post_schema_sync``` get called after the schema been migrated.

```schema_needs_to_be_sync``` get called if the schema needs to be migrated.


Management commands
-------------------
Every command except tenant_command runs by default on all tenants. You can also create your own commands that run on every tenant by inheriting ``BaseTenantCommand``. To run only a particular schema, there is an optional argument called ``--schema``.

.. code-block:: bash

    ./manage.py sync_schemas --schema=customer1

sync_schemas    
~~~~~~~~~~~~

The command ``sync_schemas`` is the most important command on this app. The way it works is that it calls Django's ``syncdb`` in two different ways. First, it calls ``syncdb`` for the ``public`` schema, only syncing the shared apps. Then it runs ``syncdb`` for every tenant in the database, this time only syncing the tenant apps.

.. warning::

   You should never directly call ``syncdb``. We perform some magic in order to make ``syncdb`` only sync the appropriate apps.

The options given to ``sync_schemas`` are passed to every ``syncdb``. So if you use South, you may find this handy

.. code-block:: bash

    ./manage.py sync_schemas --migrate

You can also use the option ``--tenant`` to only sync tenant apps or ``--shared`` to only sync shared apps.

.. code-block:: bash

    ./manage.py sync_schemas --shared # will only sync the public schema

migrate_schemas    
~~~~~~~~~~~~~~~

We've also packed south's migrate command in a compatible way with this app. It will also respect the ``SHARED_APPS`` and ``TENANT_APPS`` settings, so if you're migrating the ``public`` schema it will only migrate ``SHARED_APPS``. If you're migrating tenants, it will only migrate ``TENANT_APPS``.

.. code-block:: bash

    ./manage.py migrate_schemas

The options given to ``migrate_schemas`` are also passed to every ``migrate``. Hence you may find handy

.. code-block:: bash

    ./manage.py migrate_schemas --list

Or

.. code-block:: bash

    ./manage.py migrate_schemas myapp 0001_initial --fake

in case you're just switching your ``myapp`` application to use South migrations.

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



Performance Considerations
--------------------------

The hook for ensuring the ``search_path`` is set properly happens inside the ``DatabaseWrapper`` method ``_cursor()``, which sets the path on every database operation. However, in a high volume environment, this can take considerable time. A flag, ``TENANT_LIMIT_SET_CALLS``, is available to keep the number of calls to a minimum. The flag may be set in ``settings.py`` as follows:

.. code-block:: python

    #in settings.py:
    TENANT_LIMIT_SET_CALLS = True

When set, ``django-tenant-schemas`` will set the search path only once per request. The default is ``False``.


Third Party Apps
----------------
Support for Celery is available at `tenant-schemas-celery <https://github.com/maciej-gol/tenant-schemas-celery>`_.
