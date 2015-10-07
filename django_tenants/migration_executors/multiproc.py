import functools
import multiprocessing

from .base import MigrationExecutor, run_migrations


class MultiprocessingExecutor(MigrationExecutor):
    codename = 'multiprocessing'

    def run_migrations(self, tenants=None):
        tenants = tenants or []

        if self.PUBLIC_SCHEMA_NAME in tenants:
            run_migrations(self.args, self.options, self.PUBLIC_SCHEMA_NAME)
            tenants.pop(tenants.index(self.PUBLIC_SCHEMA_NAME))

        if tenants:
            run_migrations_p = functools.partial(
                run_migrations,
                self.args,
                self.options
            )
            p = multiprocessing.Pool()
            p.map(
                run_migrations_p,
                tenants
            )
