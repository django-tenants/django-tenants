========
Examples
========

Tenant Tutorial
---------------
This app comes with an interactive tutorial to teach you how to use ``django-tenants`` and to demonstrate its capabilities. This example project is available under `examples/tenant_tutorial <https://github.com/bernardopires/django-tenant-schemas/blob/master/examples/tenant_tutorial>`_. You will only need to edit the ``settings.py`` file to configure the ``DATABASES`` variable and then you're ready to run

.. code-block:: bash

    ./manage.py runserver 

All other steps will be explained by following the tutorial, just open ``http://127.0.0.1:8000`` on your browser.


Running the example project with Vagrant
----------------------------------------

You can run the example project with vagrant. You will need.

1. VirtualBox

2. Vagrant

3. Fabric  (pip install fabric)

4. Fabtools (pip install fabtools)

Then you can run ./provision_vagrant.sh

Then you can run ./vagrant_create_tenant.sh

Make sure you add and entry in you host file