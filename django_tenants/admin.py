from django_tenants.utils import get_current_schema_name, get_public_schema_name


class TenantAdminMixin:
    """
    Mixin for the tenant model's ModelAdmin.

    On the public schema it changes nothing. Anywhere else (an admin reached
    through a tenant's own site) it lists only the current tenant, and
    doesn't allow adding tenants or deleting any but the current one. The
    change form's save and delete buttons are also disabled for other
    tenants. The models enforce the same rules, whatever the admin allows.
    """
    change_form_template = 'admin/django_tenants/tenant/change_form.html'

    def _on_public_schema(self):
        current = get_current_schema_name()
        return current is None or current == get_public_schema_name()

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if self._on_public_schema():
            return queryset
        return queryset.filter(schema_name=get_current_schema_name())

    def has_add_permission(self, request, *args, **kwargs):
        return self._on_public_schema() and super().has_add_permission(request, *args, **kwargs)

    def has_delete_permission(self, request, obj=None):
        if not self._on_public_schema() and (obj is None or obj.schema_name != get_current_schema_name()):
            return False
        return super().has_delete_permission(request, obj)
