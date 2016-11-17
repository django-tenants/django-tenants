import os
from . import TenantWrappedCommand
from compressor.management.commands import compress
from django.conf import settings


class Command(TenantWrappedCommand):
    print "===== TenantWrappedCommand ====="
    COMMAND = compress.Command

    def get_tenant_from_options_or_interactive(self, **options):
        r = super(Command, self).get_tenant_from_options_or_interactive(**options)
        settings.COMPRESS_OUTPUT_DIR = os.path.join(options['schema_name'], "CACHE")
        return r
