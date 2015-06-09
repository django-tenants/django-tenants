=======================================
Specializing templates based on tenants
=======================================

Multitenant aware filesystem template loader
--------------------------------------------

The classical Django filesystem template loader cannot make the search path for template vary based on the current tenant so it's needed to use a special one which adapt the search path based on the tenant. For using it add it to your ``TEMPLATE_LOADERS`` setting.

.. code-block:: python

    TEMPLATE_LOADERS = (
        'tenant_schemas.template_loaders.FilesystemLoader',
        'django.template.loaders.filesystem.Loader',
        'django.template.loaders.app_directories.Loader'
    )

This loader is looking for templates based on the setting ``MULTITENANT_TEMPLATE_DIRS`` instead of the path in ``TEMPLATE_DIRS``. Templates are not searched directly in each directory ``template_dir`` but in the directory ``os.path.join(template_dir, tenant.domain_url)``. If ``template_dir`` contains a ``%s`` formatting placeholder the directory used is ``template_dir % tenant.domain_url`` so that you can store your templates in a subdirectory of your tenant directory. Like with the Django ``FilesystemLoader`` the first found file is returned.

Multitenant aware cached template loader
----------------------------------------

If you are using template caching with the multitenant filesystem loader it is not gonna work as the cache is ignoring the tenant. So the first template loaded for any tenant will be returned for all other tenants. To remediate to this problem you can use a new loader whose cache is based on the template path and the primary key of the tenant model.

The multitenant cached loader works exactly like the Django cached loader but is tenant aware.

.. code-block:: python

    TEMPLATE_LOADERS = (
        ('tenant_schemas.template_loaders.CachedLoader', (
          'tenant_schemas.template_loaders.FilesystemLoader',
          'django.template.loaders.filesystem.Loader',
          'django.template.loaders.app_directories.Loader')),
    )

