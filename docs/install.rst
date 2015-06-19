============
Installation
============
Assuming you have django installed, the first step is to install ``django-tenants``.

.. code-block:: bash

    pip install django-tenants

Basic Settings
==============
You'll have to make the following modifications to your ``settings.py`` file.

Your ``DATABASE_ENGINE`` setting needs to be changed to

.. code-block:: python

    DATABASES = {
        'default': {
            'ENGINE': 'django_tenants.postgresql_backend',
            # ..
        }
    }

Add `django_tenants.routers.TenantSyncRouter` to your `DATABASE_ROUTERS` setting, so that the correct apps can be synced, depending on what's being synced (shared or tenant).

.. code-block:: python

    DATABASE_ROUTERS = (
        'django_tenants.routers.TenantSyncRouter',
    )
    
Add the middleware ``django_tenants.middleware.TenantMiddleware`` to the top of ``MIDDLEWARE_CLASSES``, so that each request can be set to use the correct schema.

.. code-block:: python
    
    MIDDLEWARE_CLASSES = (
        'django_tenants.middleware.TenantMiddleware',
        #...
    )
    
Make sure you have ``django.core.context_processors.request`` listed under ``TEMPLATE_CONTEXT_PROCESSORS`` else the tenant will not be available on ``request``.

.. code-block:: python

    TEMPLATE_CONTEXT_PROCESSORS = (
        'django.core.context_processors.request',
        #...
    )
    
The Tenant & Domain Model
=========================
Now we have to create your tenant model.
 Your tenant model can contain whichever fields you want, however, you **must** inherit from ``TenantMixin``.
  This Mixin only has one field ``schema_name`` which is required.
   You also have to have a table for your domain names for this you use the you **must** inherit from ``DomainMixin`` .
    Here's an example, suppose we have an app named ``customers`` and we want to create a model called ``Client``.


.. code-block:: python

    from django.db import models
    from django_tenants.models import TenantMixin, DomainMixin
    
    class Client(TenantMixin):
        name = models.CharField(max_length=100)
        paid_until =  models.DateField()
        on_trial = models.BooleanField()
        created_on = models.DateField(auto_now_add=True)
        
        # default true, schema will be automatically created and synced when it is saved
        auto_create_schema = True

    class Domain(DomainMixin):
        pass

Configure Tenant and Shared Applications
========================================
To make use of shared and tenant-specific applications, there are two settings called ``SHARED_APPS`` and ``TENANT_APPS``. ``SHARED_APPS`` is a tuple of strings just like ``INSTALLED_APPS`` and should contain all apps that you want to be synced to ``public``. If ``SHARED_APPS`` is set, then these are the only apps that will be synced to your ``public`` schema! The same applies for ``TENANT_APPS``, it expects a tuple of strings where each string is an app. If set, only those applications will be synced to all your tenants. Here's a sample setting

.. code-block:: python

    SHARED_APPS = (
        'django_tenants',  # mandatory
        'customers', # you must list the app where your tenant model resides in
        
        'django.contrib.contenttypes',
         
        # everything below here is optional
        'django.contrib.auth', 
        'django.contrib.sessions', 
        'django.contrib.sites', 
        'django.contrib.messages', 
        'django.contrib.admin', 
    )
    
    TENANT_APPS = (
        # The following Django contrib apps must be in TENANT_APPS
        'django.contrib.contenttypes',

        # your tenant-specific apps
        'myapp.hotels',
        'myapp.houses', 
    )

    INSTALLED_APPS = list(set(SHARED_APPS + TENANT_APPS))

You also have to set where your tenant & domain models are located.

.. code-block:: python

    TENANT_MODEL = "customers.Client" # app.Model

    TENANT_DOMAIN_MODEL = "customers.Domain"  # app.Model

Now run ``migrate_schemas --shared``, this will create the shared apps on the ``public`` schema. Note: your database should be empty if this is the first time you're running this command.

.. code-block:: bash

    python manage.py migrate_schemas --shared
    
.. warning::

   Never use ``migrate`` or ``syncdb`` as it would sync *all* your apps to ``public``!
    
