from django.contrib.admin.options import csrf_protect_m


class TenantAdminMixin:
    """
    Mixin for Tenant model:
    It disables save and delete buttons when not in current or public tenant (preventing Exceptions).
    """
    change_form_template = 'admin/django_tenants/tenant/change_form.html'

    @csrf_protect_m
    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        # Remove atomic block from the view, necessary to avoid TransactionManagementError
        return self._changeform_view(request, object_id, form_url, extra_context)

