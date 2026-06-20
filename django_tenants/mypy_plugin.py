"""
Mypy plugin for django-tenants.

django-tenants middleware dynamically adds a ``tenant`` attribute to every
``HttpRequest`` at runtime.  Static type-checkers cannot see this attribute
because it is not declared on ``HttpRequest``.

This plugin hooks into mypy's class analysis and injects the ``tenant``
attribute (typed as ``TenantMixin``) into ``HttpRequest`` so that all
subclasses — including DRF's ``Request`` — inherit it automatically.

Usage — add to ``pyproject.toml``::

    [tool.mypy]
    plugins = [
        "django_tenants.mypy_plugin",
    ]
"""

from __future__ import annotations

from typing import Callable

from mypy.nodes import MemberExpr
from mypy.nodes import NameExpr
from mypy.plugin import ClassDefContext
from mypy.plugin import Plugin
from mypy.plugins.common import add_attribute_to_class
from mypy.types import AnyType
from mypy.types import TypeOfAny
from mypy.types import UnionType

HTTPREQUEST_FULLNAME = "django.http.request.HttpRequest"
TENANT_MIXIN_FULLNAME = "django_tenants.models.TenantMixin"


def _resolve_tenant_type(ctx: ClassDefContext) -> AnyType | UnionType:
    """Try to resolve TenantMixin as the type for ``request.tenant``.

    Falls back to ``Any`` if TenantMixin cannot be looked up yet (e.g.
    during early semantic-analysis passes).
    """
    try:
        tenant_info = ctx.api.named_type(TENANT_MIXIN_FULLNAME, [])
        return tenant_info
    except (AssertionError, KeyError):
        return AnyType(TypeOfAny.implementation_artifact)


def _add_tenant_attribute(ctx: ClassDefContext) -> None:
    """Add ``tenant: TenantMixin`` to a class that inherits HttpRequest."""
    tenant_type = _resolve_tenant_type(ctx)
    add_attribute_to_class(ctx.api, ctx.cls, "tenant", tenant_type)


class DjangoTenantsPlugin(Plugin):
    """Mypy plugin that declares ``request.tenant`` on HttpRequest."""

    def get_base_class_hook(
        self, fullname: str
    ) -> Callable[[ClassDefContext], None] | None:
        if fullname == HTTPREQUEST_FULLNAME:
            return _add_tenant_attribute
        return None


def plugin(version: str) -> type[Plugin]:
    return DjangoTenantsPlugin
