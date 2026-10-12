========
Security
========

django-tenants routes every request to a PostgreSQL schema from the host name.
That alone does not make authentication or sessions safe across tenants -- how
you place ``django.contrib.auth`` and ``django.contrib.sessions`` in
``SHARED_APPS`` / ``TENANT_APPS`` matters. Misplacing them can let a user on one
tenant impersonate a user on another. See
`issue #52 <https://github.com/django-tenants/django-tenants/issues/52>`_.

Auth and sessions must stay together
------------------------------------

Keep ``django.contrib.auth`` and ``django.contrib.sessions`` at the **same**
level: both shared, or both tenant-specific. Mixing them is unsafe.

=============================== =============================== ============
``django.contrib.auth``         ``django.contrib.sessions``     Safe?
=============================== =============================== ============
``SHARED_APPS``                 ``SHARED_APPS``                 Yes
``TENANT_APPS``                 ``TENANT_APPS``                 Yes [*]_
``SHARED_APPS``                 ``TENANT_APPS``                 Yes
``TENANT_APPS``                 ``SHARED_APPS``                 **No**
=============================== =============================== ============

.. [*] Safe with the database session backend. Cache- or file-backed sessions
   need extra care -- see :ref:`non-database-sessions` below.

"Safe" here means one tenant's session cannot be read as another tenant's user.
With ``django.contrib.auth`` in ``SHARED_APPS`` an account exists on every tenant,
so you still need to check that the user belongs to the tenant -- see the global
accounts setup below.

You may list both apps in **both** ``SHARED_APPS`` and ``TENANT_APPS``. Tables
are then created in public and in every tenant. On a tenant request the search
path prefers the tenant schema, so that tenant uses its own session and user
tables.

Why the unsafe combination is a vulnerability
---------------------------------------------

Django's session stores a user primary key (for example ``_auth_user_id``).
That key is only meaningful relative to the ``User`` table the request will
load.

If sessions are shared (one session store for every host) while each tenant has
its own ``User`` table, the same session id resolves to **different users** on
different tenants -- often users that happen to share the same primary key. The
session cookie reaches another tenant either because ``SESSION_COOKIE_DOMAIN`` is
set to the parent domain, or simply because the visitor sends their own cookie to
the other host, which takes no effort. A visitor who logs in on
``tenant-a.example.com`` can then present that session on ``tenant-b.example.com``
and be loaded as whoever has that id there.

Django usually catches this: the session also stores a hash of the user's
password hash, and a session whose hash does not match is logged out. But that
check only holds while the two users' stored password hashes differ. It does not
when tenants are cloned from a template that already contains users (for example
with ``TENANT_CREATION_FAKES_MIGRATIONS``), or with a custom user model without
``get_session_auth_hash``. Do not rely on it.

The session **storage** backend does not fix this. A session store shared by
every tenant plus tenant-specific users is enough; database, cache, and file
sessions are all vulnerable in that configuration.

Recommended setups
------------------

Separate accounts per tenant
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Put auth and sessions in ``TENANT_APPS`` (and typically also in
``SHARED_APPS`` if the public site needs login)::

    SHARED_APPS = (
        'django_tenants',
        'customers',
        'django.contrib.contenttypes',
        'django.contrib.auth',
        'django.contrib.sessions',
        # ...
    )

    TENANT_APPS = (
        'django.contrib.contenttypes',
        'django.contrib.auth',
        'django.contrib.sessions',
        # your tenant apps
    )

With the database session backend, each tenant gets its own ``django_session``
table and its own users.

Global accounts shared by every tenant
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Put auth and sessions in ``SHARED_APPS`` only. Users are global -- logging in on
one tenant leaves them logged in on every tenant they can open, similar to a
single sign-on cookie across subdomains.

That is not an impersonation bug by itself, but it **is** a cross-tenant access
bug unless you restrict which tenants a user may enter. A common approach is a
middleware placed **after**
``django.contrib.auth.middleware.AuthenticationMiddleware`` that checks a
relation between the user and ``request.tenant`` and returns HTTP 403 when they
do not belong together. Keep
``django_tenants.middleware.main.TenantMainMiddleware`` at the top of
``MIDDLEWARE`` so the schema is selected first; the membership check comes
after authentication has set ``request.user``.

.. _non-database-sessions:

Non-database session backends
-----------------------------

``TENANT_APPS`` only controls where Django creates the session **table**. If
sessions live in cache, Redis, Memcached, or files, that store is shared unless
you make it tenant-aware yourself.

* Prefer the database session backend when sessions are tenant-specific, or
* Configure a tenant-aware cache key function (see :ref:`tenant-aware-caching`
  below) when using a cache-backed session, and verify keys cannot collide
  across schemas.

.. _tenant-aware-caching:

Tenant-aware caching
--------------------

A shared cache without a tenant prefix has the same cross-tenant risk as shared
sessions. Use the helpers shipped with django-tenants::

    CACHES = {
        'default': {
            # ...
            'KEY_FUNCTION': 'django_tenants.cache.make_key',
            'REVERSE_KEY_FUNCTION': 'django_tenants.cache.reverse_key',
        },
    }

``REVERSE_KEY_FUNCTION`` is only required with the django-redis backend.

Moving sessions onto tenants later
----------------------------------

If an existing project had ``django.contrib.sessions`` only in ``SHARED_APPS``
and you add it to ``TENANT_APPS``, Django may believe the sessions migrations
are already applied on each tenant and skip creating the table. Fake the
sessions app back to zero on tenants, then migrate again -- see the warning
under :doc:`install` about moving apps between ``SHARED_APPS`` and
``TENANT_APPS``.

Multi-type tenants
------------------

The same rules apply when using ``HAS_MULTI_TYPE_TENANTS``: for every type in
``TENANT_TYPES``, keep auth and sessions together in that type's ``APPS`` list
(or rely on shared auth with an explicit membership check). Do not give a type
tenant-specific auth while leaving sessions only on the public / shared side.
