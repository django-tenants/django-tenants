from django.conf.urls import patterns, url
from tenant_tutorial.views import HomeView

urlpatterns = patterns('',
                       url(r'^$', HomeView.as_view()),
                       )
