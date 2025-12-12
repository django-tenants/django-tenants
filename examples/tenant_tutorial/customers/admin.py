from django.contrib import admin
from django.db import connection

from customers.models import Client, Domain
from django_tenants.admin import TenantAdminMixin


class DomainInline(admin.TabularInline):
    model = Domain


@admin.register(Client)
class ClientAdmin(TenantAdminMixin, admin.ModelAdmin):
    inlines = [DomainInline]
    list_display = ('schema_name', 'name')

