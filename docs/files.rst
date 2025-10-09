==========================
Tenant-aware file handling
==========================

The default Django behaviour is for all tenants to share **one** set of templates and static files between them. This can be changed so that each tenant will have its own:

- Static files (like cascading stylesheets and JavaScript)
- Location for files uploaded by users (usually stored in a */media* directory)
- Django templates

The process for making Django's file handling tenant-aware generally consists of the following steps:

1. Using a custom tenant-aware ``finder`` for locating files
2. Specifying where ``finders`` should look for files
3. Using a custom tenant-aware file ``storage`` handler for collecting and managing those files
4. Using a custom tenant-aware ``loader`` for finding and loading Django templates

We'll cover the configuration steps for each in turn.

Project layout
==============

This configuration guide assumes the following Django project layout (loosely based on django-cookiecutter):

.. code-block:: python

    absolute/path/to/your_project_dir
        ...
        static              # System-wide static files
        templates           # System-wide templates
        # Tenant-specific files below will override pre-existing system-wide files with same name.
        tenants
            tenant_1        # Static files / templates for tenant_1
                templates
                static
            tenant_2        # Static files / templates for tenant_2
                templates
                static
        media               # Created automatically when users upload files
            tenant_1
            tenant_2
    staticfiles             # Created automatically when collectstatic_schemas is run
        tenant_1
        tenant_2
        ...

The configuration details may differ depending on your specific requirements for your chosen layout. Fortunately, django-tenants makes it easy to cater for a wide range of project layouts as illustrated below.


Configuring the static file finders
-----------------------------------

Start by inserting django-tenants' ``django_tenants.staticfiles.finders.TenantFileSystemFinder`` at the top of the list of available ``STATICFILES_FINDERS`` in your Django configuration file:

.. code-block:: python

    # in settings.py

    STATICFILES_FINDERS = [
        "django_tenants.staticfiles.finders.TenantFileSystemFinder",  # Must be first
        "django.contrib.staticfiles.finders.FileSystemFinder",
        "django.contrib.staticfiles.finders.AppDirectoriesFinder",
        "compressor.finders.CompressorFinder",
    ]

    # or this way

    STATICFILES_FINDERS.insert(0, "django_tenants.staticfiles.finders.TenantFileSystemFinder")


By adding ``TenantFileSystemFinder`` at the top, we ensure that Django will look for the tenant-specific files first, before reverting to the standard search path. This makes it possible for tenants to *override* any static files (e.g. stylesheets or javascript files) that are specific to that tenant, and use the standard static files for the rest.

Next, add ``MULTITENANT_STATICFILES_DIRS`` to the configuration file in order to let ``TenantFileSystemFinder`` know where to look for tenant-specific static files:

.. code-block:: python

    # in settings.py

    MULTITENANT_STATICFILES_DIRS = [
        os.path.join( "absolute/path/to/your_project_dir", "tenants/%s/static" ),
    ]

For the path provided above, ``%s`` will be replaced with the current tenant's ``schema_name`` during runtime (see :ref:`target_dir` for details).

Configuring the static files storage
------------------------------------

By default, Django uses ``StaticFilesStorage`` for collecting static files into a dedicated folder on the server when the ``collectstatic`` management command is run. The location that the files are written to is specified in the ``STATIC_ROOT`` setting (usually configured to point to *'staticfiles'*).

django-tenants provides a replacement tenant-aware ``TenantStaticFilesStorage`` than can be configured by setting:

.. code-block:: python

    # in settings.py

    STATICFILES_STORAGE = "django_tenants.staticfiles.storage.TenantStaticFilesStorage"

    MULTITENANT_RELATIVE_STATIC_ROOT = ""  # (default: create sub-directory for each tenant)

The path specified in ``MULTITENANT_RELATIVE_STATIC_ROOT`` tells ``TenantStaticFilesStorage`` where in ``STATIC_ROOT`` the tenant's files should be saved. The default behaviour is to just create a sub-directory for each tenant in ``STATIC_ROOT``.

The command to collect the static files for all tenants is ``collectstatic_schemas``. The optional ``--schema`` argument can be used to only collect files for a single tenant.

.. code-block:: bash
    
    ./manage.py collectstatic_schemas --schema=your_tenant_schema_name

