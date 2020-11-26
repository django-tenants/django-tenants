import functools
import multiprocessing

from django.conf import settings

from .base import MigrationExecutor, run_migrations


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
            processes = getattr(
                settings,
                'TENANT_MULTIPROCESSING_MAX_PROCESSES',
                2
            )
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
            p = multiprocessing.Pool(processes=processes)
            p.map(
                run_migrations_p,
                enumerate(tenants),
                chunks
            )

    def run_multi_type_migrations(self, tenants):
        tenants = tenants or []
        processes = getattr(
            settings,
            'TENANT_MULTIPROCESSING_MAX_PROCESSES',
            2
        )
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
        p = multiprocessing.Pool(processes=processes)
        p.map(
            run_migrations_p,
            enumerate(tenants),
            chunks
        )
