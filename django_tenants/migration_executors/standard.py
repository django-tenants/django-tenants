from .base import MigrationExecutor, run_migrations


class StandardExecutor(MigrationExecutor):
    codename = 'standard'

    def run_migrations(self, tenants=None):
        tenants = tenants or []

        if self.PUBLIC_SCHEMA_NAME in tenants:
            run_migrations(self.args, self.options, self.PUBLIC_SCHEMA_NAME)
            tenants.pop(tenants.index(self.PUBLIC_SCHEMA_NAME))

        for schema_name in tenants:
            run_migrations(self.args, self.options, schema_name)
