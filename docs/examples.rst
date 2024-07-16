========
Examples
========

Tenant Tutorial
---------------
This app comes with an interactive tutorial to teach you how to use ``django-tenants`` and to demonstrate its capabilities. This example project is available under `examples/tenant_tutorial <https://github.com/django-tenants/django-tenants/blob/master/examples/tenant_tutorial>`_. You will only need to edit the ``settings.py`` file to configure the ``DATABASES`` variable and then you're ready to run

.. code-block:: bash

    ./manage.py runserver 

All other steps will be explained by following the tutorial, just open ``http://127.0.0.1:8000`` on your browser.


Running the example projects with Docker Compose
------------------------------------------------

To run the example projects with docker-compose. You will need.

1. Docker

2. Docker Compose

Then you can run

.. code-block:: bash

    docker-compose run -p 8088:8088 web bash

    cd examples/tenant_tutorial

    python manage.py migrate

    python manage.py create_tenant

    python manage.py runserver 0.0.0.0:8088


All other steps will be explained by following the tutorial, just open ``http://127.0.0.1:8088`` on your browser.
