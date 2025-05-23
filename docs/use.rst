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

You can delete tenants by just deleting the entry via the Django ORM. There is a flag that can set on the tenant model called ``auto_drop_schema``. The default for ``auto_drop_schema`` is False. 

WARNING SETTING ``AUTO_DROP_SCHEMA`` TO TRUE WILL DELETE THE SCHEMA WITH THE TENANT!


Utils
-----

There are several utils available in `django_tenants.utils` that can help you in writing more complicated applications.

.. function:: schema_context(schema_name)

This is a context manager. Database queries performed inside it will be executed in against the passed ``schema_name``. (with statement)

.. code-block:: python

    from django_tenants.utils import schema_context

    with schema_context(schema_name):
        # All commands here are ran under the schema `schema_name`

    # Restores the `SEARCH_PATH` to its original value

You can also use `schema_context` as a decorator.

.. code-block:: python

    from django_tenants.utils import schema_context

    @schema_context(schema_name)
    def my_func():
      # All commands in this function are ran under the schema `schema_name`

.. function:: tenant_context(tenant_object)

This context manager is very similar to the ``schema_context`` function,
but it takes a tenant model object as the argument instead.

.. code-block:: python

    from django_tenants.utils import tenant_context

    with tenant_context(tenant):
        # All commands here are ran under the schema from the `tenant` object

    # Restores the `SEARCH_PATH` to its original value

You can also use `tenant_context` as a decorator.

.. code-block:: python

    from django_tenants.utils import tenant_context

    @tenant_context(tenant)
    def my_func():
      # All commands in this function are ran under the schema from the `tenant` object

.. function:: @tenant_migration

This decorator allows the flexibility to have data migrations (using ``migrations.RunPython``) execute specifically under a tenant or public schema for apps in both tenant/public INSTALLED_APPS. 
It accepts boolean kwargs ``tenant_schema`` or ``public_schema`` - the default beign ``tenant_schema=True`` and ``public_schema=False``.

.. code-block:: python
    # <users/migrations/0012_datamigration.py>
    from django.db import migrations
    from django_tenants.utils import tenant_migration

    @tenant_migration
    def create_dummy_users(apps, schema_editor):
        User = apps.get_model("users", "User")
        User.objects.get_or_create(username='test_user1', email='test_user1@gmail.com')
        # creates user only in tenant schemas if migration is in app available in both public/tenant schemas

Signals
-------


There are number of signals

```post_schema_sync``` will get called after a schema gets created from the save method on the tenant class.

```schema_needs_to_be_sync``` will get called if the schema needs to be migrated. ```auto_create_schema``` (on the tenant model) has to be set to False for this signal to get called. This signal is very useful when tenants are created via a background process such as celery.

```schema_migrated``` will get called once migrations finish running for a schema.

```schema_pre_migration``` will get called just before migrations start running for a schema.

```schema_migrate_message``` will get called after each migration with the message of the migration. This signal is very useful when for process / status bars.

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

    @receiver(schema_pre_migration, sender=run_migrations)
    def handle_schema_pre_migration(sender, **kwargs):
        schema_name = kwargs['schema_name']

        # write some logs

    @receiver(schema_migrated, sender=run_migrations)
    def handle_schema_migrated(sender, **kwargs):
        schema_name = kwargs['schema_name']

        # recreate materialized views in the schema

    @receiver(schema_migrate_message, sender=run_migrations)
    def handle_schema_migrate_message(**kwargs):
        message = kwargs['message']
        # recreate materialized views in the schema


Multi-types tenants
-------------------

It is also possible to have different types of tenants. This is useful if you have two different types of users for instance you might want customers to use one style of tenant and suppliers to use another style. There is no limit to the amount of types however once the tenant has been set to a type it can't easily be converted to another type.
To enable multi types you need to change the setting file and add an extra field onto the tenant table.

In the setting file ```SHARED_APPS```, ```TENANT_APPS``` and ```PUBLIC_SCHEMA_URLCONF``` needs to be removed.

The following needs to be added to the setting file

.. code-block:: python

    HAS_MULTI_TYPE_TENANTS = True
    MULTI_TYPE_DATABASE_FIELD = 'type'  # or whatever the name you call the database field

    TENANT_TYPES = {
        "public": {  # this is the name of the public schema from get_public_schema_name
            "APPS": ['django_tenants',
                     'django.contrib.admin',
                     'django.contrib.auth',
                     'django.contrib.contenttypes',
                     'django.contrib.sessions',
                     'django.contrib.messages',
                     'django.contrib.staticfiles',
                      # shared apps here
                      ],
            "URLCONF": "tenant_multi_types_tutorial.urls_public", # url for the public type here
        },
        "type1": {
            "APPS": ['django.contrib.contenttypes',
                     'django.contrib.auth',
                     'django.contrib.admin',
                     'django.contrib.sessions',
                     'django.contrib.messages',
                     # type1 apps here
                     ],
            "URLCONF": "tenant_multi_types_tutorial.urls_type1",
        },
        "type2": {
            "APPS": ['django.contrib.contenttypes',
                     'django.contrib.auth',
                     'django.contrib.admin',
                     'django.contrib.sessions',
                     'django.contrib.messages',
                     # type1 apps here
                     ],
            "URLCONF": "tenant_multi_types_tutorial.urls_type2",
        }
    }

