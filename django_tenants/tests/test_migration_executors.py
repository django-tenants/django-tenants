"""Unit tests for the migration executors, focused on SubprocessExecutor.

These tests mock ``subprocess.run`` at the system boundary so no real
``migrate_schemas`` child processes are spawned. They assert on how the
executor selects parallelism, builds the child argv, and propagates failures.
"""

from unittest import mock

from django.test import SimpleTestCase, override_settings

from django_tenants.management.commands.migrate_schemas import MigrateSchemasCommand
from django_tenants.migration_executors import get_executor
from django_tenants.migration_executors.subproc import SubprocessExecutor


SUBPROC = "django_tenants.migration_executors.subproc"


def _contains_subsequence(seq, sub):
    """Return True if ``sub`` appears as a contiguous slice of ``seq``."""
    n = len(sub)
    return any(list(seq[i:i + n]) == list(sub) for i in range(len(seq) - n + 1))


def make_executor(args=(), **options):
    options.setdefault("verbosity", 1)
    return SubprocessExecutor(list(args), options)


class SubprocessExecutorRegistrationTests(SimpleTestCase):
    def test_codename_is_subprocess(self):
        self.assertEqual(SubprocessExecutor.codename, "subprocess")

    def test_get_executor_resolves_subprocess(self):
        self.assertIs(get_executor("subprocess"), SubprocessExecutor)


class SubprocessExecutorPublicSchemaTests(SimpleTestCase):
    def test_public_schema_runs_in_process_not_subprocess(self):
        executor = make_executor()
        public = executor.PUBLIC_SCHEMA_NAME

        with mock.patch(f"{SUBPROC}.run_migrations") as run_migrations, \
                mock.patch(f"{SUBPROC}.subprocess.run") as subprocess_run:
            executor.run_migrations(tenants=[public])

        run_migrations.assert_called_once_with(
            executor.args, executor.options, executor.codename, public
        )
        subprocess_run.assert_not_called()


class SubprocessExecutorArgvTests(SimpleTestCase):
    def test_one_subprocess_per_tenant_with_expected_argv(self):
        executor = make_executor(
            args=("myapp",),
            interactive=False,
            fake=True,
            verbosity=2,
            database="default",
        )

        completed = mock.Mock(returncode=0)
        with mock.patch.object(executor, "_close_connections"), \
                mock.patch(f"{SUBPROC}.subprocess.run", return_value=completed) as run:
            executor.run_migrations(tenants=["tenant_a", "tenant_b"])

        self.assertEqual(run.call_count, 2)
        first_cmd = run.call_args_list[0].args[0]
        second_cmd = run.call_args_list[1].args[0]

        for cmd, schema in ((first_cmd, "tenant_a"), (second_cmd, "tenant_b")):
            self.assertIn("migrate_schemas", cmd)
            self.assertIn("--executor=standard", cmd)
            self.assertTrue(_contains_subsequence(cmd, ["--schema", schema]))
            self.assertIn("myapp", cmd)
            self.assertIn("--noinput", cmd)
            self.assertIn("--fake", cmd)
            self.assertTrue(_contains_subsequence(cmd, ["--verbosity", "2"]))
            self.assertTrue(_contains_subsequence(cmd, ["--database", "default"]))

    def test_parallel_flag_not_forwarded_to_child(self):
        executor = make_executor(parallel=5)

        completed = mock.Mock(returncode=0)
        with mock.patch(f"{SUBPROC}.subprocess.run", return_value=completed) as run:
            executor._run_in_subprocess("tenant_a")

        cmd = run.call_args.args[0]
        self.assertNotIn("--parallel", cmd)
        self.assertNotIn("5", cmd)


class SubprocessExecutorMaxParallelTests(SimpleTestCase):
    def test_cli_value_takes_precedence(self):
        executor = make_executor(parallel=4)
        with override_settings(TENANT_SUBPROCESS_PARALLEL=3):
            self.assertEqual(executor._max_parallel(), 4)

    def test_setting_used_when_no_cli_value(self):
        executor = make_executor(parallel=None)
        with override_settings(TENANT_SUBPROCESS_PARALLEL=3):
            self.assertEqual(executor._max_parallel(), 3)

    def test_default_is_one(self):
        executor = make_executor(parallel=None)
        self.assertEqual(executor._max_parallel(), 1)

    def test_values_are_clamped_to_at_least_one(self):
        self.assertEqual(make_executor(parallel=0)._max_parallel(), 1)
        self.assertEqual(make_executor(parallel=-5)._max_parallel(), 1)
        with override_settings(TENANT_SUBPROCESS_PARALLEL=0):
            self.assertEqual(make_executor(parallel=None)._max_parallel(), 1)


class SubprocessExecutorFailureTests(SimpleTestCase):
    def test_failing_child_raises_systemexit_and_stops(self):
        executor = make_executor()

        failing = mock.Mock(returncode=1)
        with mock.patch.object(executor, "_close_connections"), \
                mock.patch(f"{SUBPROC}.subprocess.run", return_value=failing) as run:
            with self.assertRaises(SystemExit) as ctx:
                executor.run_migrations(tenants=["tenant_a", "tenant_b"])

        self.assertEqual(ctx.exception.code, 1)
        self.assertEqual(run.call_count, 1)


class SubprocessExecutorParallelTests(SimpleTestCase):
    def test_parallel_failure_cancels_pending_and_propagates(self):
        executor = make_executor(parallel=2)
        tenants = ["fail", "slow1", "slow2", "slow3", "slow4", "slow5"]
        started = []
        lock = __import__("threading").Lock()

        def fake_run(schema_name):
            with lock:
                started.append(schema_name)
            if schema_name == "fail":
                raise SystemExit(1)
            import time
            time.sleep(0.3)

        with mock.patch.object(executor, "_close_connections"), \
                mock.patch.object(executor, "_run_in_subprocess", side_effect=fake_run):
            with self.assertRaises(SystemExit) as ctx:
                executor.run_migrations(tenants=tenants)

        self.assertEqual(ctx.exception.code, 1)
        self.assertIn("fail", started)
        # Cancellation must prevent at least some not-yet-started tenants from
        # ever launching.
        self.assertLess(len(started), len(tenants))


class MigrateSchemasParallelArgumentTests(SimpleTestCase):
    def _parse(self, argv):
        command = MigrateSchemasCommand()
        parser = command.create_parser("manage.py", "migrate_schemas")
        return parser.parse_args(argv)

    def test_parallel_defaults_to_none(self):
        namespace = self._parse([])
        self.assertIsNone(namespace.parallel)

    def test_parallel_parsed_as_int(self):
        namespace = self._parse(["--parallel", "4"])
        self.assertEqual(namespace.parallel, 4)


class SubprocessExecutorMultiTypeTests(SimpleTestCase):
    def test_run_multi_type_migrations_not_implemented(self):
        executor = make_executor()
        with self.assertRaises(NotImplementedError):
            executor.run_multi_type_migrations(tenants=[("schema", "type1")])
