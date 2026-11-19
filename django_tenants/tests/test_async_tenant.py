"""
Tests for async tenant handling with contextvars.

These tests verify that:
1. Async ORM queries resolve the correct tenant schema, not public (#1168)
2. Concurrent async tasks with different tenants don't leak tenant state
3. TENANT_LIMIT_SET_CALLS refreshes a stale search path cache (#1052)
"""
import asyncio

from django.db import connection, connections
from django.test.utils import override_settings

from dts_test_app.models import DummyModel

from django_tenants.test.cases import TenantTestCase
from django_tenants.utils import get_public_schema_name, tenant_context


def _current_search_path(cursor):
    cursor.execute("SELECT current_setting('search_path')")
    value = cursor.fetchone()[0]
    return value.split(",")[0].strip().strip("'\"")


class AsyncTenantResolutionTest(TenantTestCase):
    """
    The tenant state lives in ContextVars so that async stacks -- which spread
    database work across threads (django-bolt, or plain Django ASGI where
    sync_to_async runs ORM work on another thread) -- resolve the tenant that
    was selected for the request, rather than falling back to whatever the
    thread-local attributes of that thread's connection happen to hold.
    """

    def test_async_orm_resolves_tenant_schema_not_public(self):
        """
        await DummyModel.objects.aget(...) inside a tenant context must resolve
        the tenant's schema, not public. DummyModel only exists in tenant
        schemas, so a public-only search_path would make the query fail.

        The ORM calls run on asgiref's executor thread, which has its own DB
        connection that cannot see rows created inside the TestCase's
        uncommitted transaction on the main thread's connection. The row is
        therefore created and removed on the executor thread's connection
        (autocommitted), so the aget actually finds it.
        """
        # Clean up any residue from a previous crashed run (committed data is
        # visible here).
        DummyModel.objects.filter(name="async-tenant-row").delete()

        async def query():
            await DummyModel.objects.acreate(name="async-tenant-row")
            try:
                return await DummyModel.objects.aget(name="async-tenant-row")
            finally:
                await DummyModel.objects.filter(name="async-tenant-row").adelete()

        with tenant_context(self.tenant):
            obj = asyncio.run(query())

        self.assertEqual(obj.name, "async-tenant-row")

    def test_db_work_on_executor_thread_resolves_tenant_schema(self):
        """
        ``sync_to_async(thread_sensitive=False)`` runs DB work on a threadpool
        thread with its own thread-local ``DatabaseWrapper``. The ContextVar
        state must reach that thread, and the ``SET search_path`` must be
        issued on that thread's own session -- otherwise the query would run
        against public, which is exactly the failure the middleware approach
        could not fix.
        """
        from asgiref.sync import sync_to_async

        async def probe():
            @sync_to_async
            def _on_executor_thread():
                # This runs on a threadpool thread: the thread-local wrapper
                # for THIS thread is resolved from the ContextVars.
                schema = connection.schema_name
                cursor = connection.cursor()
                search_path = _current_search_path(cursor)
                cursor.close()
                # Don't linger on the executor thread's session.
                connection.close()
                return schema, search_path

            return await _on_executor_thread()

        with tenant_context(self.tenant):
            schema, search_path = asyncio.run(probe())

        # The threadpool thread's own connection was scoped to the tenant...
        self.assertEqual(schema, self.tenant.schema_name)
        # ...and its SET search_path was issued there too.
        self.assertEqual(search_path, self.tenant.schema_name)

    def _assert_task_state_isolation(self):
        """
        A task that changes the tenant must see its own change, and the change
        must not leak into the surrounding context.
        """
        async def set_public_inside_task():
            connection.set_schema_to_public()
            # Give the event loop a chance to interleave with other tasks.
            await asyncio.sleep(0)
            return connection.schema_name

        async def main():
            before = connection.schema_name
            inside = await asyncio.create_task(set_public_inside_task())
            after = connection.schema_name
            return before, inside, after

        connection.set_tenant(self.tenant)
        before, inside, after = asyncio.run(main())

        # The task saw its own change...
        self.assertEqual(inside, get_public_schema_name())
        # ...and the change did not leak into the surrounding context.
        self.assertEqual(after, before)

    def test_concurrent_tasks_do_not_leak_tenant_state(self):
        """
        Two concurrent tasks set to different tenants must not see each
        other's schema. Each task copies the current context, so tenant
        changes made inside a task must stay inside it.
        """
        self._assert_task_state_isolation()

    @override_settings(TENANT_LIMIT_SET_CALLS=True)
    def test_concurrent_tasks_do_not_leak_tenant_state_with_limit_set_calls(self):
        """
        Same isolation guarantee with TENANT_LIMIT_SET_CALLS enabled, which is
        the setup this PR targets.
        """
        self._assert_task_state_isolation()


