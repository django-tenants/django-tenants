"""Subprocess-based migration executor.

Spawns a fresh ``python manage.py migrate_schemas --schema <name>`` process
for each tenant. Optionally runs N processes in parallel via a thread pool.

See migration_executors/__init__.py for executor selection and
docs/use.rst for configuration.
"""

from __future__ import annotations

import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import connections

from .base import MigrationExecutor, run_migrations


def _options_to_argv(options: dict) -> list[str]:
    """Translate parsed migrate_schemas options into CLI args for the child.

    Only flags that affect migration behavior are forwarded. The child always
    runs with ``--executor=standard`` to avoid recursive fan-out.
    """
    argv: list[str] = []
    if not options.get("interactive", True):
        argv.append("--noinput")
    if options.get("skip_checks"):
        argv.append("--skip-checks")
    if options.get("fake"):
        argv.append("--fake")
    if options.get("fake_initial"):
        argv.append("--fake-initial")
    if options.get("prune"):
        argv.append("--prune")
    if options.get("run_syncdb"):
        argv.append("--run-syncdb")
    if options.get("check_unapplied"):
        argv.append("--check")
    if options.get("plan"):
        argv.append("--plan")
    if not options.get("load_initial_data", True):
        argv.append("--no-initial-data")
    if options.get("database"):
        argv += ["--database", options["database"]]
    verbosity = options.get("verbosity", 1)
    if verbosity != 1:
        argv += ["--verbosity", str(verbosity)]
    # These two decide which settings the child loads at all. A parent invoked as
    # `manage.py migrate_schemas --settings=myproject.settings.production` would otherwise
    # spawn children that fall back to DJANGO_SETTINGS_MODULE -- quietly migrating against a
    # different database than the one asked for.
    if options.get("settings"):
        argv += ["--settings", options["settings"]]
    if options.get("pythonpath"):
        argv += ["--pythonpath", options["pythonpath"]]
    return argv


def _manage_py() -> str:
    """Locate the manage.py to spawn children with.

    Raises rather than handing subprocess a path that isn't there: when this executor is
    driven by something other than ``manage.py`` (``django-admin``, ``call_command()`` from
    application or task code, a test runner) ``sys.argv[0]`` points elsewhere and the cwd
    fallback need not contain a manage.py. Failing here says what is wrong; failing in the
    child surfaces as an opaque interpreter error once per tenant.
    """
    if sys.argv and sys.argv[0].endswith("manage.py"):
        candidate = Path(sys.argv[0]).resolve()
    else:
        candidate = Path("manage.py").resolve()
    if not candidate.is_file():
        raise ImproperlyConfigured(
            "The subprocess executor spawns 'manage.py migrate_schemas' per tenant, but no "
            "manage.py could be found (looked for {}). This happens when migrate_schemas is "
            "not run through manage.py -- via django-admin, or call_command() from "
            "application code. Use --executor=standard or --executor=multiprocessing "
            "instead, or run migrate_schemas through manage.py.".format(candidate)
        )
    return str(candidate)


class SubprocessExecutor(MigrationExecutor):
    """Run each tenant migration in a fresh OS process."""

    codename = "subprocess"

    def _max_parallel(self) -> int:
        explicit = self.options.get("parallel")
        if explicit is not None:
            return max(1, int(explicit))
        return max(1, int(getattr(settings, "TENANT_SUBPROCESS_PARALLEL", 1)))

    def _close_connections(self) -> None:
        connection = connections[self.TENANT_DB_ALIAS]
        connection.close()
        connection.connection = None

    def _run_in_subprocess(self, schema_name: str) -> None:
        cmd: list[str] = [
            sys.executable,
            _manage_py(),
            "migrate_schemas",
            "--executor=standard",
            "--schema",
            schema_name,
        ]
        cmd += list(self.args)
        cmd += _options_to_argv(self.options)
        completed = subprocess.run(cmd)
        if completed.returncode != 0:
            # Match StandardExecutor: propagate the child's rc and stop the
            # tenant loop. Covers both real migrate failures and --check
            # signaling pending migrations.
            raise SystemExit(completed.returncode)

    def _run_parallel(self, tenants: list[str], parallel: int) -> None:
        # In-flight subprocesses cannot be safely killed mid-DDL. On first
        # failure we cancel not-yet-started tasks and let the pool's
        # __exit__ wait for in-flight to drain before the SystemExit
        # propagates.
        with ThreadPoolExecutor(max_workers=parallel) as pool:
            futures = [
                pool.submit(self._run_in_subprocess, name) for name in tenants
            ]
            try:
                for f in as_completed(futures):
                    f.result()
            except SystemExit:
                for f in futures:
                    f.cancel()
                raise

    def run_migrations(self, tenants=None):
        tenants = list(tenants or [])
        if self.PUBLIC_SCHEMA_NAME in tenants:
            # Public is a single schema; running it in-process avoids paying
            # subprocess startup for the no-leak case.
            run_migrations(
                self.args, self.options, self.codename, self.PUBLIC_SCHEMA_NAME
            )
            tenants.remove(self.PUBLIC_SCHEMA_NAME)
        if not tenants:
            return
        self._close_connections()
        parallel = self._max_parallel()
        if parallel == 1:
            for schema_name in tenants:
                self._run_in_subprocess(schema_name)
            return
        self._run_parallel(tenants, parallel)

    def run_multi_type_migrations(self, tenants):
        # Implement analogously to run_migrations if/when needed; see the
        # multi-type code in MultiprocessingExecutor for argument shape.
        raise NotImplementedError(
            "SubprocessExecutor does not yet support multi-type tenants."
        )
