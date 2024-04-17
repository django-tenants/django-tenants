import io

from django.core.management import call_command

from django_tenants.test.cases import FastTenantTestCase
from dts_test_app.models import DummyModel


class TenantCommandTestCase(FastTenantTestCase):

    def test_pass_arguments_to_subcommand(self):
        DummyModel(name="Schemas are").save()
        DummyModel(name="awesome!").save()

        indented_dump_data = '\n'.join([
            '[',
            '{',
            '    "model": "dts_test_app.dummymodel",',
            '    "pk": 1,',
            '    "fields": {',
            '        "name": "Schemas are"',
            '    }',
            '},',
            '{',
            '    "model": "dts_test_app.dummymodel",',
            '    "pk": 2,',
            '    "fields": {',
            '        "name": "awesome!"',
            '    }',
            '}',
            ']',
            '',
        ])

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
