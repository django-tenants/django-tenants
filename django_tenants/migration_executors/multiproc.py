import functools
import multiprocessing

from django.conf import settings

from .base import MigrationExecutor, run_migrations


def get_pool():
    """Return a multiprocessing pool using the ``fork`` start method when available.

    The migration workers rely on inheriting the parent process's already
    populated Django app registry and settings, which only happens with the
    ``fork`` start method. Python no longer guarantees ``fork`` as the implicit
    default (it is deprecated when the parent is multi-threaded), so request it
    explicitly on platforms that support it (e.g. Linux) and fall back to the
    default context elsewhere (e.g. Windows, which has no ``fork``).
    """
    processes = getattr(settings, 'TENANT_MULTIPROCESSING_MAX_PROCESSES', 2)
    if 'fork' in multiprocessing.get_all_start_methods():
        context = multiprocessing.get_context('fork')
    else:
        context = multiprocessing.get_context()
    return context.Pool(processes=processes)


def run_migrations_percent(args, options, codename, count, idx_schema_name):
    idx, schema_name = idx_schema_name
    return run_migrations(
        args,
        options,
        codename,
        schema_name,
        allow_atomic=False,
        idx=idx,
        count=count
    )


def run_multi_type_migrations_percent(args, options, codename, count, idx_schema_name):
    idx, tenant = idx_schema_name
    return run_migrations(
        args,
        options,
        codename,
        schema_name=tenant[0],
        tenant_type=tenant[1],
        allow_atomic=False,
        idx=idx,
        count=count
    )


class MultiprocessingExecutor(MigrationExecutor):
    codename = 'multiprocessing'

    def run_migrations(self, tenants=None):
        tenants = tenants or []

        if self.PUBLIC_SCHEMA_NAME in tenants:
            run_migrations(self.args, self.options, self.codename, self.PUBLIC_SCHEMA_NAME)
            tenants.pop(tenants.index(self.PUBLIC_SCHEMA_NAME))

        if tenants:
            chunks = getattr(
                settings,
                'TENANT_MULTIPROCESSING_CHUNKS',
                2
            )

            from django.db import connections

            connection = connections[self.TENANT_DB_ALIAS]
            connection.close()
            connection.connection = None

            run_migrations_p = functools.partial(
                run_migrations_percent,
                self.args,
                self.options,
                self.codename,
                len(tenants)
            )
            p = get_pool()
            p.map(
                run_migrations_p,
                enumerate(tenants),
                chunks
            )

    def run_multi_type_migrations(self, tenants):
        tenants = tenants or []
        chunks = getattr(
            settings,
            'TENANT_MULTIPROCESSING_CHUNKS',
            2
        )

        from django.db import connections

        connection = connections[self.TENANT_DB_ALIAS]
        connection.close()
        connection.connection = None

        run_migrations_p = functools.partial(
            run_multi_type_migrations_percent,
            self.args,
            self.options,
            self.codename,
            len(tenants)
        )
        p = get_pool()
        p.map(
            run_migrations_p,
            enumerate(tenants),
            chunks
        )