class LimitSetCallsTest(TenantTestCase):
    """
    With TENANT_LIMIT_SET_CALLS, skipping `SET search_path` must compare the
    cached paths against the ones the current tenant state produces, not just
    check that the cache is filled in (#1052). A connection whose cache still
    holds the previous tenant's paths must re-issue the SET.
    """

    @override_settings(TENANT_LIMIT_SET_CALLS=True)
    def test_stale_cache_is_refreshed_when_tenant_changes(self):
        self.addCleanup(connection.set_tenant, self.tenant)

        # Cache the search path for the tenant schema.
        connection.set_tenant(self.tenant)
        cursor = connection.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        self.assertEqual(connection.search_path_set_schemas,
                         connection._get_cursor_search_paths())

        # Move the tenant state without going through set_tenant() (which
        # clears the cache): this is what happens when the ContextVar is set
        # from another thread of the same request while this connection
        # instance still holds a cache from the previous tenant.
        connection.schema_name = get_public_schema_name()

        # The SET search_path must have been re-issued for the new tenant,
        # not skipped because a cache was present.
        cursor = connection.cursor()
        self.assertEqual(_current_search_path(cursor), get_public_schema_name())
        cursor.close()

        # And the cache must match the current tenant state again.
        self.assertEqual(connection.search_path_set_schemas,
                         connection._get_cursor_search_paths())

    @override_settings(TENANT_LIMIT_SET_CALLS=True)
    def test_stale_cache_on_second_wrapper_instance(self):
        """
        The async flow from #1052: a worker thread uses its own DatabaseWrapper
        (Django keeps connections thread-local) which inherits the ContextVar
        state of the request, while its instance cache still holds the search
        paths of the tenant an earlier request had selected.
        """
        self.addCleanup(connection.set_tenant, self.tenant)

        # ContextVars say the tenant's schema...
        connection.set_tenant(self.tenant)
        # ...but this instance's cache pretends a previous request had
        # selected public. Note: connections["default"] is the real
        # DatabaseWrapper -- django.db.connection is a proxy, so
        # connection.__class__ would give the proxy class, not the wrapper.
        stale_wrapper = connections["default"].__class__(
            connections["default"].settings_dict, alias=connections["default"].alias
        )
        self.addCleanup(stale_wrapper.close)
        stale_wrapper.search_path_set_schemas = [get_public_schema_name()]

        cursor = stale_wrapper.cursor()
        self.assertEqual(_current_search_path(cursor), self.tenant.schema_name)
        cursor.close()


class PerAliasStateTest(TenantTestCase):
    """
    The tenant state is kept per database alias, so a second backend alias
    (e.g. a read replica) can select a different tenant without switching the
    default alias, and the other way around.
    """

    def test_set_tenant_is_isolated_per_alias(self):
        # connections["default"] is the real DatabaseWrapper; django.db.connection
        # is a proxy, so connection.__class__ would give the proxy class.
        default_wrapper = connections["default"]
        replica = default_wrapper.__class__(default_wrapper.settings_dict, alias="replica")
        self.addCleanup(replica.close)

        connection.set_tenant(self.tenant)
        # A second alias on this backend keeps its own state.
        self.assertEqual(replica.schema_name, get_public_schema_name())

        # Selecting a tenant on the second alias does not switch the default.
        replica.set_tenant(self.tenant)
        replica.schema_name = get_public_schema_name()
        self.assertEqual(connection.schema_name, self.tenant.schema_name)
