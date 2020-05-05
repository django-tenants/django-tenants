*********
Changelog
*********

This changelog is used to track all major changes to django-tenants.


v3.1.0 (26 April 2020)
======================

- Allowed a schema to be renamed. #388
- Stopped a crash id logging with the public tenant #358
- Fix clone_tenant command #379
- Cloning SQL changed to allow it work on AWS etc #381
- Now testing with workflow instead of Travis CI
- Read the docs now work again

v3.0.3 (16 April 2020)
======================

- Fixed a problem with clone tenant

v3.0.2 (15 April 2020)
======================

- You can now clone a tenants with the clone_tenant command #322
- Fixed some issues with docker-compose and the example project
- Refactor some classes/methods #325

v3.0.1 (17 Feb 2020)
===================

- Make "test login" add tenant to request #340

**Fixes**

- Use field.attname instead of field.name in create_tenant.py

v3.0.0 (9 Jan 2020)
===================

- Django 3 support
- Removed psycopg2 as a requirement #317
- Changed docker image to python 3.7 image
- Do not pip install --quiet while testing
- Added database support to validate schemas #312
- allow to disable new coloring of tenant app in admin #272

**Fixes**

- Fixed an issue where tenant-specific application static files (stylesheets, Javascript, images etc.), that have not been collected yet using ``collectstatic_schemas``, were not being found using ``TenantStaticFilesStorage``. Fixes `#265 <https://github.com/tomturner/django-tenants/issues/265>`_.
- Fix a crash (ProgrammingError) when attempting to create a schema named like a SQL keyword (select, where, ...)
Allow to create a tenant named with only numbers (123). #302 #307

v2.2.3 (15 April 2019)
======================

**Fixes**

- Fixed an issue in setup.py to allow different color of tenant apps in the admin area. Should now work with PyPi.

v2.2.2 (15 April 2019)
======================

**Fixes**

- Fixed an issue in setup.py to allow different color of tenant apps in the admin area. Take 2. [`#262 <https://github.com/tomturner/django-tenants/issues/262>`_]

v2.2.1 (15 April 2019)
======================

**Fixes**

- Fixed an issue with the different color of tenant apps in the admin area. [`#261 <https://github.com/tomturner/django-tenants/issues/261>`_]

v2.2.0 (14 April 2019)
======================

**Fixes**

- TenantFileSystemStorage now works [`#249 <https://github.com/tomturner/django-tenants/issues/249>`_]

**Enhancements**

- support django>=2.2 [`#238 <https://github.com/tomturner/django-tenants/issues/238>`_]
- TenantAdminMixin is available in order to register the tenant model. [`#223 <https://github.com/tomturner/django-tenants/issues/223>`_]
- Admin site: highlight with a different color the tenant apps. [`#227 <https://github.com/tomturner/django-tenants/issues/227>`_]
- Admin site: disable the tenant apps when in the public schema. [`#227 <https://github.com/tomturner/django-tenants/issues/227>`_]
- Custom auth backend compatibility for TenantClient. [`#228 <https://github.com/tomturner/django-tenants/issues/228>`_]
- Switch to psycopg2 dependency rather than psycopg2-binary [`#239 <https://github.com/tomturner/django-tenants/issues/239>`_]

v2.1.0 (31 Dec 2018)
====================

**Enhancements**

- Added `TENANT_CREATION_FAKES_MIGRATIONS` configuration parameter that can be used to copy schemas from an existing "template" schema instead of running migrations.
- `schema_context` now operates as a decorator too. Fixes: `#199 <https://github.com/tomturner/django-tenants/issues/199>`_.
- Update template loaders and static file storage for Django > 2.0. Fixes: `#197 <https://github.com/tomturner/django-tenants/issues/197>`_.
- Added `pre_drop` to `TenantMixin` that can be used to backup the tenant schema before dropping.
- Allow using non-default databases for schemas using the new `TENANT_DB_ALIAS` config parameter.
- Add `TENANT_BASE_SCHEMA` configuration parameter for creating tenant schema from a pre-specified "default" base tenant schema.
- Add support for tenant models that are not serializable.
- Various updates to documentation.
- Update tests for Django 2 and Python 3.

**Fixes**

- Fix setup.py to reference new `psycopg2-binary` dependency. Fixes `#174 <https://github.com/tomturner/django-tenants/issues/174>`_.
- Add support for creating tenants that share field names with domains. Fixes: `#167 <https://github.com/tomturner/django-tenants/issues/167>`_.
- Use `get_tenant` instead of `get_domain` in `DefaultTenantMiddleware` to lookup tenant. Fixes: `#154 <https://github.com/tomturner/django-tenants/issues/154>`_.
- Fix `TENANT_LIMIT_SET_CALLS` implementation to not rely on the cursor pointer changes. See: `#157 <https://github.com/tomturner/django-tenants/pull/157>`_.
