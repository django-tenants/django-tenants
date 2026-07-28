# MySQL Backend Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `django_tenants.mysql_backend` engine so `django-tenants` can run tenants as isolated MySQL databases with a shared "public" MySQL database, alongside the existing PostgreSQL support.

**Architecture:** Each tenant is a real MySQL database; the public schema is another real MySQL database named via `PUBLIC_SCHEMA_NAME`. A custom `DatabaseWrapper` switches tenants by issuing `` USE `<db_name>` `` on the existing connection (instead of Postgres's `SET search_path`). `connection.schema_name`/`set_tenant()`/`set_schema()`/`set_schema_to_public()` keep the exact same API surface as the Postgres backend, so `routers.py`, `middleware/`, and `migration_executors/` need zero changes. No introspection patching is needed — MySQL's stock introspection already scopes to the current database.

**Tech Stack:** Django's built-in `django.db.backends.mysql` (mysqlclient driver), MySQL 8.0+/8.4, existing `dts_test_project` test harness.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-28-mysql-backend-design.md` — read it before starting; it governs every task below.
- Cross-database FKs/joins between `TENANT_APPS` and `SHARED_APPS` models are **not supported** under MySQL — do not attempt to work around this anywhere in this plan.
- Tenant cloning (`clone_tenant`, `TENANT_CREATION_FAKES_MIGRATIONS`/`TENANT_BASE_SCHEMA`) and `schema_rename()` are **out of scope** for MySQL — they must raise a clear `NotImplementedError`, never silently misbehave.
- Do not change the `schema_name` field's `max_length=63` on `TenantMixin` — it's a Postgres-derived constraint but is a safe, conservative superset-compatible value for MySQL's 64-char limit too; bumping it would force a migration on every existing Postgres project and is not needed for MySQL support to work.
- MariaDB is not tested or claimed as supported in this phase.
- Full-suite parameterization of the existing ~15 Postgres-oriented test files across both backends is **not** attempted in this plan (many hardcode Postgres-only syntax, e.g. backtick-containing schema names in `test_tenants.py`). Instead, this plan adds focused new tests for all new/changed code, plus one dedicated MySQL end-to-end smoke test module. Broadening backend coverage of the pre-existing suite is a follow-up, not this plan.
- Every new MySQL-touching test must be skipped (not run, not failed) when the configured backend isn't MySQL, so the existing Postgres CI job and local Postgres dev workflow are completely unaffected.

## Prerequisites (read before Task 2)

You'll need a local MySQL server to verify Tasks 2–7. Docker is available on this machine. Use a container name and port that won't collide with anything else running:

```bash
docker run --name dts-mysql-test -p 3307:3306 \
  -e MYSQL_ROOT_PASSWORD=testing -e MYSQL_DATABASE=public \
  -d mysql:8.0
```

`MYSQL_DATABASE=public` creates the shared "public" database automatically at container startup — this is required before `migrate_schemas --shared` can run, since MySQL has no schema equivalent to Postgres's always-present default `public` schema inside every database.

Wait for it to be ready before using it:

```bash
until docker exec dts-mysql-test mysqladmin ping -h 127.0.0.1 -u root -ptesting --silent; do sleep 1; done
```

You'll also need the `mysqlclient` Python driver installed, which requires MySQL client libraries. On macOS:

```bash
brew install mysql-client pkg-config
export PKG_CONFIG_PATH="$(brew --prefix mysql-client)/lib/pkgconfig"
```

When you're done with all tasks, tear the container down:

```bash
docker stop dts-mysql-test && docker rm dts-mysql-test
```

---

### Task 1: Move `FakeTenant` to a shared location (DRY fix, prerequisite)

`FakeTenant` is currently defined once, inside `postgresql_backend/base.py`, and imported directly from that Postgres-specific path by `django_tenants/template/loaders/cached.py` (`isinstance(connection.tenant, FakeTenant)`). Once a MySQL backend exists with its own tenant-switching, we need a single shared `FakeTenant` class both backends use — otherwise `cached.py`'s `isinstance` check silently breaks under MySQL (it would always be `False` for MySQL's fake tenants, since they'd be a different class). This fix is needed regardless of which backend is active, so it's a clean prerequisite.

**Files:**
- Modify: `django_tenants/utils.py` (add `FakeTenant` class)
- Modify: `django_tenants/postgresql_backend/base.py:196-206` (remove local `FakeTenant`, import shared one)
- Modify: `django_tenants/template/loaders/cached.py:10` (import from `utils` instead of `postgresql_backend.base`)
- Test: `django_tenants/tests/test_utils.py`

**Interfaces:**
- Produces: `django_tenants.utils.FakeTenant(schema_name, tenant_type=None)` with `.schema_name`, `.tenant_type`, `.get_tenant_type()` — used by both backends' `set_schema()`/`set_schema_to_public()` and by `template/loaders/cached.py`.

- [ ] **Step 1: Write the failing test**

Add to `django_tenants/tests/test_utils.py`:

```python
from django_tenants.postgresql_backend.base import FakeTenant as PostgresFakeTenant
from django_tenants.utils import FakeTenant


class FakeTenantTestCase(TenantTestCase):
    def test_postgres_backend_uses_shared_fake_tenant(self):
        self.assertIs(PostgresFakeTenant, FakeTenant)

    def test_fake_tenant_exposes_tenant_type(self):
        tenant = FakeTenant(schema_name='public', tenant_type='default')
        self.assertEqual(tenant.schema_name, 'public')
        self.assertEqual(tenant.get_tenant_type(), 'default')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd dts_test_project && python manage.py test django_tenants.tests.test_utils.FakeTenantTestCase -v2`
Expected: FAIL — `ImportError: cannot import name 'FakeTenant' from 'django_tenants.utils'`

- [ ] **Step 3: Add `FakeTenant` to `utils.py`**

In `django_tenants/utils.py`, add near the top, right after the `get_model` try/except block (before `def get_tenant_model():`):

```python
class FakeTenant:
    """
    Database backend wrappers can't import real tenant models (risk of
    circular imports), so this wraps a schema name in a tenant-like
    structure for DatabaseWrapper.set_schema()/set_schema_to_public().
    Shared by every backend so isinstance checks (e.g. the cached
    template loader) work regardless of which backend is configured.
    """
    def __init__(self, schema_name, tenant_type=None):
        self.schema_name = schema_name
        self.tenant_type = tenant_type

    def get_tenant_type(self):
        return self.tenant_type
```

- [ ] **Step 4: Update `postgresql_backend/base.py` to use the shared class**

In `django_tenants/postgresql_backend/base.py`, change the import line:

```python
from django_tenants.utils import get_public_schema_name, get_limit_set_calls, FakeTenant
```

Remove the local class definition at the bottom of the file:

```python
class FakeTenant:
    """
    We can't import any db model in a backend (apparently?), so this class is used
    for wrapping schema names in a tenant-like structure.
    """
    def __init__(self, schema_name, tenant_type=None):
        self.schema_name = schema_name
        self.tenant_type = tenant_type

    def get_tenant_type(self):
        return self.tenant_type
```

- [ ] **Step 5: Update `template/loaders/cached.py`**

Change:

```python
from django_tenants.postgresql_backend.base import FakeTenant
```

to:

```python
from django_tenants.utils import FakeTenant
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd dts_test_project && python manage.py test django_tenants.tests.test_utils.FakeTenantTestCase -v2`
Expected: PASS

- [ ] **Step 7: Run the full existing Postgres suite to confirm no regression**

Run: `cd dts_test_project && python manage.py test -v2 django_tenants`
Expected: PASS (same result as before this change — this is a pure refactor)

- [ ] **Step 8: Commit**

```bash
git add django_tenants/utils.py django_tenants/postgresql_backend/base.py django_tenants/template/loaders/cached.py django_tenants/tests/test_utils.py
git commit -m "Move FakeTenant to utils so it's shared across backends"
```

---

### Task 2: `mysql_backend` package skeleton + identifier validation

MySQL database-name rules differ from Postgres schema-name rules (different max length, different disallowed characters). This is pure validation logic with no database dependency, so it's TDD'd standalone before the `DatabaseWrapper` that depends on it.

**Files:**
- Create: `django_tenants/mysql_backend/__init__.py`
- Create: `django_tenants/mysql_backend/base.py`
- Modify: `pyproject.toml`
- Test: `django_tenants/tests/test_mysql_validation_utils.py`

**Interfaces:**
- Produces: `django_tenants.mysql_backend.base.is_valid_schema_name(name) -> bool`, `django_tenants.mysql_backend.base._check_schema_name(name) -> None` (raises `django.core.exceptions.ValidationError`) — used by Task 3's `DatabaseWrapper` and Task 4's `get_schema_name_validator()`.

- [ ] **Step 1: Write the failing tests**

Create `django_tenants/tests/test_mysql_validation_utils.py`:

```python
import unittest

from django.core.exceptions import ValidationError

from django_tenants.mysql_backend import base


class TestMySQLValidationUtils(unittest.TestCase):
    def test_check_schema_name_with_valid_name(self):
        self.assertIsNone(base._check_schema_name('tenant1'))

    def test_check_schema_name_underscore_is_valid(self):
        self.assertIsNone(base._check_schema_name('tenant_1'))

    def test_check_schema_name_upper_case_is_valid(self):
        self.assertIsNone(base._check_schema_name('Tenant1'))

    def test_check_schema_name_hyphen_is_valid(self):
        self.assertIsNone(base._check_schema_name('my-tenant'))

    def test_check_schema_name_64_chars_is_valid(self):
        schema_name = 'a' * 64
        self.assertIsNone(base._check_schema_name(schema_name))

    def test_check_schema_name_65_chars_is_invalid(self):
        schema_name = 'a' * 65
        with self.assertRaisesRegex(ValidationError,
                                    'Invalid string used for the schema name.'):
            base._check_schema_name(schema_name)

    def test_check_schema_name_with_slash_is_invalid(self):
        with self.assertRaisesRegex(ValidationError,
                                    'Invalid string used for the schema name.'):
            base._check_schema_name('tenant/1')

    def test_check_schema_name_with_backslash_is_invalid(self):
        with self.assertRaisesRegex(ValidationError,
                                    'Invalid string used for the schema name.'):
            base._check_schema_name('tenant\\1')

    def test_check_schema_name_with_dot_is_invalid(self):
        with self.assertRaisesRegex(ValidationError,
                                    'Invalid string used for the schema name.'):
            base._check_schema_name('tenant.1')

    def test_check_schema_name_with_backtick_is_invalid(self):
        with self.assertRaisesRegex(ValidationError,
                                    'Invalid string used for the schema name.'):
            base._check_schema_name('tenant`1')

    def test_check_schema_name_with_trailing_space_is_invalid(self):
        with self.assertRaisesRegex(ValidationError,
                                    'Invalid string used for the schema name.'):
            base._check_schema_name('tenant1 ')

    def test_check_schema_name_empty_is_invalid(self):
        with self.assertRaisesRegex(ValidationError,
                                    'Invalid string used for the schema name.'):
            base._check_schema_name('')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd dts_test_project && python manage.py test django_tenants.tests.test_mysql_validation_utils -v2`
Expected: FAIL — `ModuleNotFoundError: No module named 'django_tenants.mysql_backend'`

- [ ] **Step 3: Create the package and validation logic**

Create `django_tenants/mysql_backend/__init__.py` (empty file, matches `postgresql_backend/__init__.py`).

Create `django_tenants/mysql_backend/base.py`:

```python
from django.core.exceptions import ValidationError

# Valid MySQL database (schema) name.
# Criteria:
#  1. Cannot be empty
#  2. Cannot exceed 64 characters
#  3. Cannot contain '/', '\', '.', or a backtick (the identifier-quote
#     character) — disallowed here to avoid needing to escape it when
#     building `USE `<name>`` statements
#  4. Cannot have a trailing space
#
# Reference: https://dev.mysql.com/doc/refman/8.0/en/identifiers.html
DISALLOWED_CHARACTERS = ('/', '\\', '.', '`')


def is_valid_schema_name(name):
    if not name or len(name) > 64:
        return False
    if name != name.rstrip():
        return False
    return not any(char in name for char in DISALLOWED_CHARACTERS)


def _check_schema_name(name):
    if not is_valid_schema_name(name):
        raise ValidationError("Invalid string used for the schema name.")
```

- [ ] **Step 4: Register the package and dev dependency in `pyproject.toml`**

In `pyproject.toml`, add `"django_tenants.mysql_backend",` to the `[tool.setuptools.packages.find]` `include` list, right after `"django_tenants.postgresql_backend",` — check the exact list with `grep -n "packages.find" -A 20 pyproject.toml` first since the include list isn't contiguous with `postgresql_backend` in every version of the file.

Add to `optional-dependencies.dev`:

```toml
optional-dependencies.dev = [
  "coverage",
  "gunicorn==25.1.0",
  "mysqlclient>=2.2,<2.3",
  "psycopg>=3.2.1,<3.3",
]
```

- [ ] **Step 5: Install the new dependency**

Run: `pip install -e ".[dev]"`
Expected: `mysqlclient` installs successfully (requires the Prerequisites section's MySQL client libraries).

- [ ] **Step 6: Run test to verify it passes**

Run: `cd dts_test_project && python manage.py test django_tenants.tests.test_mysql_validation_utils -v2`
Expected: PASS, 12 tests

- [ ] **Step 7: Commit**

```bash
git add django_tenants/mysql_backend/__init__.py django_tenants/mysql_backend/base.py django_tenants/tests/test_mysql_validation_utils.py pyproject.toml
git commit -m "Add mysql_backend package skeleton with schema-name validation"
```

---

### Task 3: MySQL `DatabaseWrapper` (tenant switching)

This is the core of the feature: a `DatabaseWrapper` that switches the "current" MySQL database via `` USE `<db>` `` instead of Postgres's `SET search_path`, exposing the identical `set_tenant`/`set_schema`/`set_schema_to_public` API.

**Files:**
- Modify: `django_tenants/mysql_backend/base.py` (created in Task 2)
- Modify: `dts_test_project/dts_test_project/settings.py:83-92` (env-driven `ENGINE`, needed to point the test runner at MySQL)
- Test: `django_tenants/tests/test_mysql_backend.py` (new)

**Interfaces:**
- Consumes: `django_tenants.mysql_backend.base.is_valid_schema_name`, `_check_schema_name` (Task 2); `django_tenants.utils.FakeTenant`, `get_public_schema_name()`, `get_limit_set_calls()` (Task 1, existing).
- Produces: `django_tenants.mysql_backend.base.DatabaseWrapper` with `.schema_name`, `.tenant`, `.set_tenant(tenant, include_public=True)`, `.set_schema(schema_name, include_public=True, tenant_type=None)`, `.set_schema_to_public()`, `.set_settings_schema(schema_name)` — same signatures as `postgresql_backend.base.DatabaseWrapper`, consumed unchanged by `routers.py`, `models.py`, `migration_executors/*`, `middleware/*` in later tasks.

- [ ] **Step 1: Make the test settings module MySQL-selectable**

In `dts_test_project/dts_test_project/settings.py`, replace the `DATABASES` block (lines 83-92):

```python
DATABASE_ENGINE = os.environ.get('DATABASE_ENGINE', 'django_tenants.postgresql_backend')

_DEFAULT_PORTS = {
    'django_tenants.postgresql_backend': 5432,
    'django_tenants.mysql_backend': 3306,
}
_DEFAULT_USERS = {
    'django_tenants.postgresql_backend': 'postgres',
    'django_tenants.mysql_backend': 'root',
}

DATABASES = {
    'default': {
        'ENGINE': DATABASE_ENGINE,
        'NAME': os.environ.get('DATABASE_DB', 'dts_test_project'),
        'USER': os.environ.get('DATABASE_USER', _DEFAULT_USERS.get(DATABASE_ENGINE, 'postgres')),
        'PASSWORD': os.environ.get('DATABASE_PASSWORD', 'root'),
        'HOST': os.environ.get('DATABASE_HOST', 'localhost'),
        'PORT': os.environ.get('DATABASE_PORT', _DEFAULT_PORTS.get(DATABASE_ENGINE, 5432)),
    }
}
```

- [ ] **Step 2: Write the failing test**

Create `django_tenants/tests/test_mysql_backend.py`. `test_set_schema_switches_current_database` and its siblings need their target databases to exist first — MySQL's `USE` fails on a nonexistent database — so `setUpClass`/`tearDownClass` create and drop them once for the whole class:

```python
import unittest

from django.db import connection
from django.test import TransactionTestCase

from django_tenants.utils import FakeTenant, get_public_schema_name

mysql_only = unittest.skipUnless(
    connection.vendor == 'mysql',
    "MySQL-only test — run with DATABASE_ENGINE=django_tenants.mysql_backend",
)


@mysql_only
class MySQLTenantSwitchingTestCase(TransactionTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        connection.set_schema_to_public()
        with connection.cursor() as cursor:
            cursor.execute('CREATE DATABASE IF NOT EXISTS tenant_switch_test')
            cursor.execute('CREATE DATABASE IF NOT EXISTS tenant_switch_test_2')
            cursor.execute('CREATE DATABASE IF NOT EXISTS fake_tenant_db')

    @classmethod
    def tearDownClass(cls):
        connection.set_schema_to_public()
        with connection.cursor() as cursor:
            cursor.execute('DROP DATABASE IF EXISTS tenant_switch_test')
            cursor.execute('DROP DATABASE IF EXISTS tenant_switch_test_2')
            cursor.execute('DROP DATABASE IF EXISTS fake_tenant_db')
        super().tearDownClass()

    def test_starts_on_public_schema(self):
        self.assertEqual(connection.schema_name, get_public_schema_name())

    def test_set_schema_switches_current_database(self):
        connection.set_schema('tenant_switch_test')
        with connection.cursor() as cursor:
            cursor.execute('SELECT DATABASE()')
            self.assertEqual(cursor.fetchone()[0], 'tenant_switch_test')
        connection.set_schema_to_public()

    def test_set_schema_to_public_returns_to_public_database(self):
        connection.set_schema('tenant_switch_test_2')
        connection.set_schema_to_public()
        with connection.cursor() as cursor:
            cursor.execute('SELECT DATABASE()')
            self.assertEqual(cursor.fetchone()[0], get_public_schema_name())

    def test_set_tenant_accepts_fake_tenant(self):
        connection.set_tenant(FakeTenant(schema_name='fake_tenant_db'))
        self.assertEqual(connection.schema_name, 'fake_tenant_db')
        connection.set_schema_to_public()
```

- [ ] **Step 3: Run test to verify it fails**

Run:
```bash
cd dts_test_project
DATABASE_ENGINE=django_tenants.mysql_backend DATABASE_PORT=3307 DATABASE_USER=root DATABASE_PASSWORD=testing \
  python manage.py test django_tenants.tests.test_mysql_backend -v2
```
Expected: FAIL — `ModuleNotFoundError` or `AttributeError` (no `DatabaseWrapper` yet in `mysql_backend.base`)

- [ ] **Step 4: Implement the `DatabaseWrapper`**

Append to `django_tenants/mysql_backend/base.py`:

```python
import warnings
from importlib import import_module

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string
import django.db.utils

from django_tenants.utils import get_public_schema_name, get_limit_set_calls, FakeTenant

ORIGINAL_BACKEND = getattr(settings, 'ORIGINAL_BACKEND', 'django.db.backends.mysql')
original_backend = import_module(ORIGINAL_BACKEND + '.base')

EXTRA_SET_TENANT_METHOD_PATH = getattr(settings, 'EXTRA_SET_TENANT_METHOD_PATH', None)
if EXTRA_SET_TENANT_METHOD_PATH:
    EXTRA_SET_TENANT_METHOD = import_string(EXTRA_SET_TENANT_METHOD_PATH)
else:
    EXTRA_SET_TENANT_METHOD = None


class DatabaseWrapper(original_backend.DatabaseWrapper):
    """
    Adds the capability to switch the active MySQL database using
    set_tenant()/set_schema(), mirroring the Postgres backend's
    search_path-based tenant switching. MySQL has no concept of a search
    path spanning databases, so switching means literally changing which
    database this connection currently has selected, via `USE`.
    """
    include_public_schema = True

    def __init__(self, *args, **kwargs):
        self.active_schema_name = None
        self.tenant = None
        self.schema_name = None
        super().__init__(*args, **kwargs)

        self.set_schema_to_public()

    def close(self):
        self.active_schema_name = None
        super().close()

    def set_tenant(self, tenant, include_public=True):
        """
        Main API method to set the current database schema, but it does
        not actually modify the db connection.
        """
        self.tenant = tenant
        self.schema_name = tenant.schema_name
        self.include_public_schema = include_public
        self.set_settings_schema(self.schema_name)

        if EXTRA_SET_TENANT_METHOD:
            EXTRA_SET_TENANT_METHOD(self, tenant)

        self.active_schema_name = None

        from django.contrib.contenttypes.models import ContentType
        ContentType.objects.clear_cache()

    def set_schema(self, schema_name, include_public=True, tenant_type=None):
        """
        Main API method to set the current database schema, but it does
        not actually modify the db connection.
        """
        self.set_tenant(FakeTenant(schema_name=schema_name, tenant_type=tenant_type), include_public)

    def set_schema_to_public(self):
        """
        Instructs to stay in the common 'public' database.
        """
        self.set_tenant(FakeTenant(schema_name=get_public_schema_name()))

    def set_settings_schema(self, schema_name):
        self.settings_dict['SCHEMA'] = schema_name
        self.settings_dict['NAME'] = schema_name

    def get_schema(self):
        warnings.warn("connection.get_schema() is deprecated, use connection.schema_name instead.",
                      category=DeprecationWarning)
        return self.schema_name

    def get_tenant(self):
        warnings.warn("connection.get_tenant() is deprecated, use connection.tenant instead.",
                      category=DeprecationWarning)
        return self.tenant

    def _cursor(self, name=None):
        """
        Every MySQL db operation must go through this to get the cursor
        handle. We switch the active database here.
        """
        if name:
            cursor = super()._cursor(name=name)
        else:
            cursor = super()._cursor()

        if (not get_limit_set_calls()) or self.active_schema_name != self.schema_name:
            if not self.schema_name:
                raise ImproperlyConfigured("Database schema not set. Did you forget "
                                           "to call set_schema() or set_tenant()?")

            _check_schema_name(self.schema_name)

            try:
                cursor.execute('USE `{0}`'.format(self.schema_name))
            except django.db.utils.DatabaseError:
                self.active_schema_name = None
            else:
                self.active_schema_name = self.schema_name

        return cursor
```

- [ ] **Step 5: Run test to verify it passes**

Run:
```bash
cd dts_test_project
DATABASE_ENGINE=django_tenants.mysql_backend DATABASE_PORT=3307 DATABASE_USER=root DATABASE_PASSWORD=testing \
  python manage.py test django_tenants.tests.test_mysql_backend -v2
```
Expected: PASS, 4 tests

- [ ] **Step 6: Confirm the Postgres suite still passes unmodified**

Run: `cd dts_test_project && python manage.py test -v2 django_tenants`
Expected: PASS (unaffected — `DATABASE_ENGINE` defaults to Postgres)

- [ ] **Step 7: Commit**

```bash
git add django_tenants/mysql_backend/base.py dts_test_project/dts_test_project/settings.py django_tenants/tests/test_mysql_backend.py
git commit -m "Add MySQL DatabaseWrapper with USE-based tenant switching"
```

---

### Task 4: `utils.py` vendor dispatch

`schema_exists()` and `schema_rename()` hardcode Postgres catalog queries/syntax. Add MySQL-aware branches, plus the new helpers `models.py` will use in Task 5 to stop hardcoding Postgres SQL.

**Files:**
- Modify: `django_tenants/utils.py:193-230` (`schema_exists`, `schema_rename`), `:285-313` (`validate_extra_extensions`, no functional change but a docstring note)
- Test: `django_tenants/tests/test_mysql_backend.py`

**Interfaces:**
- Consumes: `django_tenants.mysql_backend.base._check_schema_name` (Task 2/3).
- Produces: `django_tenants.utils.get_schema_name_validator() -> callable`, `django_tenants.utils.create_schema_sql(schema_name, connection) -> str`, `django_tenants.utils.drop_schema_sql(schema_name, connection) -> str` — consumed by `models.py` in Task 5.

- [ ] **Step 1: Write the failing tests**

Add to `django_tenants/tests/test_mysql_backend.py`:

```python
from django.core.exceptions import ValidationError

from django_tenants.utils import (
    create_schema_sql,
    drop_schema_sql,
    get_schema_name_validator,
    schema_exists,
    schema_rename,
)


@mysql_only
class MySQLUtilsDispatchTestCase(TransactionTestCase):
    def test_schema_exists_true_for_public(self):
        self.assertTrue(schema_exists(get_public_schema_name()))

    def test_schema_exists_false_for_missing_database(self):
        self.assertFalse(schema_exists('does_not_exist_db'))

    def test_schema_rename_raises_not_implemented(self):
        class _Tenant:
            schema_name = 'whatever'
        with self.assertRaises(NotImplementedError):
            schema_rename(_Tenant(), 'new_name')

    def test_get_schema_name_validator_returns_mysql_validator(self):
        from django_tenants.mysql_backend.base import _check_schema_name
        self.assertIs(get_schema_name_validator(), _check_schema_name)

    def test_get_schema_name_validator_rejects_invalid_name(self):
        validator = get_schema_name_validator()
        with self.assertRaises(ValidationError):
            validator('invalid/name')

    def test_create_schema_sql_uses_create_database(self):
        self.assertEqual(create_schema_sql('my_tenant', connection), 'CREATE DATABASE `my_tenant`')

    def test_drop_schema_sql_uses_drop_database(self):
        self.assertEqual(drop_schema_sql('my_tenant', connection), 'DROP DATABASE `my_tenant`')
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
cd dts_test_project
DATABASE_ENGINE=django_tenants.mysql_backend DATABASE_PORT=3307 DATABASE_USER=root DATABASE_PASSWORD=testing \
  python manage.py test django_tenants.tests.test_mysql_backend.MySQLUtilsDispatchTestCase -v2
```
Expected: FAIL — `ImportError: cannot import name 'create_schema_sql'`

- [ ] **Step 3: Implement the dispatch in `utils.py`**

Replace `schema_exists()` (lines 193-209):

```python
def schema_exists(schema_name, database=get_tenant_database_alias()):
    _connection = connections[database]
    cursor = _connection.cursor()

    # check if this schema already exists in the db
    if _connection.vendor == 'mysql':
        sql = 'SELECT EXISTS(SELECT 1 FROM information_schema.schemata WHERE LOWER(schema_name) = LOWER(%s))'
    else:
        sql = 'SELECT EXISTS(SELECT 1 FROM pg_catalog.pg_namespace WHERE LOWER(nspname) = LOWER(%s))'
    cursor.execute(sql, (schema_name, ))

    row = cursor.fetchone()
    if row:
        exists = row[0]
    else:
        exists = False

    cursor.close()

    return exists
```

Replace `schema_rename()` (lines 212-230):

```python
def schema_rename(tenant, new_schema_name, database=get_tenant_database_alias(), save=True):
    """
    This renames a schema to a new name. It checks to see if it exists first
    """
    _connection = connections[database]

    if _connection.vendor == 'mysql':
        raise NotImplementedError(
            "schema_rename() is not supported on the MySQL backend: MySQL has no "
            "RENAME DATABASE command. Renaming a tenant requires recreating its "
            "database and copying every table, which is not yet implemented."
        )

    from django_tenants.postgresql_backend.base import is_valid_schema_name
    cursor = _connection.cursor()

    if schema_exists(new_schema_name):
        raise ValidationError("New schema name already exists")
    if not is_valid_schema_name(new_schema_name):
        raise ValidationError("Invalid string used for the schema name.")
    sql = 'ALTER SCHEMA {0} RENAME TO {1}'.format(connection.ops.quote_name(tenant.schema_name),
                                                  connection.ops.quote_name(new_schema_name))
    cursor.execute(sql)
    cursor.close()
    tenant.schema_name = new_schema_name
    if save:
        tenant.save()
```

Add three new functions right after `schema_rename()`:

```python
def get_schema_name_validator():
    """
    Returns the schema-name-validating function appropriate for the
    configured tenant database's vendor. Postgres and MySQL have different
    identifier rules, so this dispatches rather than hardcoding one.
    """
    vendor = connections[get_tenant_database_alias()].vendor
    if vendor == 'mysql':
        from django_tenants.mysql_backend.base import _check_schema_name
    else:
        from django_tenants.postgresql_backend.base import _check_schema_name
    return _check_schema_name


def create_schema_sql(schema_name, connection):
    """
    Returns the vendor-appropriate SQL to create a tenant's schema/database.
    """
    if connection.vendor == 'mysql':
        return 'CREATE DATABASE `{0}`'.format(schema_name)
    return 'CREATE SCHEMA "{0}"'.format(schema_name)


def drop_schema_sql(schema_name, connection):
    """
    Returns the vendor-appropriate SQL to drop a tenant's schema/database.
    MySQL has no CASCADE keyword for DROP DATABASE — dropping a database
    already drops everything inside it.
    """
    if connection.vendor == 'mysql':
        return 'DROP DATABASE `{0}`'.format(schema_name)
    return 'DROP SCHEMA "{0}" CASCADE'.format(schema_name)
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
cd dts_test_project
DATABASE_ENGINE=django_tenants.mysql_backend DATABASE_PORT=3307 DATABASE_USER=root DATABASE_PASSWORD=testing \
  python manage.py test django_tenants.tests.test_mysql_backend.MySQLUtilsDispatchTestCase -v2
```
Expected: PASS, 7 tests

- [ ] **Step 5: Confirm the Postgres suite still passes**

Run: `cd dts_test_project && python manage.py test -v2 django_tenants`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add django_tenants/utils.py django_tenants/tests/test_mysql_backend.py
git commit -m "Add MySQL vendor dispatch for schema_exists/schema_rename and schema SQL helpers"
```

---

### Task 5: `models.py` refactor — remove hardcoded Postgres SQL

`TenantMixin.create_schema()`/`_drop_schema()` currently run raw Postgres SQL directly, and the `schema_name` field's validator is imported unconditionally from `postgresql_backend.base`. Both move to the vendor-dispatch helpers from Task 4.

**Files:**
- Modify: `django_tenants/models.py:1-14` (imports), `:39-40` (validator), `:171-213` (`create_schema`), `:143-155` (`_drop_schema`)
- Test: `django_tenants/tests/test_mysql_backend.py`, existing `django_tenants/tests/test_tenants.py` (regression, unmodified)

**Interfaces:**
- Consumes: `django_tenants.utils.get_schema_name_validator`, `create_schema_sql`, `drop_schema_sql` (Task 4).

- [ ] **Step 1: Write the failing test**

Add to `django_tenants/tests/test_mysql_backend.py`:

```python
from django_tenants.utils import get_tenant_model, get_tenant_domain_model


@mysql_only
class MySQLTenantLifecycleTestCase(TransactionTestCase):
    def test_create_and_drop_tenant_creates_real_database(self):
        Tenant = get_tenant_model()
        Domain = get_tenant_domain_model()

        tenant = Tenant(schema_name='mysql_lifecycle_test')
        tenant.save()
        domain = Domain(tenant=tenant, domain='mysql-lifecycle.test.com')
        domain.save()

        self.assertTrue(schema_exists('mysql_lifecycle_test'))

        domain.delete()
        tenant.delete(force_drop=True)

        self.assertFalse(schema_exists('mysql_lifecycle_test'))

    def test_fake_migrations_cloning_raises_not_implemented(self):
        from django.test.utils import override_settings

        Tenant = get_tenant_model()
        with override_settings(TENANT_CREATION_FAKES_MIGRATIONS=True, TENANT_BASE_SCHEMA=get_public_schema_name()):
            tenant = Tenant(schema_name='mysql_clone_attempt')
            with self.assertRaises(NotImplementedError):
                tenant.save()
```

This test module needs `SHARED_APPS`/`TENANT_APPS` configured the same way `BaseTestCase` does. Add the import and base class at the top of `test_mysql_backend.py`:

```python
from django_tenants.tests.testcases import BaseTestCase
```

Change `MySQLTenantLifecycleTestCase(TransactionTestCase)` to `MySQLTenantLifecycleTestCase(BaseTestCase)` so `TENANT_MODEL`/`TENANT_DOMAIN_MODEL`/`SHARED_APPS`/`TENANT_APPS` are already wired up (see `BaseTestCase` in `django_tenants/tests/testcases.py`).

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
cd dts_test_project
DATABASE_ENGINE=django_tenants.mysql_backend DATABASE_PORT=3307 DATABASE_USER=root DATABASE_PASSWORD=testing \
  python manage.py test django_tenants.tests.test_mysql_backend.MySQLTenantLifecycleTestCase -v2
```
Expected: FAIL — `django.db.utils.ProgrammingError` (raw `CREATE SCHEMA "..."` isn't valid MySQL syntax) on the first test, and no `NotImplementedError` raised on the second (it currently tries to run Postgres-only `CloneSchema` and fails differently).

- [ ] **Step 3: Update imports in `models.py`**

Replace:

```python
from django_tenants.clone import CloneSchema
from .postgresql_backend.base import _check_schema_name
from .signals import post_schema_sync, schema_needs_to_be_sync
from .utils import get_creation_fakes_migrations, get_tenant_base_schema
from .utils import schema_exists, get_tenant_domain_model, get_public_schema_name, get_tenant_database_alias
```

with:

```python
from django_tenants.clone import CloneSchema
from .signals import post_schema_sync, schema_needs_to_be_sync
from .utils import get_creation_fakes_migrations, get_tenant_base_schema
from .utils import (
    create_schema_sql,
    drop_schema_sql,
    get_public_schema_name,
    get_schema_name_validator,
    get_tenant_database_alias,
    get_tenant_domain_model,
    schema_exists,
)
```

- [ ] **Step 4: Update the field validator**

Replace:

```python
    schema_name = models.CharField(max_length=63, unique=True, db_index=True,
                                   validators=[_check_schema_name])
```

with:

```python
    schema_name = models.CharField(max_length=63, unique=True, db_index=True,
                                   validators=[get_schema_name_validator()])
```

- [ ] **Step 5: Update `create_schema()`**

Replace the body of `create_schema()` (originally lines 171-213):

```python
    def create_schema(self, check_if_exists=False, sync_schema=True,
                      verbosity=1):
        """
        Creates the schema 'schema_name' for this tenant. Optionally checks if
        the schema already exists before creating it. Returns true if the
        schema was created, false otherwise.
        """

        # safety check
        connection = connections[get_tenant_database_alias()]
        get_schema_name_validator()(self.schema_name)
        cursor = connection.cursor()

        if check_if_exists and schema_exists(self.schema_name):
            return False

        fake_migrations = get_creation_fakes_migrations()

        if sync_schema:
            if fake_migrations:
                if connection.vendor == 'mysql':
                    raise NotImplementedError(
                        "TENANT_CREATION_FAKES_MIGRATIONS/TENANT_BASE_SCHEMA cloning is "
                        "not supported on the MySQL backend yet."
                    )
                # copy tables and data from provided model schema
                base_schema = get_tenant_base_schema()
                clone_schema = CloneSchema()
                clone_schema.clone_schema(
                    base_schema, self.schema_name, self.clone_mode
                )

                call_command('migrate_schemas',
                             tenant=True,
                             fake=True,
                             schema_name=self.schema_name,
                             interactive=False,
                             verbosity=verbosity)
            else:
                # create the schema
                cursor.execute(create_schema_sql(self.schema_name, connection))
                call_command('migrate_schemas',
                             tenant=True,
                             schema_name=self.schema_name,
                             interactive=False,
                             verbosity=verbosity)

        connection.set_schema_to_public()
```

- [ ] **Step 6: Update `_drop_schema()`**

Replace the last two lines of `_drop_schema()`:

```python
        if has_schema and schema_exists(self.schema_name) and (self.auto_drop_schema or force_drop):
            self.pre_drop()
            cursor = connection.cursor()
            cursor.execute('DROP SCHEMA "%s" CASCADE' % self.schema_name)
```

with:

```python
        if has_schema and schema_exists(self.schema_name) and (self.auto_drop_schema or force_drop):
            self.pre_drop()
            cursor = connection.cursor()
            cursor.execute(drop_schema_sql(self.schema_name, connection))
```

- [ ] **Step 7: Run test to verify it passes**

Run:
```bash
cd dts_test_project
DATABASE_ENGINE=django_tenants.mysql_backend DATABASE_PORT=3307 DATABASE_USER=root DATABASE_PASSWORD=testing \
  python manage.py test django_tenants.tests.test_mysql_backend.MySQLTenantLifecycleTestCase -v2
```
Expected: PASS, 2 tests

- [ ] **Step 8: Confirm the full Postgres suite still passes (this file is shared by both backends)**

Run: `cd dts_test_project && python manage.py test -v2 django_tenants`
Expected: PASS — this is the most important regression check in this plan, since `models.py` is used by every existing Postgres test.

- [ ] **Step 9: Commit**

```bash
git add django_tenants/models.py django_tenants/tests/test_mysql_backend.py
git commit -m "Remove hardcoded Postgres SQL from TenantMixin, dispatch by vendor"
```

---

### Task 6: Guard `clone_tenant` and `rename_schema` commands for MySQL

`rename_schema` already raises `NotImplementedError` via `schema_rename()` (Task 4). `clone_tenant` calls `CloneSchema` directly and needs its own guard.

**Files:**
- Modify: `django_tenants/management/commands/clone_tenant.py:1-19`
- Test: `django_tenants/tests/test_mysql_backend.py`

- [ ] **Step 1: Write the failing test**

Add to `django_tenants/tests/test_mysql_backend.py`:

```python
from django.core.management import call_command
from django.core.management.base import CommandError


@mysql_only
class MySQLGuardedCommandsTestCase(BaseTestCase):
    def test_clone_tenant_command_raises_not_implemented(self):
        Tenant = get_tenant_model()
        Domain = get_tenant_domain_model()
        tenant = Tenant(schema_name='mysql_clone_source')
        tenant.save()
        Domain(tenant=tenant, domain='mysql-clone-source.test.com').save()

        with self.assertRaises(NotImplementedError):
            call_command(
                'clone_tenant',
                clone_from='mysql_clone_source',
                clone_tenant_fields=False,
                schema_name='mysql_clone_target',
                name='Cloned',
                domain_domain='mysql-clone-target.test.com',
                domain_is_primary=True,
            )

    def test_rename_schema_command_raises_not_implemented(self):
        Tenant = get_tenant_model()
        Domain = get_tenant_domain_model()
        tenant = Tenant(schema_name='mysql_rename_source')
        tenant.save()
        Domain(tenant=tenant, domain='mysql-rename-source.test.com').save()

        with self.assertRaises(NotImplementedError):
            call_command('rename_schema', rename_from='mysql_rename_source', rename_to='mysql_rename_target')
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
cd dts_test_project
DATABASE_ENGINE=django_tenants.mysql_backend DATABASE_PORT=3307 DATABASE_USER=root DATABASE_PASSWORD=testing \
  python manage.py test django_tenants.tests.test_mysql_backend.MySQLGuardedCommandsTestCase -v2
```
Expected: `test_rename_schema_command_raises_not_implemented` PASSES already (Task 4 covers it). `test_clone_tenant_command_raises_not_implemented` FAILS — `clone_tenant` currently tries to run Postgres-only `CloneSchema` SQL and errors with something other than `NotImplementedError`.

- [ ] **Step 3: Guard `clone_tenant.py`**

In `django_tenants/management/commands/clone_tenant.py`, add the guard at the top of `handle()`. First check the current `handle()` signature with `grep -n "def handle" django_tenants/management/commands/clone_tenant.py`, then add right after the `def handle(self, *args, **options):` line:

```python
    def handle(self, *args, **options):
        from django.db import connection as _connection
        if _connection.vendor == 'mysql':
            raise NotImplementedError(
                "clone_tenant is not supported on the MySQL backend yet: it depends on "
                "CloneSchema, which is a Postgres-only PL/pgSQL procedure."
            )
```

(Keep every existing line of `handle()` below this guard unchanged.)

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
cd dts_test_project
DATABASE_ENGINE=django_tenants.mysql_backend DATABASE_PORT=3307 DATABASE_USER=root DATABASE_PASSWORD=testing \
  python manage.py test django_tenants.tests.test_mysql_backend.MySQLGuardedCommandsTestCase -v2
```
Expected: PASS, 2 tests

- [ ] **Step 5: Confirm the Postgres suite still passes**

Run: `cd dts_test_project && python manage.py test -v2 django_tenants`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add django_tenants/management/commands/clone_tenant.py django_tenants/tests/test_mysql_backend.py
git commit -m "Guard clone_tenant command against use with the MySQL backend"
```

---

### Task 7: End-to-end MySQL smoke test + `run_tests_mysql.sh`

Prove the whole stack works together: create a public tenant, create a real tenant, run `migrate_schemas`, switch between them, verify data isolation — using both the `standard` and `multiprocessing` migration executors, mirroring what `run_tests.sh` already proves for Postgres.

**Files:**
- Create: `run_tests_mysql.sh`
- Test: `django_tenants/tests/test_mysql_backend.py` (multi-tenant isolation + both executors)

- [ ] **Step 1: Write the failing test**

Add to `django_tenants/tests/test_mysql_backend.py`:

```python
from django.core.management import call_command
from django.db import connection


@mysql_only
class MySQLMultiTenantIsolationTestCase(BaseTestCase):
    def test_data_is_isolated_between_tenant_databases(self):
        from dts_test_app.models import DummyModel

        Tenant = get_tenant_model()
        Domain = get_tenant_domain_model()

        tenant1 = Tenant(schema_name='mysql_isolation_1')
        tenant1.save()
        Domain(tenant=tenant1, domain='mysql-isolation-1.test.com').save()

        tenant2 = Tenant(schema_name='mysql_isolation_2')
        tenant2.save()
        Domain(tenant=tenant2, domain='mysql-isolation-2.test.com').save()

        connection.set_tenant(tenant1)
        DummyModel(name='only in tenant 1').save()

        connection.set_tenant(tenant2)
        self.assertEqual(DummyModel.objects.count(), 0)

        connection.set_tenant(tenant1)
        self.assertEqual(DummyModel.objects.count(), 1)

        connection.set_schema_to_public()
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
cd dts_test_project
DATABASE_ENGINE=django_tenants.mysql_backend DATABASE_PORT=3307 DATABASE_USER=root DATABASE_PASSWORD=testing \
  python manage.py test django_tenants.tests.test_mysql_backend.MySQLMultiTenantIsolationTestCase -v2
```
Expected: FAIL if any earlier task is incomplete; if Tasks 1-6 are done correctly this may already PASS — if so, skip to Step 4 (nothing to implement, this step is a confirming regression test for the feature as a whole).

- [ ] **Step 3: Fix anything the test surfaces**

If it fails, the failure will point at whichever earlier task's behavior is incomplete (e.g. `migrate_schemas` not creating `django_migrations` correctly per-database) — fix it in the relevant file from Tasks 1-6, don't add new abstractions here.

- [ ] **Step 4: Run test to verify it passes**

Run the same command as Step 2.
Expected: PASS

- [ ] **Step 5: Create `run_tests_mysql.sh`**

Create `run_tests_mysql.sh` at the repo root:

```bash
#!/bin/bash

set -e

function greenprint {
    echo -e "\033[1;32m[$(date -Isecond)] ${1}\033[0m"
}

DATABASE=${DATABASE_HOST:-localhost}
DATABASE_PORT=${DATABASE_PORT:-3306}
echo "Database: $DATABASE"

while ! nc -v -w 1 "$DATABASE" "$DATABASE_PORT" > /dev/null 2>&1 < /dev/null; do
    i=`expr $i + 1`
    if [ $i -ge 50 ]; then
        echo "$(date) - $DATABASE:$DATABASE_PORT still not reachable, giving up"
        exit 1
    fi
    echo "$(date) - waiting for $DATABASE:$DATABASE_PORT..."
    sleep 1
done
echo "mysql connection established"

export DATABASE_ENGINE=django_tenants.mysql_backend

pushd dts_test_project

EXECUTORS=( standard multiprocessing )

for executor in "${EXECUTORS[@]}"; do
    echo "Running MySQL-specific tests with executor: $executor"
    EXECUTOR=$executor PYTHONWARNINGS=d coverage run manage.py test -v2 django_tenants.tests.test_mysql_backend
done

greenprint "===== START INTEGRATION TESTS ====="

greenprint "Create public schema"
PYTHONWARNINGS=d python manage.py migrate --noinput
PYTHONWARNINGS=d python manage.py create_tenant --noinput \
    --schema_name public --name "Public tenant" --domain-domain public.example.com --domain-is_primary True

greenprint "Create a tenant"
PYTHONWARNINGS=d python manage.py create_tenant --noinput \
    --schema_name a-mysql-tenant --name "A MySQL tenant" --domain-domain a-mysql-tenant.example.com --domain-is_primary True

greenprint "Confirm clone_tenant is rejected on MySQL"
if PYTHONWARNINGS=d python manage.py clone_tenant \
    --clone_from a-mysql-tenant --clone_tenant_fields False \
    --schema_name a-cloned-tenant --name "Should fail" --domain-domain a-cloned-tenant.example.com --domain-is_primary True; then
    echo "clone_tenant should have failed on the MySQL backend but did not"
    exit 1
fi
greenprint "clone_tenant correctly rejected"
```

Make it executable: `chmod +x run_tests_mysql.sh`

- [ ] **Step 6: Run the full script locally against the docker container**

Run:
```bash
DATABASE_HOST=127.0.0.1 DATABASE_PORT=3307 DATABASE_USER=root DATABASE_PASSWORD=testing ./run_tests_mysql.sh
```
Expected: all steps pass, ending with "clone_tenant correctly rejected".

- [ ] **Step 7: Commit**

```bash
git add run_tests_mysql.sh django_tenants/tests/test_mysql_backend.py
git commit -m "Add MySQL end-to-end smoke test script"
```

---

### Task 8: CI job for MySQL

Mirror the existing `postgres_compatibility` job in `.github/workflows/code.yml`.

**Files:**
- Modify: `.github/workflows/code.yml`

- [ ] **Step 1: Add the `mysql_compatibility` job**

In `.github/workflows/code.yml`, add a new job after `postgres_compatibility` (check current indentation/structure with `grep -n "^  [a-z]" .github/workflows/code.yml` first):

```yaml
  mysql_compatibility:
    name: MySQL compatibility ${{ matrix.mysql-version }}
    runs-on: ubuntu-latest
    strategy:
      fail-fast: true
      matrix:
        python-version: ["3.13"]
        mysql-version: ["8.0", "8.4"]

    steps:
    - uses: actions/checkout@v5

    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v6
      with:
        python-version: ${{ matrix.python-version }}

    - name: Install MySQL client libraries
      run: |
        sudo apt-get update
        sudo apt-get install -y default-libmysqlclient-dev pkg-config

    - name: Install Python dependencies
      run: |
        pip install Django
        pip install -e ".[dev]"

    - name: Create database
      run: |
        docker run --name db -p 3306:3306 -d \
          -e MYSQL_ROOT_PASSWORD=testing -e MYSQL_DATABASE=public \
          mysql:${{ matrix.mysql-version }}

        sleep 15 # wait for server to initialize
        until docker exec db mysqladmin ping -h 127.0.0.1 -u root -ptesting --silent; do sleep 2; done

    - name: Run tests
      run: |
        export DATABASE_HOST=127.0.0.1
        export DATABASE_PORT=3306
        export DATABASE_USER=root
        export DATABASE_PASSWORD=testing
        ./run_tests_mysql.sh
```

- [ ] **Step 2: Validate the YAML syntax**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/code.yml'))"`
Expected: no error

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/code.yml
git commit -m "Add mysql_compatibility CI job"
```

---

### Task 9: Documentation

**Files:**
- Modify: `docs/install.rst`
- Modify: `README.rst`

- [ ] **Step 1: Add a MySQL section to `docs/install.rst`**

Add a new section right after the "Basic Settings" section (after line 56, before "The Tenant & Domain Model"):

```rst
MySQL Support (Beta)
=====================
As an alternative to PostgreSQL schemas, ``django-tenants`` supports MySQL by
giving each tenant its own real MySQL database, plus a shared "public"
database for ``SHARED_APPS`` tables.

.. code-block:: python

    DATABASES = {
        'default': {
            'ENGINE': 'django_tenants.mysql_backend',
            'NAME': 'public',
            # ..
        }
    }

The MySQL "public" database (named via ``PUBLIC_SCHEMA_NAME``, default
``'public'``) must exist before running ``migrate_schemas --shared`` for the
first time — create it once with ``CREATE DATABASE public;``. Unlike
PostgreSQL, MySQL doesn't ship a default schema inside every database, so
this step has no Postgres equivalent.

.. warning::

    **Cross-database joins are not supported.** PostgreSQL resolves
    unqualified table names across both the tenant and public schemas in a
    single connection via ``search_path``, which lets ``TENANT_APPS``
    models have foreign keys to ``SHARED_APPS`` models. MySQL has no
    equivalent — a connection only has one "current" database at a time.
    Do not add foreign keys from a ``TENANT_APPS`` model to a
    ``SHARED_APPS`` model when using the MySQL backend.

.. warning::

    The following are not yet supported on the MySQL backend and raise
    ``NotImplementedError``:

    - Tenant cloning (the ``clone_tenant`` command, and
      ``TENANT_CREATION_FAKES_MIGRATIONS``/``TENANT_BASE_SCHEMA``)
    - ``rename_schema`` (MySQL has no ``RENAME DATABASE`` command)

    ``PG_EXTRA_SEARCH_PATHS`` and other PostgreSQL-only settings are not
    applicable to the MySQL backend.

MariaDB is not tested or officially supported at this time, though the same
code path may work incidentally.
```

- [ ] **Step 2: Add a brief MySQL mention to `README.rst`**

Find the existing `ENGINE` snippet in `README.rst` (around line 125-131) and add one sentence directly after it pointing to the docs:

```rst
MySQL is also supported as of a recent version, using isolated databases per
tenant instead of PostgreSQL schemas — see :doc:`the installation docs
<docs/install>` for setup and current limitations.
```

- [ ] **Step 3: Build the docs to confirm no syntax errors**

Run: `cd docs && pip install Sphinx && make html`
Expected: builds without RST errors (warnings about the `:doc:` cross-reference path are fine if the existing docs already use relative doc references elsewhere — check with `grep -n ":doc:" *.rst docs/*.rst` and match the existing style if it differs from the snippet above).

- [ ] **Step 4: Commit**

```bash
git add docs/install.rst README.rst
git commit -m "Document MySQL backend setup and limitations"
```

---

## Self-Review Notes

- **Spec coverage:** Architecture (Tasks 3, 4, 5), schema create/drop/exists (Tasks 4, 5), migrations/routing requiring no changes (verified via regression runs in Tasks 1, 3, 5, 6, 7 rather than a dedicated task, since the spec's claim is "nothing to change"), cloning/rename guards (Tasks 5, 6), packaging (Task 2), testing/CI (Tasks 2, 3, 7, 8), docs (Task 9) — all covered.
- **Beyond the spec, found necessary during planning:** `template/loaders/cached.py`'s `FakeTenant` isinstance check (Task 1) — the spec didn't examine this file, but it would silently misbehave under MySQL without the fix, so it's included as a small prerequisite DRY fix rather than triggering a new brainstorming round.
- **Known gap, called out rather than hidden:** the pre-existing ~15 Postgres-oriented test files (`test_tenants.py`, `test_multi_types.py`, etc.) are not parameterized to run against MySQL in this plan — only new, MySQL-specific tests are added. This is stated explicitly in Global Constraints so it isn't mistaken for full test-suite parity.
