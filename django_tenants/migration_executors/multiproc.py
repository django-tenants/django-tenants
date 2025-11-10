import functools
import multiprocessing
import sys

from django.conf import settings

from .base import MigrationExecutor, run_migrations


def is_larger_than_314():
    return sys.version_info.major > 3 or sys.version_info.minor >= 14


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

            if is_larger_than_314() and multiprocessing.get_start_method() == "forkserver":
                # In Python 3.14 and above, the default start method is changed to 'forkserver', which breaks
                # the django migrations, raising django.core.exceptions.AppRegistryNotReady. 'fork' is the previous
                # default, which continues to work on Python 3.14.
                multiprocessing.set_start_method('fork', force=True)

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
