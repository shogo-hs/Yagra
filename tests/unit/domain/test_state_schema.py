"""Tests for state_schema / StateFieldSpec support."""

from __future__ import annotations

from typing import Any

import pytest

from yagra.domain.entities import GraphSpec
from yagra.domain.entities.graph_schema import STATE_FIELD_TYPES, StateFieldSpec


def _base_payload() -> dict[str, Any]:
    return {
        "version": "1.0",
        "start_at": "node_a",
        "end_at": ["node_a"],
        "nodes": [{"id": "node_a", "handler": "my_handler"}],
        "edges": [],
        "params": {},
    }


# ---------------------------------------------------------------------------
# StateFieldSpec unit tests
# ---------------------------------------------------------------------------


def test_state_field_spec_accepts_all_supported_types() -> None:
    for type_name in STATE_FIELD_TYPES:
        spec = StateFieldSpec(type=type_name)
        assert spec.type == type_name


def test_state_field_spec_rejects_unsupported_type() -> None:
    with pytest.raises(ValueError, match="unsupported state field type"):
        StateFieldSpec(type="unknown_type")


def test_state_field_spec_rejects_extra_fields() -> None:
    with pytest.raises(ValueError):
        StateFieldSpec(type="str", extra_key="oops")  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# GraphSpec.state_schema integration tests
# ---------------------------------------------------------------------------


def test_graph_spec_state_schema_defaults_to_empty() -> None:
    spec = GraphSpec.model_validate(_base_payload())
    assert spec.state_schema == {}


def test_graph_spec_state_schema_accepts_messages_type() -> None:
    payload = _base_payload()
    payload["state_schema"] = {"messages": {"type": "messages"}}
    spec = GraphSpec.model_validate(payload)
    assert spec.state_schema["messages"].type == "messages"


def test_graph_spec_state_schema_accepts_mixed_types() -> None:
    payload = _base_payload()
    payload["state_schema"] = {
        "messages": {"type": "messages"},
        "result": {"type": "str"},
        "count": {"type": "int"},
        "score": {"type": "float"},
        "active": {"type": "bool"},
        "items": {"type": "list"},
        "metadata": {"type": "dict"},
    }
    spec = GraphSpec.model_validate(payload)
    assert len(spec.state_schema) == 7
    assert spec.state_schema["messages"].type == "messages"
    assert spec.state_schema["result"].type == "str"
    assert spec.state_schema["count"].type == "int"


def test_graph_spec_state_schema_rejects_invalid_type() -> None:
    payload = _base_payload()
    payload["state_schema"] = {"foo": {"type": "invalid_type"}}
    with pytest.raises(Exception, match="unsupported state field type"):
        GraphSpec.model_validate(payload)


def test_graph_spec_json_schema_includes_state_schema() -> None:
    schema = GraphSpec.model_json_schema()
    props = schema.get("properties", {})
    assert "state_schema" in props
    assert "description" in props["state_schema"]
