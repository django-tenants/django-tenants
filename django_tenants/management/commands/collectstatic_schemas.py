# -*- coding: utf-8 -*-
from . import TenantWrappedCommand
from django.contrib.staticfiles.management.commands import collectstatic


class Command(TenantWrappedCommand):
    COMMAND = collectstatic.Command