Now you need to change the install app line in the settings file

.. code-block:: python

    INSTALLED_APPS = []
    for schema in TENANT_TYPES:
        INSTALLED_APPS += [app for app in TENANT_TYPES[schema]["APPS"] if app not in INSTALLED_APPS]

You also need to make sure that ```ROOT_URLCONF``` is blank

.. code-block:: python
    ROOT_URLCONF = ''

The tenant tables needs to have the following field added to the model

.. code-block:: python

    from django_tenants.utils import get_tenant_type_choices

    class Client(TenantMixin):
        type = models.CharField(max_length=100, choices=get_tenant_type_choices())

That's all you need to add the multiple types.

There is an example project called ```tenant_multi_types```

Other settings
--------------

By default if no tenant is found it will raise an error Http404 however you add ```SHOW_PUBLIC_IF_NO_TENANT_FOUND``` to
the setting it will display the the public tenant. This will not work for subfolders.

```DEFAULT_NOT_FOUND_TENANT_VIEW``` If set, specifies a path to a view (function-based or class-based) that will handle requests when no tenant is found for the current domain. It uses the public schema `DEFAULT_NOT_FOUND_TENANT_VIEW='myapp.views.my_view'`

Admin
~~~~~

By default if you look at the admin all the tenant apps will be colored dark green you can disable this by doing.

.. code-block:: python

    TENANT_COLOR_ADMIN_APPS = False


Reverse
~~~~~~~

You can get the tenant domain name by calling a method on the tenant model called ``reverse``.


Management commands
-------------------
Every command except tenant_command runs by default on all tenants. You can also create your own commands that run on every tenant by inheriting ``BaseTenantCommand``. To run only a particular schema, there is an optional argument called ``--schema``.

Custom command example:

.. code-block:: python

    from django_tenants.management.commands import BaseTenantCommand
    # rest of your imports
    
    class Command(BaseTenantCommand):
        COMMAND_NAME = 'awesome command'
        # rest of your command

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

in case you're just switching your ``myapp`` application to use migrations.


Running the ``migrate`` will work however all it does is forward over to ``migrate_schemas``.



To run the migration only on the public tenant do the following.


.. code-block:: bash

    ./manage.py migrate_schemas --shared


To exlclude running migration on the public do the following


.. code-block:: bash

    ./manage.py migrate_schemas --tenant
 

To run only migration only on a single tenant run the following.

.. code-block:: bash
    
    python manage.py migrate --schema="demo"
    


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



all_tenants_command
~~~~~~~~~~~~~~~~~~~

To run any command on an every schema, you can use the special ``all_tenants_command``, which creates a wrapper around your command so that it run on every schema. For example

.. code-block:: bash

    ./manage.py all_tenants_command loaddata

If the command you need to run on all tenants should not be run on the public tenant, you can specify the ``--no-public`` flag which will exclude the public tenant.

.. code-block:: bash

    ./manage.py all_tenants_command --no-public loaddata



create_tenant_superuser
~~~~~~~~~~~~~~~~~~~~~~~

The command ``create_tenant_superuser`` is already automatically wrapped to have a ``schema`` flag. Create a new super user with

.. code-block:: bash

    ./manage.py create_tenant_superuser --username=admin --schema=customer1


create_tenant
~~~~~~~~~~~~~

The command ``create_tenant`` creates a new schema

.. code-block:: bash

    ./manage.py create_tenant --domain-domain=newtenant.net --schema_name=new_tenant --name=new_tenant --description="New tenant"

The argument are dynamic depending on the fields that are in the ``TenantMixin`` model.
For example if you have a field in the ``TenantMixin`` model called company you will be able to set this using --company=MyCompany.
If no argument are specified for a field then you be prompted for the values.
There is an additional argument of -s which sets up a superuser for that tenant.


delete_tenant
~~~~~~~~~~~~~

The command ``delete_tenant`` deletes a schema

.. code-block:: bash

    ./manage.py delete_tenant

Warning this command will delete a tenant and PostgreSQL schema regardless if ``auto_drop_schema`` is set to False.


clone_tenant
~~~~~~~~~~~~~

The command ``clone_tenant`` clones a schema.

.. code-block:: bash

    ./manage.py clone_tenant


There are some options to that can be set. You can view all the options by running

.. code-block:: bash

    ./manage.py clone_tenant -h

Credits to `pg-clone-schema <https://github.com/denishpatel/pg-clone-schema>`_.

rename_schema
~~~~~~~~~~~~~

The command ``rename_schema`` renames a schema in the db and updates the Client associated with it.

.. code-block:: bash

    ./manage.py rename_schema

It will prompt you for the current name of the schema, and what it should be renamed to.

You can provide them with these arguments:

.. code-block:: bash

    ./manage.py rename_schema --rename_from old_name --rename_to new_name

