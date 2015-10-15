import functools
import multiprocessing

from django.conf import settings

from .base import MigrationExecutor, run_migrations


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

            from django.db import connection

            # Let every process make its connection, but don't close the
            # main connection
            c = connection.connection
            connection.connection = None

            run_migrations_p = functools.partial(
                run_migrations,
                self.args,
                self.options,
                self.codename
            )
            p = multiprocessing.Pool(processes=processes)
            p.map(
                run_migrations_p,
                tenants,
                chunks
            )

            # Revert the original connection
            connection.connection = c
