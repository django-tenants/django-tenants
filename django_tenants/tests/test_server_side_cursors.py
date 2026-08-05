"""
Tests for ``QuerySet.iterator()`` (server-side cursors) under tenancy.

``DatabaseWrapper._cursor()`` has a dedicated branch for named cursors: a named
cursor can only execute one statement, so ``SET search_path`` has to be issued
on a *separate* cursor before the query runs. That branch had no test coverage,
which matters more than it looks -- a named cursor resolves its table names when
Postgres runs ``DECLARE``, so if the search_path were not established first an
``.iterator()`` would silently read from the wrong schema.

The tests below assert against ``pg_cursors``, Postgres' own view of the cursors
open in the current session. That is deliberate: an isolation test that only
checks the returned rows would still pass if Django quietly stopped using a
server-side cursor, which is exactly the regression worth catching.
"""

from unittest import mock

from django.db import connection
from django.test.utils import override_settings

from dts_test_app.models import DummyModel

from django_tenants.tests.testcases import BaseTestCase
from django_tenants.utils import get_tenant_domain_model, get_tenant_model, tenant_context

DJANGO_CURSOR_PREFIX = '_django_curs_'


class ServerSideCursorTenantTest(BaseTestCase):
    """
    ``.iterator()`` must stay inside the tenant whose schema was active when the
    cursor was declared.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.sync_shared()

    def setUp(self):
        super().setUp()

        self.created = []

        self.tenant1 = get_tenant_model()(schema_name='cursor_tenant_1')
        self.tenant1.save()
        self.domain1 = get_tenant_domain_model()(tenant=self.tenant1, domain='cursor-one.test.com')
        self.domain1.save()

        connection.set_schema_to_public()

        self.tenant2 = get_tenant_model()(schema_name='cursor_tenant_2')
        self.tenant2.save()
        self.domain2 = get_tenant_domain_model()(tenant=self.tenant2, domain='cursor-two.test.com')
        self.domain2.save()

        self.created = [self.domain2, self.domain1, self.tenant2, self.tenant1]

        # Distinguishable rows, and more of them than the chunk_size used below so
        # that the cursor is still open part-way through iteration.
        with tenant_context(self.tenant1):
            for name in ('t1-a', 't1-b', 't1-c'):
                DummyModel(name=name).save()

        with tenant_context(self.tenant2):
            for name in ('t2-a', 't2-b'):
                DummyModel(name=name).save()

    def tearDown(self):
        from django_tenants.models import TenantMixin

        connection.set_schema_to_public()

        for c in self.created:
            if isinstance(c, TenantMixin):
                c.delete(force_drop=True)
            else:
                c.delete()

        super().tearDown()

    @staticmethod
    def open_server_side_cursor_names():
        """
        Names of the server-side cursors Postgres currently holds for this session.
        """
        with connection.cursor() as cursor:
            cursor.execute('SELECT name FROM pg_cursors')
            return [row[0] for row in cursor.fetchall()]

    def django_cursor_is_open(self):
        return any(name.startswith(DJANGO_CURSOR_PREFIX)
                   for name in self.open_server_side_cursor_names())

    def test_iterator_really_uses_a_server_side_cursor(self):
        """
        Guard test. If Django stops opening a server-side cursor here, the
        isolation tests below would pass without ever exercising the named-cursor
        branch of ``_cursor()`` -- so assert the cursor genuinely exists in
        Postgres before trusting anything else in this module.
        """
        connection.set_tenant(self.tenant1)

        iterator = DummyModel.objects.iterator(chunk_size=1)
        try:
            next(iterator)
            self.assertTrue(
                self.django_cursor_is_open(),
                'expected an open server-side cursor in pg_cursors; got %r'
                % (self.open_server_side_cursor_names(),),
            )
        finally:
            iterator.close()

    def test_iterator_is_scoped_to_the_current_tenant(self):
        """
        The whole point: ``SET search_path`` must have run before ``DECLARE``, so
        each tenant's iterator sees only its own rows.
        """
        with tenant_context(self.tenant1):
            self.assertEqual(
                ['t1-a', 't1-b', 't1-c'],
                sorted(obj.name for obj in DummyModel.objects.iterator(chunk_size=1)),
            )

        with tenant_context(self.tenant2):
            self.assertEqual(
                ['t2-a', 't2-b'],
                sorted(obj.name for obj in DummyModel.objects.iterator(chunk_size=1)),
            )

    def test_iterator_keeps_its_schema_across_a_tenant_switch(self):
        """
        A cursor is bound to the schema it was declared against, so switching the
        connection to another tenant part-way through iteration must not retarget
        an already-open iterator.
        """
        connection.set_tenant(self.tenant1)

        iterator = DummyModel.objects.iterator(chunk_size=1)
        try:
            names = [next(iterator).name]

            with tenant_context(self.tenant2):
                # Still tenant1's cursor: tenant2's rows must not appear.
                names.extend(obj.name for obj in iterator)
        finally:
            iterator.close()

        self.assertEqual(['t1-a', 't1-b', 't1-c'], sorted(names))

    @override_settings(TENANT_LIMIT_SET_CALLS=True)
    def test_iterator_is_tenant_scoped_with_limited_set_calls(self):
        """
        ``TENANT_LIMIT_SET_CALLS`` suppresses redundant ``SET search_path`` calls
        by caching ``search_path_set_schemas``. Switching tenant clears that cache
        (``set_tenant``), so iterators must still be correctly scoped.
        """
        with tenant_context(self.tenant1):
            self.assertEqual(
                ['t1-a', 't1-b', 't1-c'],
                sorted(obj.name for obj in DummyModel.objects.iterator(chunk_size=1)),
            )

        with tenant_context(self.tenant2):
            self.assertEqual(
                ['t2-a', 't2-b'],
                sorted(obj.name for obj in DummyModel.objects.iterator(chunk_size=1)),
            )

    def test_iterator_is_tenant_scoped_without_server_side_cursors(self):
        """
        ``DISABLE_SERVER_SIDE_CURSORS`` is required when running behind a pooler in
        transaction pooling mode. It makes ``.iterator()`` fetch client-side, which
        costs memory but must not change which schema the rows come from.
        """
        with mock.patch.dict(connection.settings_dict, {'DISABLE_SERVER_SIDE_CURSORS': True}):
            with tenant_context(self.tenant1):
                iterator = DummyModel.objects.iterator(chunk_size=1)
                next(iterator)
                self.assertFalse(
                    self.django_cursor_is_open(),
                    'no server-side cursor should be opened when they are disabled',
                )
                iterator.close()

                self.assertEqual(
                    ['t1-a', 't1-b', 't1-c'],
                    sorted(obj.name for obj in DummyModel.objects.iterator(chunk_size=1)),
                )

            with tenant_context(self.tenant2):
                self.assertEqual(
                    ['t2-a', 't2-b'],
                    sorted(obj.name for obj in DummyModel.objects.iterator(chunk_size=1)),
                )
