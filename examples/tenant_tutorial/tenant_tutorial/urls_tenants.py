from customers.views import TenantView
from django.conf.urls import include, url
from django.contrib import admin

urlpatterns = [
        url(r'^$', TenantView.as_view()),

    url(
        r'^admin/',
        include(admin.site.urls)),


    ]
