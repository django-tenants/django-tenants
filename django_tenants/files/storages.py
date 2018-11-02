import os
from django.utils._os import safe_join
from django.db import connection
from django.core.files.storage import FileSystemStorage
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from django.utils.encoding import filepath_to_uri
from django.utils.six.moves.urllib.parse import urljoin


__all__ = (
    'TenantStorageMixin',
    'TenantFileSystemStorage',
)


class TenantStorageMixin(object):

    def path(self, name):
        """
        To static_files is the destination path to collectstatic
        To media_files is the destination path to upload files
        """
        if name is None:
            name = ''
        try:
            if '%s' in self.location:
                location = safe_join(self.location % connection.schema_name)
            else:
                location = safe_join(self.location, connection.schema_name)
        except AttributeError:
            location = self.location

        # path = safe_join(location, name)
        return path


class TenantFileSystemStorage(TenantStorageMixin, FileSystemStorage):
    """
    Implementation that extends core Django's FileSystemStorage.
    """

    def __init__(self, location=None, base_url=None, *args, **kwargs):
        super(TenantFileSystemStorage, self).__init__(location, base_url, *args, **kwargs)
        if hasattr(settings, "MULTITENANT_RELATIVE_MEDIA_ROOT") and \
                settings.MULTITENANT_RELATIVE_MEDIA_ROOT:
            self.location = os.path.join(self.location,
                                         settings.MULTITENANT_RELATIVE_MEDIA_ROOT)

            relative_base_url = settings.MULTITENANT_RELATIVE_MEDIA_ROOT
            if not relative_base_url.endswith('/'):
                relative_base_url += '/'
            self.base_url += relative_base_url

    """
    def path(self, name):
        if not hasattr(settings, "MULTITENANT_RELATIVE_MEDIA_ROOT") or \
                not settings.MULTITENANT_RELATIVE_MEDIA_ROOT:
            raise ImproperlyConfigured("You're using the TenantFileSystemStorage "
                                       "without having set the MULTITENANT_RELATIVE_MEDIA_ROOT "
                                       "setting to a relative filesystem path as from MEDIA_ROOT.")

        return super(TenantFileSystemStorage, self).path(name)
    """

    def url(self, name):
        if self.base_url is None:
            raise ValueError("This file is not accessible via a URL.")

        try:
            if '%s' in self.base_url:
                base_url = self.base_url % connection.schema_name
            else:
                base_url = u"{0}{1}/".format(self.base_url, connection.schema_name)
        except AttributeError:
            base_url = self.base_url

        return urljoin(base_url, filepath_to_uri(name))