create_missing_schemas
~~~~~~~~~~~~~~~~~~~~~~

The command ``create_missing_schemas`` checks the tenant table against the list of schemas.
If it find a schema that doesn't exist it will create it.

.. code-block:: bash

    ./manage.py create_missing_schemas

create_domain
~~~~~~~~~~~~~

The command ``create_domain`` adds a domain to an existing tenant.

.. code-block:: bash

    ./manage.py create_domain     
    ./manage.py create_domain --schema_name=tenant1 --domain-domain=tenant1.my-domain.com
    ./manage.py create_domain -s=tenant1 -d=tenant1.my-domain.com --is_primary=True --no-input

delete_domain
~~~~~~~~~~~~~

The command ``delete_domain`` deletes a domain on a tenant.

.. code-block:: bash

    ./manage.py delete_domain     
    ./manage.py delete_domain --schema_name=tenant1 --domain-domain=tenant1.my-domain.com
    ./manage.py delete_domain -s=tenant1 -d=tenant1.my-domain.com

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

When set, ``django-tenants`` will set the search path only once per request. The default is ``False``.


Extra Set Tenant Method
-----------------------

Sometimes you might want to do something special when you switch to another schema / tenant such as read replica.
Add ``EXTRA_SET_TENANT_METHOD_PATH`` to the settings file and point a method.

.. code-block:: python

    EXTRA_SET_TENANT_METHOD_PATH = 'tenant_multi_types_tutorial.set_tenant_utils.extra_set_tenant_stuff'

The method
~~~~~~~~~~

The method takes 2 arguments the first is the database wrapper class and the second is the tenant.
example

.. code-block:: python

    def extra_set_tenant_stuff(wrapper_class, tenant):
        pass


Get Executor Function
-----------------------

Sometimes you might want to have some custom functionality with your migration executor.
Add ``GET_EXECUTOR_FUNCTION`` to the settings file and point a method.

.. code-block:: python

    GET_EXECUTOR_FUNCTION = 'tenant_multi_types_tutorial.set_tenant_utils.get_custom_executor'

The function
~~~~~~~~~~

The function takes 1 keyword argument (default=None) for the executor codename and returns a MigrationExector class.
example

.. code-block:: python
    from .custom_migration_executors import CustomMigrationExecutor
    from django_tenants.migrate_executors.standard import StandardExecutor

    def get_custom_executor(codename=None):
        codename = codename or os.environ.get('EXECUTOR', StandardExecutor.codename)

        for klass in MigrationExecutor.__subclasses__():
            if klass.codename == codename:
                return klass

        raise NotImplementedError('No executor with codename %s' % codename)


Logging
-------

The optional ``TenantContextFilter`` can be included in ``settings.LOGGING`` to add the current ``schema_name`` and ``domain_url`` to the logging context.

.. code-block:: python

    # settings.py
    LOGGING = {
        'filters': {
            'tenant_context': {
                '()': 'django_tenants.log.TenantContextFilter'
            },
        },
        'formatters': {
            'tenant_context': {
                'format': '[%(schema_name)s:%(domain_url)s] '
                '%(levelname)-7s %(asctime)s %(message)s',
            },
        },
        'handlers': {
            'console': {
                'filters': ['tenant_context'],
            },
        },
    }

This will result in logging output that looks similar to:

.. code-block:: text

    [example:example.com] DEBUG 13:29 django.db.backends: (0.001) SELECT ...


Get Tenant
----------

If you need to access the tenant object and have access to the request object you can do the following.

.. code-block:: python

    from django_tenants.utils import get_tenant
    ...
    tenant = get_tenant(request)

If no tenant is found None will be returned


Running in Development
----------------------

If you want to use django-tenant in development you need to use a fake a domain
name. All domains under the TLD ``.localhost`` will be routed to your local
machine, so you can use things like ``tenant1.localhost`` and ``tenant2.localhost``.

Migrating Single-Tenant to Multi-Tenant
---------------------------------------

.. warning::

    The following instructions may or may not work for you.
    Use at your own risk!

- Create a backup of your existing single-tenant database,
  presumably non PostgreSQL::

.. code-block:: bash

    ./manage.py dumpdata --all --indent 2 > database.json

- Edit ``settings.py`` to connect to your new PostrgeSQL database
- Execute ``manage.py migrate`` to create all tables in the PostgreSQL database
- Ensure newly created tables are empty::

.. code-block:: bash

    ./manage.py sqlflush | ./manage.py dbshell

- Load previously exported data into the database::

.. code-block:: bash

    ./manage.py loaddata --format json database.json

- Create the ``public`` tenant::

.. code-block:: bash

    ./manage.py create_tenant

At this point your application should be multi-tenant aware and you may proceed
creating more tenants.


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

Useful information
------------------

Running code across every tenant
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you want to run some code on every tenant you can do the following

.. code-block:: python

    from django_tenants.utils import tenant_context, get_tenant_model

    for tenant in get_tenant_model().objects.all():
        with tenant_context(tenant):
            pass
            # do whatever you want in that tenant
