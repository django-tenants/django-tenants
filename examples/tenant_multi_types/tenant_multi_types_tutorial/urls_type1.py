from tenant_type_one_only.views import TenantView, TenantViewRandomForm, TenantViewFileUploadCreate
from django.contrib import admin
from django.urls import path
from django.views.generic import TemplateView

urlpatterns = [
    path('', TenantView.as_view(), name="index"),
    path('sample-random/', TenantViewRandomForm.as_view(), name="random_form"),
    path('upload-file/', TenantViewFileUploadCreate.as_view(), name="upload_file"),
    path('test/', TemplateView.as_view(template_name='test.html'), name="test"),
    path('admin/', admin.site.urls),
    ]
