import io
import json
from unittest import mock, expectedFailure

from django.core.management import call_command
from django.test import TestCase, TransactionTestCase

from django_tenants.test.cases import FastTenantTestCase
from django_tenants.utils import get_tenant_model, get_tenant_domain_model
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


class CreateTenantCommandTestCase(TransactionTestCase):
    """Tests for the create_tenant management command.

    Uses TransactionTestCase because these tests intentionally trigger
    IntegrityErrors which break the PostgreSQL transaction state.
    """

    def tearDown(self) -> None:
        """Clean up tenant schemas created during tests.

        Django's test framework cleans up database rows but not PostgreSQL schemas.
        We must manually drop tenant schemas to avoid conflicts in subsequent test runs.
        """
        super().tearDown()
        Tenant = get_tenant_model()
        for schema in ['duplicate_test_schema']:
            try:
                tenant = Tenant.objects.filter(schema_name=schema).first()
                if tenant:
                    tenant.delete(force_drop=True)
            except Exception:
                pass  # Ignore cleanup errors

    def test_create_tenant_with_duplicate_schema_raises_error(self) -> None:
        """
        When creating a tenant with a schema_name that already exists,
        the command should raise CommandError with a descriptive message.
        """
        from django.core.management.base import CommandError

        # First, create a tenant successfully
        call_command(
            "create_tenant",
            "--schema_name=duplicate_test_schema",
            "--name=First",
            "--domain-domain=first.test",
            "--noinput",
        )

        # Try to create a duplicate tenant - should raise CommandError
        with self.assertRaises(CommandError) as cm:
            call_command(
                "create_tenant",
                "--schema_name=duplicate_test_schema",
                "--name=Duplicate",
                "--domain-domain=duplicate.test",
                "--noinput",
            )

        # CommandError message should mention the duplicate/already exists issue
        error_message = str(cm.exception)
        self.assertIn("already exist", error_message.lower())
