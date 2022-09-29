from django.test import TestCase, TransactionTestCase

from .mixins import TenantTestCaseMixin, FastTenantTestCaseMixin


class TenantTestCase(TenantTestCaseMixin, TestCase):
    pass


class FastTenantTestCase(FastTenantTestCaseMixin, TenantTestCase):
    pass


class TransactionTenantTestCase(TenantTestCaseMixin, TransactionTestCase):
    pass


class TransactionFastTenantTestCase(FastTenantTestCaseMixin, TransactionTenantTestCase):
    pass
