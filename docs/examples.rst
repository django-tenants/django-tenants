========
Examples
========

Tenant Tutorial
---------------
This app comes with an interactive tutorial to teach you how to use ``django-tenants`` and to demonstrate its capabilities. This example project is available under `examples/tenant_tutorial <https://github.com/django-tenants/django-tenants/blob/master/examples/tenant_tutorial>`_. You will only need to edit the ``settings.py`` file to configure the ``DATABASES`` variable and then you're ready to run

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

Then you can run

.. code-block:: bash

    fab vagrant provision_vagrant

    fab vagrant reset_database

    fab vagrant create_tenant

    fab vagrant runserver


Now port 8080 is open and ready to use

Make sure you add and entry in you host file
