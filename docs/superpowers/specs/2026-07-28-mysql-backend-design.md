# MySQL Backend Support — Design

Date: 2026-07-28
Status: Approved for planning

## Problem

`django-tenants` currently only supports PostgreSQL. Multi-tenancy is implemented
by keeping tenants and the shared "public" data in the same physical database,
as separate Postgres *schemas*, and switching between them per-request by
running `SET search_path` on the connection. Because Postgres resolves
unqualified table names by walking the search path, tenant-app models and
shared-app models can be joined transparently within a single query/connection.

We want to add MySQL support for the same isolation model the maintainers
actually want: **one real MySQL database per tenant, plus one shared "public"
database for shared tables** — not an attempt to replicate Postgres's
search-path semantics inside MySQL.

## Scope

This spec covers **core MySQL tenancy only**:
- A MySQL `DatabaseWrapper` implementing tenant switching.
- Schema (database) creation, deletion, and existence checks.
- Making `migrate_schemas`, `create_tenant`, `create_domain`, the router, the
  middleware, and both migration executors (standard + multiprocessing) work
  end-to-end against the new backend.

**Explicitly out of scope for this spec** (tracked as follow-up work):
- Tenant cloning (`clone_tenant` command, `TENANT_CREATION_FAKES_MIGRATIONS` /
  `TENANT_BASE_SCHEMA`, and the underlying `clone.py`, which is a ~4600-line
  Postgres-only PL/pgSQL procedure).
- `rename_schema` for MySQL (MySQL has no `RENAME DATABASE`; a correct
  implementation requires copying every table into a new database, which is
  cloning-adjacent work and deferred with it).
- MariaDB support/testing (may work incidentally via the same code path, but
  is not tested or claimed as supported here).

## Architecture

Mirror the Postgres approach, substituting MySQL's native database-switching
for Postgres's `search_path`:

- Each tenant is a real MySQL database (`CREATE DATABASE`), created and
  dropped the same way tenant schemas are today.
- The "public" schema is another real MySQL database, named via the existing
  `PUBLIC_SCHEMA_NAME` setting.
- Switching tenants means issuing `` USE `<db_name>` `` on the existing
  connection instead of `SET search_path`. This is cheap — no reconnect.
- `connection.schema_name` keeps meaning "the currently active database", so
  `TenantMixin`, `routers.py`, the middleware, and the migration executors
  keep working against the same `set_tenant()` / `set_schema()` /
  `set_schema_to_public()` API surface. **These modules require no changes** —
  they only ever call that API, never raw SQL.
- MySQL only ever has one database "in scope" per connection (no
  search-path-style overlay of multiple schemas), so introspection needs **no
  patching** — Django's stock `django.db.backends.mysql.introspection` already
  scopes `get_table_list()` etc. to the current database.

### Confirmed limitation: no cross-database joins

Because MySQL can't have a tenant database and the public database
simultaneously "in path" on one connection the way Postgres can, **foreign
keys from `TENANT_APPS` models to `SHARED_APPS` models cannot be resolved as a
single-query SQL JOIN** under MySQL. This mirrors how most database-per-tenant
Django setups already work. It is not silently allowed to fail at query time —
it's a documented architectural constraint of the MySQL backend.

## Components

### New package: `django_tenants/mysql_backend/`

Mirrors `postgresql_backend/`:

- **`base.py`**: `DatabaseWrapper(original_backend.DatabaseWrapper)` wrapping
  `django.db.backends.mysql`. Overrides `_cursor()` to run
  `` USE `<schema_name>` `` (skipping the call when the current database
  already matches, mirroring the `TENANT_LIMIT_SET_CALLS` optimization that
  today skips repeated `SET search_path` calls). Keeps `set_tenant`,
  `set_schema`, `set_schema_to_public`, `set_settings_schema`, `get_schema`,
  `get_tenant`, and `FakeTenant` with identical signatures to the Postgres
  backend. `include_public_schema` is accepted for API compatibility but has
  no effect (there is no second schema to overlay).
- MySQL identifier validation: `is_valid_schema_name` / `_check_schema_name`
  reimplemented for MySQL database-naming rules (≤64 characters; no
  `/ \ .` or trailing space; not empty) — a different rule set from the
  Postgres regex, not a reuse of it.
- No `introspection.py` — uses Django's stock MySQL introspection unchanged.

