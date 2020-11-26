from django.db import models


class TypeTwoOnly(models.Model):
    """
    Just a test model so we can test manipulating data inside a tenant
    """
    name = models.CharField(max_length=100)

    def __unicode__(self):
        return self.name

