import os

from django.contrib.staticfiles.utils import check_settings
from django.core.files.storage import FileSystemStorage

from django.conf import settings

from django_tenants import utils


class TenantStaticFilesStorage(FileSystemStorage):
    """
    Implementation that extends core Django's StaticFilesStorage for multi-tenant setups.
    """
    def __init__(self, location=None, base_url=None, *args, **kwargs):

        try:
            relative_static_root = settings.MULTITENANT_RELATIVE_STATIC_ROOT
        except AttributeError:
            # MULTITENANT_RELATIVE_STATIC_ROOT is an optional setting, use the default value if none provided
            relative_static_root = ""

        relative_static_root = utils.parse_tenant_config_path(relative_static_root)

        if location is None:
            location = os.path.join(settings.STATIC_ROOT, relative_static_root)
        if base_url is None:
            base_url = os.path.join(settings.STATIC_URL, relative_static_root)
            if not base_url.endswith("/"):
                base_url += "/"

        check_settings(base_url)

        super().__init__(
            location, base_url, *args, **kwargs
        )

    def listdir(self, path):
        """
        More forgiving wrapper for parent class implementation that does not insist on
        each tenant having its own static files dir.
        """
        try:
            return super().listdir(path)
        except FileNotFoundError:
            # Having static files for each tenant is optional - ignore.
            return [], []
