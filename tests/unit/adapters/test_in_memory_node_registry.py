from __future__ import annotations

from typing import Any

import pytest

from yagra.adapters.outbound import InMemoryNodeRegistry
from yagra.ports.outbound import (
    NodeHandlerAlreadyRegisteredError,
    NodeHandlerNotFoundError,
)


def _route_handler(state: dict[str, Any]) -> dict[str, Any]:
    return {"step": "route", **state}


def _tool_handler(state: dict[str, Any]) -> dict[str, Any]:
    return {"step": "tool", **state}


def test_register_and_resolve_returns_registered_handler() -> None:
    registry = InMemoryNodeRegistry()

    registry.register("route_handler", _route_handler)
    resolved = registry.resolve("route_handler")

    assert resolved is _route_handler


def test_register_raises_when_same_name_is_registered_twice() -> None:
    registry = InMemoryNodeRegistry({"route_handler": _route_handler})

    with pytest.raises(NodeHandlerAlreadyRegisteredError, match="route_handler"):
        registry.register("route_handler", _tool_handler)


def test_resolve_raises_when_handler_is_not_registered() -> None:
    registry = InMemoryNodeRegistry()

    with pytest.raises(NodeHandlerNotFoundError, match="missing_handler"):
        registry.resolve("missing_handler")


def test_constructor_registers_initial_handlers() -> None:
    registry = InMemoryNodeRegistry({"tool_handler": _tool_handler})

    resolved = registry.resolve("tool_handler")

    assert resolved is _tool_handler


def test_resolve_for_node_delegates_to_resolve_by_default() -> None:
    registry = InMemoryNodeRegistry({"tool_handler": _tool_handler})

    resolved = registry.resolve_for_node("tool_handler", "node_a")

    assert resolved is _tool_handler
