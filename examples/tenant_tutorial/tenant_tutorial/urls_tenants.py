from django.conf.urls import patterns, url
from customers.views import TenantView

urlpatterns = patterns('',
                       url(r'^$', TenantView.as_view()),
                       )
