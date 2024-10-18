from django.conf import settings
from asgiref.sync import sync_to_async
from django.db import connection
from django.core.exceptions import DisallowedHost
from django_tenants.utils import get_tenant_domain_model
from asgiref.sync import sync_to_async
from django.http import HttpResponse
from django.core.exceptions import ImproperlyConfigured
from django.urls import set_urlconf, clear_url_caches
from django_tenants.urlresolvers import get_subfolder_urlconf
from django_tenants.utils import (
    remove_www, get_public_schema_name,
    get_tenant_types,
    has_multi_type_tenants,
    get_tenant_domain_model,
    get_public_schema_urlconf,
    get_subfolder_prefix,
    get_tenant_model,

)
from django.http import Http404, HttpResponseNotFound
from django.core.handlers.asgi import ASGIRequest
from middleware.asgi import CoreMiddleware



class ASGITenantMainMiddleware(CoreMiddleware):
   pass