.. code-block:: bash

    ./manage.py collectstatic_schemas --all-schemas

.. note::

   If you have configured an HTTP server, like `nginx <https://nginx.org>`_, to serve static files instead of the
   Django built-in server, then you also need to set ``REWRITE_STATIC_URLS = True``. This tells django-tenants to
   rewrite ``STATIC_URL`` to include ``MULTITENANT_RELATIVE_STATIC_ROOT`` when static files are requested so that
   these files can be found and served directly by the external HTTP server.


Configuring media file storage
------------------------------

The default Django behavior is to store all files that are uploaded by users in one folder. The path for this upload folder can be configured via the standard ``MEDIA_ROOT`` setting.

The above behaviour can be changed for multi-tenant setups so that each tenant will have a dedicated sub-directory for storing user-uploaded files. To do this simply change ``DEFAULT_FILE_STORAGE`` so that ``TenantFileSystemStorage`` replaces the standard ``FileSystemStorage`` handler:

.. code-block:: python

    # in settings.py

    STORAGES = {
        "default": {
            "BACKEND": "django_tenants.files.storage.TenantFileSystemStorage",
        },
    }

    # OR, in the unlikely case you're using django < 4.2
    DEFAULT_FILE_STORAGE = "django_tenants.files.storage.TenantFileSystemStorage"

    MULTITENANT_RELATIVE_MEDIA_ROOT = ""  # (default: create sub-directory for each tenant)

The path specified in ``MULTITENANT_RELATIVE_MEDIA_ROOT`` tells ``TenantFileSystemStorage`` where in ``MEDIA_ROOT`` the tenant's files should be saved. The default behaviour is to just create a sub-directory for each tenant in ``MEDIA_ROOT``.

Configuring the template loaders
--------------------------------

django-tenants provides a tenant-aware template loader that uses the current tenant's ``schema_name`` when looking for templates.

It can be configured by inserting the custom ``Loader`` at the top of the list in the ``TEMPLATES`` setting, and specifying the template search path to be used in the ``MULTITENANT_TEMPLATE_DIRS`` setting, as illustrated below:

.. code-block:: python

    TEMPLATES = [
        {
            ...
            "DIRS": ["absolute/path/to/your_project_dir/templates"],  # -> Dirs used by the standard template loader
            "OPTIONS": {
                ...
                "loaders": [
                    "django_tenants.template.loaders.filesystem.Loader",  # Must be first
                    "django.template.loaders.filesystem.Loader",
                    "django.template.loaders.app_directories.Loader",
                ],
                ...
            ...
        }
    ]

    MULTITENANT_TEMPLATE_DIRS = [
        "absolute/path/to/your_project_dir/tenants/%s/templates"
    ]

Notice that ``django_tenants.template.loaders.filesystem.Loader`` is added at the top of the list. This will cause Django to look for the tenant-specific templates first, before reverting to the standard search path. This makes it possible for tenants to *override* individual templates as required.

Just like with standard Django, the first template found will be returned.

.. attention::

    If the template contains any `include tags <https://docs.djangoproject.com/en/2.1/ref/templates/builtins/#include>`_, then all of the included templates need to be located in the tenant's template folder as well. It is not currently possible to include templates from sources outside of the tenant's template folder.

.. _target_dir:

Specifying a different target directory
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

django-tenants supports simple Python string formatting for configuring the various path strings used throughout the configuration steps.  any occurrences of ``%s`` in the path string will be replaced with the current tenant's ``schema_name`` during runtime.

This makes it possible to cater for more elaborate folder structures. Some examples are provided below:


.. code-block:: python

    # in settings.py

    STATIC_ROOT = "absolute/path/to/your_project_dir/staticfiles"

    MULTITENANT_RELATIVE_STATIC_ROOT = "tenants/%s

Static files will be collected into -> absolute/path/to/your_project_dir/staticfiles/tenants/``schema_name``.

...and for media files:


.. code-block:: python

    # in settings.py

    MEDIA_ROOT = "absolute/path/to/your_project_dir/apps_dir/media/"

    MULTITENANT_RELATIVE_MEDIA_ROOT = "%s/other_dir"

Media files will be uploaded at -> absolute/path/to/your_project_dir/apps_dir/media/``schema_name``/other_dir
