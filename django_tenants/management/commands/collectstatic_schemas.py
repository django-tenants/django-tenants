# -*- coding: utf-8 -*-
import sys
from . import SingleOrAllTenantWrappedCommand
from django.contrib.staticfiles.management.commands import collectstatic
from django.core.management import color
from django.core.management.base import OutputWrapper


class Command(SingleOrAllTenantWrappedCommand):
    COMMAND = collectstatic.Command

    def on_execute_command(self, tenant, args, options):
        style = color.color_style()
        stdout = OutputWrapper(sys.stdout)
        stdout.write(style.MIGRATE_HEADING("=".ljust(70, "=")))
        stdout.write(style.MIGRATE_HEADING("=== Starting collectstatic: {0} ".format(tenant.schema_name).ljust(70, "=")))
        stdout.write(style.MIGRATE_HEADING("=".ljust(70, "=")))
        options["interactive"] = False
        super(Command, self).on_execute_command(tenant, args, options)
