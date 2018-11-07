import os

from django.core.files.storage import FileSystemStorage
from django.conf import settings

from django_tenants import utils


class TenantFileSystemStorage(FileSystemStorage):
    """
    Implementation that extends core Django's FileSystemStorage for multi-tenant setups.
    """

    def __init__(self, location=None, base_url=None, *args, **kwargs):
        try:
            relative_media_root = settings.MULTITENANT_RELATIVE_MEDIA_ROOT
        except AttributeError:
            # MULTITENANT_RELATIVE_MEDIA_ROOT is an optional setting, use the default value if none provided
            relative_media_root = ""

        relative_media_root = utils.parse_tenant_config_path(relative_media_root)

        if location is None:
            location = os.path.join(settings.MEDIA_ROOT, relative_media_root)
        if base_url is None:
            base_url = os.path.join(settings.MEDIA_URL, relative_media_root)
            if not base_url.endswith("/"):
                base_url += "/"

        super(TenantFileSystemStorage, self).__init__(
            location, base_url, *args, **kwargs
        )
