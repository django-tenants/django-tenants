import io
import json

from django.core.management import call_command

from django_tenants.test.cases import FastTenantTestCase
from dts_test_app.models import DummyModel


class TenantCommandTestCase(FastTenantTestCase):

    def test_pass_arguments_to_subcommand(self):
        schemas = DummyModel(name="Schemas are")
        schemas.save()
        awesome = DummyModel(name="awesome!")
        awesome.save()

        dump_data = [
            {
                "model": "dts_test_app.dummymodel",
                "pk": schemas.id,
                "fields": {
                    "name": "Schemas are"
                }
            },
            {
                "model": "dts_test_app.dummymodel",
                "pk": awesome.id,
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
