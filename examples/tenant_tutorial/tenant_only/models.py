from __future__ import unicode_literals

from django.db import models


class TableOne(models.Model):
     name = models.CharField(max_length=100)


class TableTwo(models.Model):
     name = models.CharField(max_length=100)
     table_one = models.ForeignKey(TableOne)
