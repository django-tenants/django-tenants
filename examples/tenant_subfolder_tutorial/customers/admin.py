from django.contrib import admin
from django_tenants.admin import TenantAdminMixin

from customers.models import Client, Domain


class DomainInline(admin.TabularInline):
    model = Domain


@admin.register(Client)
class ClientAdmin(TenantAdminMixin, admin.ModelAdmin):
    inlines = [DomainInline]
    list_display = ('schema_name', 'name')