Lastly, you need to create a tenant whose schema is ``public`` and it's address is your domain URL. Please see the section on :doc:`use <use>`.

You can also specify extra schemas that should be visible to all queries using
``PG_EXTRA_SEARCH_PATHS`` setting.

.. code-block:: python

   PG_EXTRA_SEARCH_PATHS = ['extensions']

``PG_EXTRA_SEARCH_PATHS`` should be a list of schemas you want to make visible
globally.

.. tip::

   You can create a dedicated schema to hold postgresql extensions and make it
   available globally. This helps avoid issues caused by hiding the public
   schema from queries.

Optional Settings
=================

.. attribute:: PUBLIC_SCHEMA_NAME

    :Default: ``'public'``
    
    The schema name that will be treated as ``public``, that is, where the ``SHARED_APPS`` will be created.
    
.. attribute:: TENANT_CREATION_FAKES_MIGRATIONS

    :Default: ``'True'``
    
    Sets if the models will be synced directly to the last version and all migration subsequently faked. Useful in the cases where migrations can not be faked and need to be ran individually. Be aware that setting this to `False` may significantly slow down the process of creating tenants.


Tenant View-Routing
-------------------

.. attribute:: PUBLIC_SCHEMA_URLCONF

    :Default: ``None``

    We have a goodie called ``PUBLIC_SCHEMA_URLCONF``. Suppose you have your main website at ``example.com`` and a customer at ``customer.example.com``. You probably want your user to be routed to different views when someone requests ``http://example.com/`` and ``http://customer.example.com/``. Because django only uses the string after the host name, this would be impossible, both would call the view at ``/``. This is where ``PUBLIC_SCHEMA_URLCONF`` comes in handy. If set, when the ``public`` schema is being requested, the value of this variable will be used instead of `ROOT_URLCONF <https://docs.djangoproject.com/en/dev/ref/settings/#std:setting-ROOT_URLCONF>`_. So for example, if you have

    .. code-block:: python

        PUBLIC_SCHEMA_URLCONF = 'myproject.urls_public'
    
    When requesting the view ``/login/`` from the public tenant (your main website), it will search for this path on ``PUBLIC_SCHEMA_URLCONF`` instead of ``ROOT_URLCONF``. 

Separate projects for the main website and tenants (optional)
-------------------------------------------------------------
In some cases using the ``PUBLIC_SCHEMA_URLCONF`` can be difficult. For example, `Django CMS <https://www.django-cms.org/>`_ takes some control over the default Django URL routing by using middlewares that do not play well with the tenants. Another example would be when some apps on the main website need different settings than the tenants website. In these cases it is much simpler if you just run the main website `example.com` as a separate application. 

If your projects are ran using a WSGI configuration, this can be done by creating a filed called ``wsgi_main_website.py`` in the same folder as ``wsgi.py``.

.. code-block:: python

    # wsgi_main_website.py
    import os
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings_public")

    from django.core.wsgi import get_wsgi_application
    application = get_wsgi_application()

If you put this in the same Django project, you can make a new ``settings_public.py`` which points to a different ``urls_public.py``. This has the advantage that you can use the same apps that you use for your tenant websites.

Or you can create a completely separate project for the main website.

Configuring your Apache Server (optional)
=========================================
Here's how you can configure your Apache server to route all subdomains to your django project so you don't have to setup any subdomains manually.

.. code-block:: apacheconf

    <VirtualHost 127.0.0.1:8080>
        ServerName mywebsite.com
        ServerAlias *.mywebsite.com mywebsite.com
        WSGIScriptAlias / "/path/to/django/scripts/mywebsite.wsgi"
    </VirtualHost>

`Django's Deployment with Apache and mod_wsgi <https://docs.djangoproject.com/en/dev/howto/deployment/wsgi/modwsgi/>`_ might interest you too.

Building Documentation
======================
Documentation is available in ``docs`` and can be built into a number of 
formats using `Sphinx <http://pypi.python.org/pypi/Sphinx>`_. To get started

.. code-block:: bash

    pip install Sphinx
    cd docs
    make html

This creates the documentation in HTML format at ``docs/_build/html``.
