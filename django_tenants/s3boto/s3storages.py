# -*- coding: utf-8 -*-
import os
from django.core.exceptions import ImproperlyConfigured, SuspiciousOperation
from storages.backends.s3boto import S3BotoStorage, safe_join
from django.utils import timezone
from django.db import connection
from django.conf import settings


class TenantS3BotoStorageAbstract(S3BotoStorage):

    def __init__(self, acl=None, bucket=None, **kwargs):

        super(TenantS3BotoStorageAbstract, self).__init__(acl=acl, bucket=bucket, **kwargs)

        self.current_schema_name = connection.schema_name
        self.set_location_by_schema()

    def get_path_location_by_schema(self):
        return connection.schema_name

    def set_location_by_schema(self):
        self.location = (self.location or '').lstrip('/')
        if not self.location.endswith('/'):
            self.location += '/'

        try:
            if '%s' in self.location:
                self.location = self.location % self.get_path_location_by_schema()
            else:
                self.location = u"{0}/".format(os.path.join(self.location, self.get_path_location_by_schema()))
        except AttributeError:
            pass

    def _normalize_name(self, name):
        """
        Normalizes the name so that paths like /path/to/ignored/../something.txt
        work. We check to make sure that the path pointed to is not outside
        the directory specified by the LOCATION setting.
        """

        try:
            return safe_join(self.location, name)
        except (SuspiciousOperation, ValueError):
            return ""


class TenantMediaS3BotoStorage(TenantS3BotoStorageAbstract):
    def __init__(self, acl=None, bucket=None, **kwargs):
        try:
            self.location = settings.S3_BOTO_STORAGE_MEDIA_LOCATION
            self.location_original = self.location
            super(TenantMediaS3BotoStorage, self).__init__(acl=acl, bucket=bucket, **kwargs)
        except AttributeError:
            raise ImproperlyConfigured('To use %s.%s you must '
                                       'define the S3_BOTO_STORAGE_MEDIA_LOCATION '
                                       'in your settings' %
                                       (__name__, TenantMediaS3BotoStorage.__name__))

    def _normalize_name(self, name):
        """
        Normalizes the name so that paths like /path/to/ignored/../something.txt
        work. We check to make sure that the path pointed to is not outside
        the directory specified by the LOCATION setting.
        """

        # Verify if configs the schema is changed.
        if self.current_schema_name != connection.schema_name:
            self.current_schema_name = connection.schema_name
            self.location = self.location_original
            self.set_location_by_schema()

        return super(TenantMediaS3BotoStorage, self)._normalize_name(name)


class TenantStaticS3BotoStorage(TenantS3BotoStorageAbstract):
    def __init__(self, acl=None, bucket=None, **kwargs):
        try:
            self.location = settings.S3_BOTO_STORAGE_STATIC_LOCATION
            self.location_original = self.location
            super(TenantStaticS3BotoStorage, self).__init__(acl=acl, bucket=bucket, **kwargs)
        except AttributeError:
            raise ImproperlyConfigured('To use %s.%s you must '
                                       'define the S3_BOTO_STORAGE_STATIC_LOCATION '
                                       'in your settings' %
                                       (__name__, TenantStaticS3BotoStorage.__name__))

    def set_location_by_schema(self):

        super(TenantStaticS3BotoStorage, self).set_location_by_schema()

        # hack to work django compressor
        if hasattr(settings, "COMPRESS_ENABLED") and settings.COMPRESS_ENABLED:
            settings.COMPRESS_URL = 'https://{0}/{1}'.format(settings.AWS_S3_CUSTOM_DOMAIN, self.location)
            print "settings.COMPRESS_URL"
            print settings.COMPRESS_URL
            # settings.COMPRESS_URL_PLACEHOLDER = settings.COMPRESS_URL

    # def path(self, name):
    #     # print self.location
    #     return safe_join(self.location, name)

    def _normalize_name(self, name):
        """
        Normalizes the name so that paths like /path/to/ignored/../something.txt
        work. We check to make sure that the path pointed to is not outside
        the directory specified by the LOCATION setting.
        """

        # Verify if configs the schema is changed.
        # For now we need this override to work with command compress_schemas
        # and collectstatic_schemas when it runs over all schemas
        if self.current_schema_name != connection.schema_name:
            self.current_schema_name = connection.schema_name
            self._entries = {}  # force load again
            self.location = self.location_original
            self.set_location_by_schema()

        return super(TenantStaticS3BotoStorage, self)._normalize_name(name)

    fix_use_def_path_only_pass_in_collectstatic = False

    def path(self, name):
        """
        Need override this def, because collecstatic from Django only return False
        if there is one 'def path' that return one path, being him true or false.
        See code bellow from collectstatic.py by Django 1.10 :

        def delete_file(self, path, prefixed_path, source_storage):
            ...
            ...
            # The full path of the target file
            print "self.local: {0}".format(self.local)
            if self.local:
                full_path = self.storage.path(prefixed_path)
            else:
                full_path = None
            # Skip the file if the source file is younger
            # Avoid sub-second precision (see #14665, #19540)

            if (target_last_modified.replace(microsecond=0) >= source_last_modified.replace(microsecond=0) and
                    full_path and not (self.symlink ^ os.path.islink(full_path))):
                if prefixed_path not in self.unmodified_files:
                    self.unmodified_files.append(prefixed_path)
                self.log("Skipping '%s' (not modified)" % path)
                return False

            CONCLUSION:
            the condition above -> "and full_path" is the problem, then if we return fake path '_'
            the problem is solved.
        """
        # print "- {0}".format(name)
        if name and self.fix_use_def_path_only_pass_in_collectstatic:
            self.fix_use_def_path_only_pass_in_collectstatic = False
            return '_'  # return iron man face, \o/
        return None

    def get_modified_time(self, name):
        self.fix_use_def_path_only_pass_in_collectstatic = True
        d = super(TenantStaticS3BotoStorage, self).modified_time(name)
        if settings.USE_TZ:
            # Need this condition to return aware date. Required in Django collectstatic
            # when settings.USE_TZ is True.
            d = d.replace(tzinfo=timezone.utc)
        return d

    # def save(self, name, content):
    #     name = super(TenantStaticS3BotoStorage, self).save(name, content)
    #     return name

    def get_available_name(self, name, max_length=None):
        if self.exists(name):
            self.delete(name)
        return name
