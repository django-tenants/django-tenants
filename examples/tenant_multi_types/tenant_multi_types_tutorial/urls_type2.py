from tenant_type_two_only.views import TenantTypeTwoView
from django.urls import path

urlpatterns = [
    path('', TenantTypeTwoView.as_view(), name="index"),
    ]
