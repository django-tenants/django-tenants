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
    if options.get("list"):
        argv.append("--list")
    if not options.get("load_initial_data", True):
        argv.append("--no-initial-data")
    if options.get("database"):
        argv += ["--database", options["database"]]
    verbosity = options.get("verbosity", 1)
    if verbosity != 1:
        argv += ["--verbosity", str(verbosity)]
    return argv


def _manage_py() -> str:
    if sys.argv and sys.argv[0].endswith("manage.py"):
        return str(Path(sys.argv[0]).resolve())
    return str(Path("manage.py").resolve())


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
