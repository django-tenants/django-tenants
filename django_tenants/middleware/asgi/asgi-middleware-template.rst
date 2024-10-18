===================================
ASGI Middleware for Django Tenants
===================================

This sub-project introduces ASGI-compatible middleware classes to enable asynchronous multi-tenancy
for Django Tenants.

Rationale
==========
With the ever-evolving programming landscape of asynchronous methodology and developers making significant 
moves to work with asynchronous tasks, I believe it's high time we acknowledged that django-tenants has 
matured to embrace this evolution. This project aims to help users handle their middleware asynchronously
for domain/tenant URL mapping within their programs.

For example, one of the project users ([https://github.com/django-tenants/django-tenants/discussions/981])
had once raised a discussion on how to use SubfolderTenantMiddleware in the settings, and no one had a definitive 
answer. Many developers, like us, work with web-sockets and data analysis tasks, heavily relying on an asynchronous 
environment while maintaining some tasks to utilize the synchronous default nature of Django. 

This project enables users who run such daily tasks to route their domain URLs with ease. The rationale 
behind this project is to make things easier for programmers working with django-tenants, allowing them 
to handle their domain routing asynchronously and efficiently.



Overview
========

With the increasing need for handling asynchronous operations, this project aims 
to provide middleware that supports ASGI for Django Tenants. The middleware classes included here 
handle different multi-tenancy scenarios, ensuring efficient and secure tenant management.

Middleware Classes
==================

ASGIMainTenantMiddleware
-------------------------------
**Description:**
Handles multi-tenancy for ASGI applications by selecting the proper database schema using
the request host. Designed to fail safely to avoid data corruption or leakage.


**Key Features:**

- Selects appropriate database schema based on request host.

- Ensures the middleware is called first in the Django request-response cycle.

**Example Setup:**
```python
application = ProtocolTypeRouter({
    "http": ASGIMainTenantMiddleware(get_asgi_application()),
    ## Other protocols here.
})

# on settings.py
ASGI_APPLICATION = "your_project.asgi.application"

```


ASGISubfolderTenantMiddleware
------------------------------

**Description:**
Handles subfolder-based multi-tenancy for ASGI applications, 
selecting the appropriate tenant based on the request's subfolder.

**Key Features**:

- Selects tenant based on request subfolder.

- Ensures the middleware is called first in the Django request-response cycle.


**Example Setup:**
```python
application = ProtocolTypeRouter({
    "http": ASGISubfolderTenantMiddleware(get_asgi_application()),
    ## Other protocols here.
})

# on settings.py
ASGI_APPLICATION = "your_project.asgi.application"

```


ProtocolTypeRouter
-------------------
Description: Takes a mapping of protocol type names to Application instances, dispatching to the
right one based on protocol name. We don't want to re-invent the wheel, so if your project depends
on django-channels, you can import this class from `channels.routing`, and if not then inherit it
from `middleware.asgi` of django-tenants.

Adapted from: channels.routing (https://pypi.org/project/channels/)

**Key Features**:

- Routes ASGI instances based on protocol type.

- Flexible setup, allowing use of channels if desired.




ASGISuspiciousTenantMiddleware
-------------------------------
**Description:**
Handles suspicious multi-tenancy for ASGI applications. Extends the ASGITenantMiddleware to 
configure ``ALLOWED_HOSTS`` to allow ANY domain_url, supporting tenants that can bring custom domains.

See the discussion: https://github.com/bernardopires/django-tenant-schemas/pull/269

**Key Features:**
- Configures ALLOWED_HOSTS to accept any custom domain.
- Ensures the middleware is called first in the Django request-response cycle.

**Example Setup:**
```python
application = ProtocolTypeRouter({
    "http": ASGISuspiciousTenantMiddleware(get_asgi_application()),
    ## Other protocols here.
})


# on settings.py
ASGI_APPLICATION = "your_project.asgi.application"



Evidences: (the images can be deleted, it is just to show you that it is working, same with the tests)
-----------

Attach Evidence: Added screenshots or pictures here to demonstrate the middleware in action.

.. image:: images/asgi-served-tenant-domain.png :alt: Screenshot of ASGIMainTenantMiddleware working for a tenant routing.

.. image:: images/domain-url.png :alt: Screenshot of ASGIMainTenantMiddleware working for a tenant routing. 

.. image:: images/subfolder-asgi-url.png :alt: Screenshot of ASGISubfolderTenantMiddleware working

.. image:: images/domain-url.png :alt: Screenshot of ASGISuspiciousTenantMiddleware working


Attach Evidence: Shown the tests cases for ASGI middleware working  

.. image:: images/test-cases-for-the-asgi-middlewares.png  :alt: Screenshot of ASGISubfolderTenantMiddleware and ASGIMainTenantMiddleware working 


Attached Evidence: Shown evidence of the Development server and my asgi.py screenshot

.. image:: images/django-dev-server.png :alt: Screenshot of Django Development server working with Daphne server. However, on the development you may decide to use only Django server

.. image:: images/my-setup-of-asgi.png  :alt: Screenshot of my asgi project setup working. Other protocol key-value pairs are not necessary. 


Deployment
-----------
On deployment, if you are using Channels, don't forget to install this,
and add daphne at the very top, just after the django-tenants

```py
pip install django-tenants daphne
``` 




