from django.db import models


class TableShared(models.Model):
    name = models.CharField(max_length=100)