### `utils.py`: vendor dispatch for the two Postgres-only spots

- **`schema_exists()`**: currently a raw `pg_catalog.pg_namespace` query. Add
  a MySQL path querying `information_schema.SCHEMATA`, dispatched on
  `connections[database].vendor`.
- **`schema_rename()`**: keeps the existing Postgres
  `ALTER SCHEMA ... RENAME TO ...` path. For MySQL vendor, raises
  `NotImplementedError` with a message pointing at the deferred follow-up.
- **`validate_extra_extensions()`**: no-op for MySQL — `PG_EXTRA_SEARCH_PATHS`
  stays a Postgres-only setting.
- New helpers: `get_schema_name_validator()` and `create_schema_sql()` /
  `drop_schema_sql()`, dispatched by DB vendor, used by `models.py` (see
  below).

### `models.py`: remove hardcoded Postgres SQL (real fix, not MySQL-only)

`TenantMixin.create_schema()` / `_drop_schema()` currently hardcode Postgres
SQL directly in otherwise-generic model code (`CREATE SCHEMA "%s"`,
`DROP SCHEMA "%s" CASCADE`), and the `schema_name` field's validator is
imported unconditionally from `postgresql_backend.base`. Both move behind the
new `utils.py` vendor-dispatch helpers, so `models.py` no longer hardcodes
Postgres syntax regardless of which backend is configured.

For MySQL: `` CREATE DATABASE `name` `` / `` DROP DATABASE `name` ``. MySQL's
`CREATE SCHEMA` / `DROP SCHEMA` are aliases for `CREATE/DROP DATABASE` but
don't support `CASCADE` — dropping a database already drops everything in it.

### Explicitly guarded as out-of-scope for MySQL (clear error, not silent failure)

- The `TENANT_CREATION_FAKES_MIGRATIONS` / `TENANT_BASE_SCHEMA` cloning path
  inside `create_schema()` (uses `CloneSchema`, which is Postgres-only
  PL/pgSQL) raises `NotImplementedError` for the MySQL vendor.
- `clone_tenant` management command: same reason, same treatment.
- `rename_schema` management command: delegates to `schema_rename()` above.

### No changes needed

`routers.py`, `middleware/*`, `migration_executors/*`,
`management/commands/create_tenant.py`, `create_domain.py`,
`migrate_schemas.py` — all of these only touch the
`connection.set_tenant`/`set_schema`/`schema_name` API, never raw SQL.

### Packaging

- Add `django_tenants.mysql_backend` to `pyproject.toml`'s package list.
- Add an optional dev dependency on `mysqlclient` (the only driver Django's
  built-in `django.db.backends.mysql` supports).

## Documented limitations

- No cross-database FKs/joins between `TENANT_APPS` and `SHARED_APPS` models
  under MySQL (see Architecture above) — called out prominently in
  `docs/install.rst` / README as the most likely footgun when migrating a
  Postgres setup to MySQL.
- Tenant cloning and `rename_schema` raise `NotImplementedError` under MySQL,
  with a message explaining why and that it's planned as a follow-up.
- `PG_EXTRA_SEARCH_PATHS` / other Postgres-only settings are documented as not
  applicable to MySQL.
- MySQL identifier rules (64-char limit, disallowed characters) are validated
  at `schema_name` field-clean time, same as Postgres's regex today, so
  invalid tenant names fail fast with a `ValidationError` instead of a
  cryptic SQL error at `CREATE DATABASE` time.

## Testing

- New MySQL-flavored test settings module alongside
  `django_tenants/tests/test_settings.py`, and a MySQL variant of
  `dts_test_project/settings.py`'s `DATABASES`
  (`ENGINE: django_tenants.mysql_backend`), selectable via an env var so the
  existing test suite can run against either backend.
- Reuse the existing test suite (tenant creation, migration, middleware
  routing, multi-type tenants) against the new backend where it doesn't touch
  Postgres-only behavior (search path, cloning) — those cases are
  skipped/marked backend-specific.
- New CI job in `.github/workflows/code.yml`, `mysql_compatibility`, mirroring
  the existing `postgres_compatibility` job structure: a `mysql:8.0`/`8.4`
  docker service, matrix over MySQL versions, running the shared test suite
  with `ENGINE=django_tenants.mysql_backend`.
- MariaDB is not tested or officially claimed as supported in this phase.
