from django.conf.urls import include, url
from tenant_tutorial.views import HomeView
from django.contrib import admin
urlpatterns = [
    url(r'^$', HomeView.as_view()),
    url(
        r'^admin/',
        include(admin.site.urls)),

    ]
