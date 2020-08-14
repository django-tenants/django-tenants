from django.conf.urls import include, url
from django.urls import path
from tenant_subfolder_tutorial.views import HomeView
from django.contrib import admin

urlpatterns = [
    path('', HomeView.as_view()),
    path('admin/', admin.site.urls),
    ]
