"""
Tests for PgBouncer transaction pooling support (TENANT_PGBOUNCER_TRANSACTION_POOLING).
"""
from unittest import mock

from django.db import connection, transaction
from django.test import override_settings

from django_tenants.signals import tenant_transaction_began
from django_tenants.tests.testcases import BaseTestCase
from django_tenants.utils import (
    disable_transaction_pooling,
    get_public_schema_name,
    get_tenant_domain_model,
    get_tenant_model,
)
from dts_test_app.models import DummyModel


class PgBouncerTransactionPoolingTest(BaseTestCase):
    """Test PgBouncer transaction pooling behavior."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from django.conf import settings
        settings.SHARED_APPS = ('django_tenants', 'customers')
        settings.TENANT_APPS = (
            'dts_test_app',
            'django.contrib.contenttypes',
            'django.contrib.auth',
        )
        settings.INSTALLED_APPS = settings.SHARED_APPS + settings.TENANT_APPS
        cls.sync_shared()

        cls.public_tenant = get_tenant_model()(schema_name=get_public_schema_name())
        cls.public_tenant.save()
        cls.public_domain = get_tenant_domain_model()(
            tenant=cls.public_tenant, domain='test.com'
        )
        cls.public_domain.save()

    @classmethod
    def tearDownClass(cls):
        cls.public_domain.delete()
        cls.public_tenant.delete()
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        connection.set_schema_to_public()
        self.created = []

    def tearDown(self):
        from django_tenants.models import TenantMixin
        connection.set_schema_to_public()
        for c in self.created:
            if isinstance(c, TenantMixin):
                c.delete(force_drop=True)
            else:
                c.delete()
        super().tearDown()

    def test_pooling_off_default_behavior(self):
        """With pooling off (default), normal session-level search_path behavior."""
        tenant = get_tenant_model()(schema_name='pooltest1')
        tenant.save()
        domain = get_tenant_domain_model()(tenant=tenant, domain='pooltest1.test.com')
        domain.save()
        self.created = [domain, tenant]

        connection.set_tenant(tenant)
        DummyModel(name='one').save()
        self.assertEqual(DummyModel.objects.count(), 1)
        connection.set_schema_to_public()

    @override_settings(TENANT_PGBOUNCER_TRANSACTION_POOLING=True)
    def test_pooling_on_autocommit_queries_succeed(self):
        """With pooling on, autocommit-mode queries run in explicit transactions."""
        tenant = get_tenant_model()(schema_name='pooltest2')
        tenant.save()
        domain = get_tenant_domain_model()(tenant=tenant, domain='pooltest2.test.com')
        domain.save()
        self.created = [domain, tenant]

        connection.set_tenant(tenant)
        DummyModel(name='one').save()
        DummyModel(name='two').save()
        self.assertEqual(DummyModel.objects.count(), 2)
        connection.set_schema_to_public()

    @override_settings(TENANT_PGBOUNCER_TRANSACTION_POOLING=True)
    def test_pooling_on_atomic_single_transaction(self):
        """With pooling on, transaction.atomic() uses one txn, SET LOCAL once."""
        tenant = get_tenant_model()(schema_name='pooltest3')
        tenant.save()
        domain = get_tenant_domain_model()(tenant=tenant, domain='pooltest3.test.com')
        domain.save()
        self.created = [domain, tenant]

        connection.set_tenant(tenant)
        with transaction.atomic():
            DummyModel(name='a').save()
            DummyModel(name='b').save()
            self.assertEqual(DummyModel.objects.count(), 2)
        self.assertEqual(DummyModel.objects.count(), 2)
        connection.set_schema_to_public()

    @override_settings(TENANT_PGBOUNCER_TRANSACTION_POOLING=True)
    def test_pooling_on_opt_out(self):
        """With pooling on, disable_transaction_pooling() skips wrapping."""
        tenant = get_tenant_model()(schema_name='pooltest4')
        tenant.save()
        domain = get_tenant_domain_model()(tenant=tenant, domain='pooltest4.test.com')
        domain.save()
        self.created = [domain, tenant]

        connection.set_tenant(tenant)
        with disable_transaction_pooling():
            DummyModel(name='x').save()
        self.assertEqual(DummyModel.objects.count(), 1)
        connection.set_schema_to_public()

    @override_settings(TENANT_PGBOUNCER_TRANSACTION_POOLING=True)
    def test_pooling_on_search_path_cleared_after_commit(self):
        """With pooling on, _search_path_set_in_txn is cleared after commit."""
        tenant = get_tenant_model()(schema_name='pooltest5')
        tenant.save()
        domain = get_tenant_domain_model()(tenant=tenant, domain='pooltest5.test.com')
        domain.save()
        self.created = [domain, tenant]

        connection.set_tenant(tenant)
        with transaction.atomic():
            DummyModel(name='y').save()
            self.assertTrue(connection._search_path_set_in_txn)
        self.assertFalse(connection._search_path_set_in_txn)
        connection.set_schema_to_public()

    @override_settings(TENANT_PGBOUNCER_TRANSACTION_POOLING=True)
    def test_tenant_transaction_began_signal_sent(self):
        """With pooling on, tenant_transaction_began is sent when SET LOCAL runs."""
        tenant = get_tenant_model()(schema_name='pooltest6')
        tenant.save()
        domain = get_tenant_domain_model()(tenant=tenant, domain='pooltest6.test.com')
        domain.save()
        self.created = [domain, tenant]

        connection.set_tenant(tenant)
        handler = mock.Mock()
        tenant_transaction_began.connect(handler)
        self.addCleanup(tenant_transaction_began.disconnect, handler)

        DummyModel(name='z').save()
        self.assertGreaterEqual(handler.call_count, 1)
        call_kwargs = handler.call_args[1]
        self.assertEqual(call_kwargs.get('schema_name'), 'pooltest6')
        self.assertIs(call_kwargs.get('connection'), connection)
        connection.set_schema_to_public()
