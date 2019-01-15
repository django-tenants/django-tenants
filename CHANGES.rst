# Changelog

This changelog is used to track all major changes to django-tenants.

## v2.1.1 (UNRELEASED)

**Fixes**

- Fix changelog formatting.

## v2.1.0 (31 Dec 2018)

**Enhancements**

- Added `TENANT_CREATION_FAKES_MIGRATIONS` configuration parameter that can be used to copy schemas from an existing "template" schema instead of running migrations.
- `schema_context` now operates as a decorator too. Fixes: [#199](https://github.com/tomturner/django-tenants/issues/199).
- Update template loaders and static file storage for Django > 2.0. Fixes: [#197](https://github.com/tomturner/django-tenants/issues/197).
- Added `pre_drop` to `TenantMixin` that can be used to backup the tenant schema before dropping.
- Allow using non-default databases for schemas using the new `TENANT_DB_ALIAS` config parameter.
- Add `TENANT_BASE_SCHEMA` configuration parameter for creating tenant schema from a pre-specified "default" base tenant schema.
- Add support for tenant models that are not serializable.
- Various updates to documentation.
- Update tests for Django 2 and Python 3.

**Fixes**

- Fix setup.py to reference new `psycopg2-binary` dependency. Fixes [#174](https://github.com/tomturner/django-tenants/issues/174).
- Add support for creating tenants that share field names with domains. Fixes: [#167](https://github.com/tomturner/django-tenants/issues/167).
- Use `get_tenant` instead of `get_domain` in `DefaultTenantMiddleware` to lookup tenant. Fixes: [#154](https://github.com/tomturner/django-tenants/issues/154).
- Fix `TENANT_LIMIT_SET_CALLS` implementation to not rely on the cursor pointer changes. See: [#157](https://github.com/tomturner/django-tenants/pull/157).
