"""PS: This models.py file is subject to be deleted - it is just for a demonstration 
purposes about the testcases that we wrote for the ASGI application. """

from django.db import models
from django_tenants.models import TenantMixin, DomainMixin


class Client(TenantMixin):
    name = models.CharField(max_length=100)
    date_created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Company name:{self.name[0:30]}...'

    class Meta:
        ordering = ['-date_created']
    
class Domain(DomainMixin):
    pass

class Subfolder(models.Model):
    name = models.CharField(max_length=100)
    tenant = models.ForeignKey(Client, related_name='subfolders', on_delete=models.CASCADE)

