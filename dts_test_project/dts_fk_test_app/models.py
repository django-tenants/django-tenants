from django.conf.global_settings import AUTH_USER_MODEL
from django.db import models


class ModelWithFkToPublicUser(models.Model):
    user = models.ForeignKey(AUTH_USER_MODEL, on_delete=models.CASCADE)
