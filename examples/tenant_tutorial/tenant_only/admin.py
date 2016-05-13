from django.contrib import admin

from tenant_only.models import TableOne, TableTwo


@admin.register(TableOne)
class TableOneAdmin(admin.ModelAdmin):
    pass


@admin.register(TableTwo)
class TableTwoAdmin(admin.ModelAdmin):
    pass
