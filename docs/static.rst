==============================================
Specializing static and media based on tenants
==============================================

Multitenant aware static and media files
----------------------------------------

If you need to have ``different static files for each tenant`` or ``upload media files to separate directories for each tenant``, you will need use the resourses bellow, otherwise the configurations bellow are not necessary. 

The classical Django ``FileSystemStorage`` and ``StaticFilesStorage`` cannot make the search path for files vary based on the current tenant so it's needed to use a special one which adapt the search path based on the tenant. For using it change your ``DEFAULT_FILE_STORAGE`` setting and also ``STATICFILES_STORAGE`` setting.

Static files finders aware tenant
---------------------------------

The classical Django ``FileSystemFinder`` cannot finder path for files vary based on the current tenant so it's needed to use a special one which find ours files based on the tenant.

To do this, first we need to structure our project so that each tenant stay separated into directories and thus we have a starting point to manipulate `templates files <templates.html>`_ and ``static files`` to each tenant:

.. code-block:: python

    STATICFILES_FINDERS = [
        'django_tenants.staticfiles.finders.TenantFileSystemFinder',  # first
        'django.contrib.staticfiles.finders.FileSystemFinder',
        'django.contrib.staticfiles.finders.AppDirectoriesFinder',
        'compressor.finders.CompressorFinder',
    ]

    # or this way

    STATICFILES_FINDERS.insert(0, "django_tenants.staticfiles.finders.TenantFileSystemFinder")

Let's imagine the following design structure:

.. code-block:: python

    your_project_dir
        ...
        tenants
            tenant_name_1  # -> same name schema_name_1
                templates
                static
            tenant_name_2  # -> same name schema_name_2
                templates
                static
        ...
        ...

To work with that structure we need tell where are the static files of each tenant, to do this, set the variable ``MULTITENANT_STATICFILES_DIRS`` in yours settings.py as bellow: 

.. code-block:: python

    # in settings.py

    MULTITENANT_STATICFILES_DIRS = [
        os.path.join( "absolute/path/your/project", 'tenants/%s/static' ),
    ]

.. tip::
    
    To work locally in your development environment unfortunately it is necessary to set the variable ``CURRENT_SCHEMA_TO_SERVER_STATICFILES`` to the name of the current schema you are working on, because after much searching it is not possible to automatically set the current schema value because when Django is serving static files ``it does not pass through the TenantMiddleware middleware`` that is responsible for lets the current tenant available through ``from django.db import connection; connection.schema_name``. Also I tried to use ``request.path`` but ``request is also not available within FileSystemFinder``, so we have to do as below. This is necessary only to server static files locally.

    IMPORTANT: For all the other things like collectstatic files, medias files, the variable ``CURRENT_SCHEMA_TO_SERVER_STATICFILES it's not necessary``, because the schema name is automatically found for these actions.

.. code-block:: python

    # in settings.py

    # to work with schema_name_1 set:
    CURRENT_SCHEMA_TO_SERVER_STATICFILES = "schema_name_1"

    # change value to 'schema_name_2' for to work with other schema:
    CURRENT_SCHEMA_TO_SERVER_STATICFILES = "schema_name_2"

Static files aware tenant
-------------------------

.. code-block:: python

    STATICFILES_STORAGE = 'django_tenants.staticfiles.storage.TenantStaticFilesStorage'

``TenantStaticFilesStorage`` has the function of manipulating files of each tenant and collecting them to a specific directory of this tenant, having as destination directory: ``os.path.join (STATIC_ROOT, MULTITENANT_RELATIVE_STATIC_ROOT)``

The command to collect the static files of each tenant is ``collectstatic_schemas``

.. code-block:: bash
    
    ./manage.py collectstatic_schemas --schema=your_schema_name

For STATIC_ROOT settings with this value:

.. code-block:: python
    
    STATIC_ROOT = os.path.join (SITE_DIR, 'public', 'static')

We can set ``MULTITENANT_RELATIVE_STATIC_ROOT`` of the many ways, as bellow

Examples
~~~~~~~~

.. code-block:: python
    
    # For:
    MULTITENANT_RELATIVE_STATIC_ROOT = ""  # or not set

Static files will be collected at -> path_your_project/public/static/``tenant_name``.

.. code-block:: python
    
    # For:
    MULTITENANT_RELATIVE_STATIC_ROOT = "other_dir"

Static files will be collected at -> path_your_project/public/static/``other_dir/tenant_name``.

You can also use ``%s`` to have more freedom to manipulate the destination directory, where the ``%s`` will be replaced by the name of the ``schema``.
 
.. code-block:: python

    # For:
    MULTITENANT_RELATIVE_STATIC_ROOT = "%s/other_dir"

Static files will be collected at -> path_your_project/public/static/``tenant_name/other_dir``

Media files aware tenant
-------------------------

.. code-block:: python

    DEFAULT_FILE_STORAGE = 'django_tenants.files.storages.TenantFileSystemStorage'

``TenantFileSystemStorage`` has the function of uploading files of each tenant and put them to a specific directory of this tenant, having as destination directory: ``os.path.join (MEDIA_ROOT, MULTITENANT_RELATIVE_MEDIA_ROOT)``

For MEDIA_ROOT settings with this value:

.. code-block:: python
    
    MEDIA_ROOT = os.path.join (SITE_DIR, 'public', 'media')

We can set ``MULTITENANT_RELATIVE_MEDIA_ROOT`` of the many ways, as bellow

Examples
~~~~~~~~

.. code-block:: python

    # For:
    MULTITENANT_RELATIVE_MEDIA_ROOT = ""  # or not set

Media files will be uploaded at -> path_your_project/public/media/``tenant_name``.

.. code-block:: python
    
    # For:
    MULTITENANT_RELATIVE_MEDIA_ROOT = "other_dir"

Media files will be uploaded at -> path_your_project/public/media/``other_dir/tenant_name``.

You can also use ``%s`` to have more freedom to manipulate the upload destination directory, where the ``%s`` will be replaced by the name of the ``schema``.
 
.. code-block:: python

    # For:
    MULTITENANT_RELATIVE_MEDIA_ROOT = "%s/other_dir"

Media files will be uploaded at -> path_your_project/public/media/``tenant_name/other_dir``