from django.db import models


class TableOne(models.Model):
    name = models.CharField(max_length=100)


class TableTwo(models.Model):
    name = models.CharField(max_length=100)
    table_one = models.ForeignKey(TableOne, on_delete=models.CASCADE)
