from __future__ import unicode_literals

from django.apps import AppConfig


class CustomersConfig(AppConfig):
    name = 'customers'
    verbose_name = 'Customers'

    def ready(self):
        import customers.handlers
