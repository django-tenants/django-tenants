django-tenants
==============
.. image:: https://badges.gitter.im/Join%20Chat.svg
   :alt: Join the chat at https://gitter.im/django-tenants
   :target: https://gitter.im/django-tenants/Lobby?utm_source=share-link&utm_medium=link&utm_campaign=share-link

.. image:: https://badge.fury.io/py/django-tenants.svg
    :target: http://badge.fury.io/py/django-tenants

.. image:: https://github.com/tomturner/django-tenants/workflows/code/badge.svg
    :alt: Build status
    :target: https://github.com/tomturner/django-tenants/actions

.. image:: https://readthedocs.org/projects/pip/badge/?version=latest
    :target: https://django-tenants.readthedocs.io/en/latest/

This application enables `django`_ powered websites to have multiple
tenants via `PostgreSQL schemas`_. A vital feature for every
Software-as-a-Service (SaaS) website.

    Read the full documentaion here: `django-tenants.readthedocs.org`_

Django provides currently no simple way to support multiple tenants
using the same project instance, even when only the data is different.
Because we don’t want you running many copies of your project, you’ll be
able to have:

-  Multiple customers running on the same instance
-  Shared and Tenant-Specific data
-  Tenant View-Routing



What are schemas
----------------

A schema can be seen as a directory in an operating system, each
directory (schema) with it’s own set of files (tables and objects). This
allows the same table name and objects to be used in different schemas
without conflict. For an accurate description on schemas, see
`PostgreSQL’s official documentation on schemas`_.

Why schemas
-----------

There are typically three solutions for solving the multitenancy
problem.

1. Isolated Approach: Separate Databases. Each tenant has it’s own
   database.

2. Semi Isolated Approach: Shared Database, Separate Schemas. One
   database for all tenants, but one schema per tenant.

3. Shared Approach: Shared Database, Shared Schema. All tenants share
   the same database and schema. There is a main tenant-table, where all
   other tables have a foreign key pointing to.

This application implements the second approach, which in our opinion,
represents the ideal compromise between simplicity and performance.

-  Simplicity: barely make any changes to your current code to support
   multitenancy. Plus, you only manage one database.
-  Performance: make use of shared connections, buffers and memory.

Each solution has it’s up and down sides, for a more in-depth
discussion, see Microsoft’s excellent article on `Multi-Tenant Data
Architecture`_.

How it works
------------

Tenants are identified via their host name (i.e tenant.domain.com). This
information is stored on a table on the ``public`` schema. Whenever a
request is made, the host name is used to match a tenant in the
database. If there’s a match, the search path is updated to use this
tenant’s schema. So from now on all queries will take place at the
tenant’s schema. For example, suppose you have a tenant ``customer`` at
http://customer.example.com. Any request incoming at
``customer.example.com`` will automatically use ``customer``\ ’s schema
and make the tenant available at the request. If no tenant is found, a
404 error is raised. This also means you should have a tenant for your
main domain, typically using the ``public`` schema. For more information
please read the `setup`_ section.

What can this app do?
---------------------

As many tenants as you want
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Each tenant has its data on a specific schema. Use a single project
instance to serve as many as you want.

Tenant-specific and shared apps
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tenant-specific apps do not share their data between tenants, but you
can also have shared apps where the information is always available and
shared between all.

Tenant View-Routing
~~~~~~~~~~~~~~~~~~~

You can have different views for ``http://customer.example.com/`` and
``http://example.com/``, even though Django only uses the string after
the host name to identify which view to serve.

Magic
~~~~~

Everyone loves magic! You’ll be able to have all this barely having to
change your code!

Setup & Documentation
---------------------

**This is just a short setup guide**, it is **strongly** recommended
that you read the complete version at
`django-tenants.readthedocs.org`_.

Your ``DATABASE_ENGINE`` setting needs to be changed to

.. code-block:: python

    DATABASES = {
        'default': {
            'ENGINE': 'django_tenants.postgresql_backend',
            # ..
        }
    }    

Add the middleware ``django_tenants.middleware.main.TenantMainMiddleware`` to the
top of ``MIDDLEWARE``, so that each request can be set to use
the correct schema.

.. code-block:: python

    MIDDLEWARE = (
        'django_tenants.middleware.main.TenantMainMiddleware',
        #...
    )
    
Add ``django_tenants.routers.TenantSyncRouter`` to your `DATABASE_ROUTERS`
setting, so that the correct apps can be synced, depending on what's 
being synced (shared or tenant).

