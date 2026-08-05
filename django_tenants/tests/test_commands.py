import io
import json
from unittest import mock

from django.core.management import call_command

from django_tenants.test.cases import FastTenantTestCase
from django_tenants.tests.testcases import BaseTestCase
from django_tenants.utils import get_tenant_model, schema_exists
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


class DeleteTenantCommandTestCase(BaseTestCase):
    """
    Confirming the prompt has to actually delete the tenant. #1058
    """

    def create_tenant(self, schema_name='delete_test'):
        tenant = get_tenant_model()(schema_name=schema_name)
        tenant.save()
        self.assertTrue(schema_exists(schema_name))
        return tenant

    def test_answering_yes_at_the_first_prompt_deletes_the_tenant(self):
        tenant = self.create_tenant()

        with mock.patch('builtins.input', return_value='yes'):
            call_command('delete_tenant', schema_name=tenant.schema_name, stderr=io.StringIO())

        self.assertFalse(get_tenant_model().objects.filter(pk=tenant.pk).exists())
        self.assertFalse(schema_exists(tenant.schema_name))

    def test_answering_no_keeps_the_tenant(self):
        tenant = self.create_tenant()
        stderr = io.StringIO()

        with mock.patch('builtins.input', return_value='no'):
            call_command('delete_tenant', schema_name=tenant.schema_name, stderr=stderr)

        self.assertIn('Canceled', stderr.getvalue())
        self.assertTrue(get_tenant_model().objects.filter(pk=tenant.pk).exists())
        self.assertTrue(schema_exists(tenant.schema_name))

    def test_unrecognised_answer_is_reprompted_until_valid(self):
        tenant = self.create_tenant()

        with mock.patch('builtins.input', side_effect=['maybe', '', 'yes']) as mocked_input:
            call_command('delete_tenant', schema_name=tenant.schema_name, stderr=io.StringIO())

        self.assertEqual(mocked_input.call_count, 3)
        self.assertFalse(schema_exists(tenant.schema_name))

    def test_noinput_deletes_without_prompting(self):
        tenant = self.create_tenant()

        with mock.patch('builtins.input', side_effect=AssertionError('should not prompt')):
            call_command('delete_tenant', schema_name=tenant.schema_name, interactive=False,
                         stderr=io.StringIO())

        self.assertFalse(schema_exists(tenant.schema_name))
