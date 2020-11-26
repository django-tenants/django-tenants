from django.db import models


class TableTypeTwoOnly(models.Model):
    name = models.CharField(max_length=100)
