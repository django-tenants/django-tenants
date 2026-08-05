import io
import json
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection

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
