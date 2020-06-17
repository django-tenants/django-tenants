from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.urls import path


urlpatterns = [
    path("public/", lambda request: HttpResponse(), name="public"),
    path("private/", login_required(lambda request: HttpResponse()), name="private"),
]
