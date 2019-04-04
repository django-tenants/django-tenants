from customers.views import TenantView, TenantViewRandomForm, TenantViewFileUploadCreate
from django.contrib import admin
from django.urls import path

urlpatterns = [
    path('', TenantView.as_view(), name="index"),
    path('sample-random/', TenantViewRandomForm.as_view(), name="random_form"),
    path('upload-file/', TenantViewFileUploadCreate.as_view(), name="upload_file"),
    path('admin/', admin.site.urls),
    ]
