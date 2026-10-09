"""Smoke tests for the mypy plugin (django_tenants/mypy_plugin.py).

The plugin is only ever imported by mypy, never by Django at runtime, so nothing else in the
suite touches it. It leans on ``mypy.plugins.common.add_attribute_to_class``, which is not a
stable public API -- without these, a mypy release that moves it would ship broken and only be
noticed by users. Skipped when mypy is absent so the suite still runs without the dev extras.
"""

from unittest import skipUnless

from django.test import SimpleTestCase

try:
    import mypy  # noqa: F401

    HAS_MYPY = True
except ImportError:
    HAS_MYPY = False


@skipUnless(HAS_MYPY, 'mypy is not installed')
class MypyPluginTestCase(SimpleTestCase):
    def test_plugin_entrypoint_returns_the_plugin_class(self):
        from django_tenants.mypy_plugin import DjangoTenantsPlugin, plugin

        self.assertIs(plugin('1.0'), DjangoTenantsPlugin)

    def test_hook_is_registered_for_httprequest_only(self):
        from django_tenants.mypy_plugin import (
            HTTPREQUEST_FULLNAME,
            DjangoTenantsPlugin,
            _add_tenant_attribute,
        )

        instance = DjangoTenantsPlugin.__new__(DjangoTenantsPlugin)
        self.assertIs(
            instance.get_base_class_hook(HTTPREQUEST_FULLNAME), _add_tenant_attribute
        )
        self.assertIsNone(instance.get_base_class_hook('django.db.models.Model'))

    def test_the_mypy_apis_the_plugin_depends_on_still_exist(self):
        # The actual breakage risk: these are internal mypy APIs.
        from mypy.plugin import ClassDefContext, Plugin  # noqa: F401
        from mypy.plugins.common import add_attribute_to_class

        self.assertTrue(callable(add_attribute_to_class))