.. code-block:: python

    DATABASE_ROUTERS = (
        'django_tenants.routers.TenantSyncRouter',
    )

Add ``django_tenants`` to your ``INSTALLED_APPS``.

Create your tenant model
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    from django.db import models
    from django_tenants.models import TenantMixin, DomainMixin

    class Client(TenantMixin):
        name = models.CharField(max_length=100)
        paid_until =  models.DateField()
        on_trial = models.BooleanField()
        created_on = models.DateField(auto_now_add=True)

    class Domain(DomainMixin):
        pass

Define on ``settings.py`` which model is your tenant model. Assuming you
created ``Client`` inside an app named ``customers``, your
``TENANT_MODEL`` should look like this:

.. code-block:: python

    TENANT_MODEL = "customers.Client" # app.Model
    TENANT_DOMAIN_MODEL = "customers.Domain" # app.Model

Now run ``migrate_schemas``, this will sync your apps to the ``public``
schema.

.. code-block:: bash

    python manage.py migrate_schemas --shared

Create your tenants just like a normal django model. Calling ``save``
will automatically create and sync the schema.

.. code-block:: python

    from customers.models import Client, Domain

    # create your public tenant
    tenant = Client(schema_name='tenant1',
                    name='My First Tenant',
                    paid_until='2014-12-05',
                    on_trial=True)
    tenant.save()

    # Add one or more domains for the tenant
    domain = Domain()
    domain.domain = 'tenant.my-domain.com'
    domain.tenant = tenant
    domain.is_primary = True
    domain.save()

Any request made to ``tenant.my-domain.com`` will now automatically set
your PostgreSQL’s ``search_path`` to ``tenant1`` and ``public``, making
shared apps available too. This means that any call to the methods
``filter``, ``get``, ``save``, ``delete`` or any other function
involving a database connection will now be done at the tenant’s schema,
so you shouldn’t need to change anything at your views.

You’re all set, but we have left key details outside of this short
tutorial, such as creating the public tenant and configuring shared and
tenant specific apps. Complete instructions can be found at
`django-tenants.readthedocs.org`_.



Running the example project
---------------------------

django-tenants comes with an example project please see

`examples`_.


Credits
-------

I would like to thank two of the original authors of this project.

1. Bernardo Pires under the name `django-tenant-schemas`_.

2. Vlada Macek under the name of `django-schemata`_.

Requirements
------------

 - Django 2 if you want to use Django 1.11 or lower please use version 1 of django-tenants
 - PostgreSQL

Testing
-------

If you want to run test you can either run ``run_tests.sh`` (which requires access to
a PostgreSQL instance, location of which you can customize using the ``DATABASE_HOST``
env variable) or use `docker-compose`_ like this:

.. code-block:: bash

    ## Start Docker service
    # start docker   # with Upstart
    # systemctl start docker  # with systemd

    ## Install docker-compose (you might want to do this in Python virtualenv)
    # pip install docker-compose

    ## In main directory of this repo do:
    docker-compose up postgres  # starts dockerized PostgreSQL service
    docker-compose run django-tenants-test  # runs django-tenants tests

(note that upon first run the ``Dockerfile`` will be built).

Video Tutorial
--------------

An online video tutorial is available on `youtube`_.

Donation
--------

If this project help you reduce time to develop, you can give me cake :)

.. image:: https://www.paypalobjects.com/en_US/i/btn/btn_donateCC_LG.gif
  :target: https://www.paypal.com/cgi-bin/webscr?cmd=_s-xclick&hosted_button_id=QU8BGC7DWB9G6&source=ur


.. _youtube: https://youtu.be/NsWlUMTfIFo
.. _django: https://www.djangoproject.com/
.. _PostgreSQL schemas: http://www.postgresql.org/docs/9.1/static/ddl-schemas.html
.. _PostgreSQL’s official documentation on schemas: http://www.postgresql.org/docs/9.1/static/ddl-schemas.html
.. _Multi-Tenant Data Architecture: https://web.archive.org/web/20160311212239/https://msdn.microsoft.com/en-us/library/aa479086.aspx
.. _setup: https://django-tenants.readthedocs.org/en/latest/install.html
.. _examples: https://django-tenants.readthedocs.org/en/latest/examples.html
.. _django-tenants.readthedocs.org: https://django-tenants.readthedocs.org/en/latest/
.. _django-tenant-schemas: http://github.com/bernardopires/django-tenant-schemas
.. _django-schemata: https://github.com/tuttle/django-schemata
.. _docker-compose: https://docs.docker.com/engine/reference/run/
