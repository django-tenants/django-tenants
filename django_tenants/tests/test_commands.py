import contextlib
import io
import json
from unittest import mock

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError, OutputWrapper
from django.db import connection

from django_tenants.management.commands.all_tenants_command import Command as AllTenantsCommand
from django_tenants.test.cases import FastTenantTestCase
from django_tenants.tests.testcases import BaseTestCase
from django_tenants.utils import get_tenant_model, get_public_schema_name
from dts_test_app.models import DummyModel


class TenantCommandTestCase(FastTenantTestCase):

    def test_pass_arguments_to_subcommand(self):
        DummyModel(name="Schemas are").save()
        DummyModel(name="awesome!").save()

        dump_data = [
            {
                "model": "dts_test_app.dummymodel",
                "pk": 1,
                "fields": {
                    "name": "Schemas are"
                }
            },
            {
                "model": "dts_test_app.dummymodel",
                "pk": 2,
                "fields": {
                    "name": "awesome!"
                }
            }
        ]
        # json.dump has extra level of indentation comparing to dumpdata, so we remove it
        indented_dump_data = json.dumps(dump_data, indent=4).replace('\n    ', '\n')+'\n'

        out = io.StringIO()
        call_command(
            'tenant_command',
            'dumpdata',
            'dts_test_app.DummyModel',
            '--indent=4',
            schema=self.tenant.schema_name,
            stdout=out,
        )
        self.assertEqual(
            out.getvalue(),  # test that stdout is passed
            indented_dump_data  # test that indent is passed
        )


class AllTenantsCommandTestCase(BaseTestCase):
    """
    all_tenants_command is documented but had no handle(), so every
    call_command() of it raised NotImplementedError. #627
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.sync_shared()

    def setUp(self):
        super().setUp()
        # TransactionTestCase flushes rows between tests, so build the tenants
        # each time rather than once for the class.
        self.public_tenant = get_tenant_model().objects.create(schema_name=get_public_schema_name())
        self.tenant = get_tenant_model().objects.create(schema_name='all_tenants_test')

    def tearDown(self):
        connection.set_schema_to_public()
        self.tenant.delete(force_drop=True)
        # Only the row -- dropping the public schema would take the shared tables
        # with it. auto_drop_schema is set explicitly because other test cases
        # flip it on the model class.
        self.public_tenant.auto_drop_schema = False
        self.public_tenant.delete()
        super().tearDown()

    @staticmethod
    def record_schemas():
        """
        Stands in for the wrapped command, noting the schema it was run under.
        """
        schemas = []

        def wrapped(*args, **kwargs):
            schemas.append(connection.schema_name)

        return schemas, mock.patch(
            'django_tenants.management.commands.all_tenants_command.call_command',
            side_effect=wrapped,
        )

    def test_call_command_runs_the_wrapped_command_on_every_tenant(self):
        schemas, patched = self.record_schemas()

        with patched:
            call_command('all_tenants_command', 'check', stdout=io.StringIO())

        self.assertCountEqual(schemas, [get_public_schema_name(), 'all_tenants_test'])

    def test_no_public_excludes_the_public_schema(self):
        schemas, patched = self.record_schemas()

        with patched:
            call_command('all_tenants_command', 'check', no_public=True, stdout=io.StringIO())

        self.assertEqual(schemas, ['all_tenants_test'])

    def test_arguments_are_passed_to_the_wrapped_command(self):
        with mock.patch('django_tenants.management.commands.all_tenants_command.call_command') as mocked:
            call_command('all_tenants_command', 'dumpdata', 'dts_test_app.DummyModel', stdout=io.StringIO())

        self.assertEqual(mocked.call_count, 2)
        for call in mocked.call_args_list:
            self.assertEqual(call.args, ('dumpdata', 'dts_test_app.DummyModel'))

    def test_unknown_command_raises_command_error(self):
        with self.assertRaisesRegex(CommandError, 'Unknown command'):
            call_command('all_tenants_command', 'no_such_command', stdout=io.StringIO())

    # The command line goes through run_from_argv() rather than handle(), so it
    # needs driving separately from the call_command() tests above.

    def run_from_argv(self, *args):
        """
        Runs the command the way manage.py does, capturing its own output.
        """
        command = AllTenantsCommand()
        stdout, stderr = io.StringIO(), io.StringIO()
        command.stdout, command.stderr = OutputWrapper(stdout), OutputWrapper(stderr)
        command.run_from_argv(['manage.py', 'all_tenants_command', *args])
        return stdout.getvalue(), stderr.getvalue()

    @staticmethod
    def wrapped_command(calls):
        """
        Stands in for the wrapped command class that run_from_argv() loads.
        """
        class Wrapped(BaseCommand):
            def run_from_argv(self, argv):
                calls.append((argv, connection.schema_name))

        return Wrapped()

    def test_command_line_runs_the_wrapped_command_on_every_tenant(self):
        calls = []

        with mock.patch('django_tenants.management.commands.all_tenants_command.load_command_class',
                        return_value=self.wrapped_command(calls)):
            self.run_from_argv('dumpdata', '--indent=4')

        self.assertCountEqual([schema for _, schema in calls],
                              [get_public_schema_name(), 'all_tenants_test'])
        # The wrapped command's own options are handed straight through.
        for argv, _ in calls:
            self.assertEqual(argv, ['manage.py', 'dumpdata', '--indent=4'])

    def test_command_line_no_public_is_stripped_from_anywhere(self):
        calls = []

        with mock.patch('django_tenants.management.commands.all_tenants_command.load_command_class',
                        return_value=self.wrapped_command(calls)):
            self.run_from_argv('dumpdata', '--no-public', 'dts_test_app.DummyModel')

        self.assertEqual([schema for _, schema in calls], ['all_tenants_test'])
        self.assertEqual(calls[0][0], ['manage.py', 'dumpdata', 'dts_test_app.DummyModel'])

    def test_command_line_uses_an_already_loaded_command(self):
        calls = []
        loaded = self.wrapped_command(calls)

        # get_commands() hands back a BaseCommand instance rather than an app
        # label when a command is already loaded.
        with mock.patch('django_tenants.management.commands.all_tenants_command.get_commands',
                        return_value={'preloaded': loaded}):
            self.run_from_argv('preloaded')

        self.assertEqual(len(calls), 2)

    def test_command_line_unknown_command_exits_non_zero(self):
        with self.assertRaises(SystemExit) as raised:
            _, stderr = self.run_from_argv('no_such_command')

        self.assertEqual(raised.exception.code, 1)

    def test_command_line_without_a_command_name_reports_usage(self):
        # Falls back to Django's parser, which exits 2 on a missing argument.
        with self.assertRaises(SystemExit) as raised:
            with contextlib.redirect_stderr(io.StringIO()):
                self.run_from_argv()

        self.assertEqual(raised.exception.code, 2)

    def test_command_line_help_is_not_treated_as_a_command_name(self):
        with self.assertRaises(SystemExit) as raised:
            with contextlib.redirect_stdout(io.StringIO()) as help_text:
                self.run_from_argv('--help')

        self.assertEqual(raised.exception.code, 0)
        self.assertIn('--no-public', help_text.getvalue())
