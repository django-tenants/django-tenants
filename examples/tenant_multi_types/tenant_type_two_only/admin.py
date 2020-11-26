from django.contrib import admin

from tenant_type_two_only.models import TableTypeTwoOnly


@admin.register(TableTypeTwoOnly)
class TableTypeTwoOnlyAdmin(admin.ModelAdmin):
    pass
