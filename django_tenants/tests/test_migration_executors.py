from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from django_tenants.migration_executors.multiproc import MultiprocessingExecutor


def _make_executor():
    executor = MultiprocessingExecutor.__new__(MultiprocessingExecutor)
    executor.args = []
    executor.options = {}
    executor.PUBLIC_SCHEMA_NAME = 'public'
    executor.TENANT_DB_ALIAS = 'default'
    return executor


class MultiprocessingExecutorPoolTest(SimpleTestCase):
    """Tests that Pool is constructed with the correct maxtasksperchild value."""

    def _run_with_pool_mock(self, settings_dict, method='run_migrations'):
        executor = _make_executor()
        tenants = ['tenant1', 'tenant2']

        with patch('django_tenants.migration_executors.multiproc.multiprocessing.Pool') as mock_pool, \
             patch('django_tenants.migration_executors.multiproc.run_migrations'), \
             patch('django.db.connections') as mock_conns, \
             self.settings(**settings_dict):

            mock_conns.__getitem__.return_value = MagicMock()
            pool_instance = MagicMock()
            mock_pool.return_value = pool_instance

            if method == 'run_migrations':
                executor.run_migrations(tenants=list(tenants))
            else:
                executor.run_multi_type_migrations(tenants=[('s1', 'type1'), ('s2', 'type2')])

            return mock_pool.call_args

    def test_default_maxtasksperchild_is_none(self):
        call_args = self._run_with_pool_mock({})
        self.assertIsNone(call_args.kwargs['maxtasksperchild'])

    def test_custom_maxtasksperchild(self):
        call_args = self._run_with_pool_mock({'TENANT_MULTIPROCESSING_MAX_TASKS_PER_CHILD': 5})
        self.assertEqual(call_args.kwargs['maxtasksperchild'], 5)

    def test_default_maxtasksperchild_is_none_multi_type(self):
        call_args = self._run_with_pool_mock({}, method='run_multi_type_migrations')
        self.assertIsNone(call_args.kwargs['maxtasksperchild'])

    def test_custom_maxtasksperchild_multi_type(self):
        call_args = self._run_with_pool_mock(
            {'TENANT_MULTIPROCESSING_MAX_TASKS_PER_CHILD': 3},
            method='run_multi_type_migrations'
        )
        self.assertEqual(call_args.kwargs['maxtasksperchild'], 3)
