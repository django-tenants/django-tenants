from tenant_type_two_only.views import TenantTypeTwoView
from django.urls import path
from django.contrib import admin

urlpatterns = [
    path('', TenantTypeTwoView.as_view(), name="index"),
    path('admin/', admin.site.urls),
    ]
