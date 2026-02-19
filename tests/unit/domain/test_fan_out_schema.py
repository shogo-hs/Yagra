"""Tests for FanOutSpec / EdgeSpec.fan_out / StateFieldSpec.reducer support."""

from __future__ import annotations

from typing import Any

import pytest

from yagra.domain.entities import EdgeSpec, FanOutSpec, GraphSpec
from yagra.domain.entities.graph_schema import REDUCER_TYPES, StateFieldSpec


def _base_payload() -> dict[str, Any]:
    return {
        "version": "1.0",
        "start_at": "node_a",
        "end_at": ["node_b"],
        "nodes": [
            {"id": "node_a", "handler": "my_handler"},
            {"id": "node_b", "handler": "my_handler"},
        ],
        "edges": [],
        "params": {},
    }


# ---------------------------------------------------------------------------
# StateFieldSpec.reducer tests
# ---------------------------------------------------------------------------


def test_state_field_spec_reducer_default_is_none() -> None:
    spec = StateFieldSpec(type="list")
    assert spec.reducer is None


def test_state_field_spec_reducer_add_accepted_with_list() -> None:
    spec = StateFieldSpec(type="list", reducer="add")
    assert spec.reducer == "add"
    assert spec.type == "list"


def test_state_field_spec_reducer_add_accepted_with_messages() -> None:
    # add reducer is also valid on messages type
    spec = StateFieldSpec(type="messages", reducer="add")
    assert spec.reducer == "add"


def test_state_field_spec_reducer_add_rejected_with_non_list_type() -> None:
    with pytest.raises(
        ValueError, match="reducer 'add' is only valid with type 'list' or 'messages'"
    ):
        StateFieldSpec(type="str", reducer="add")


def test_state_field_spec_reducer_invalid_value_rejected() -> None:
    with pytest.raises(ValueError, match="unsupported reducer"):
        StateFieldSpec(type="list", reducer="unknown_reducer")


def test_reducer_types_constant() -> None:
    assert "add" in REDUCER_TYPES


# ---------------------------------------------------------------------------
# FanOutSpec tests
# ---------------------------------------------------------------------------


def test_fan_out_spec_basic() -> None:
    spec = FanOutSpec(items_key="topics", item_key="topic")
    assert spec.items_key == "topics"
    assert spec.item_key == "topic"


def test_fan_out_spec_rejects_extra_fields() -> None:
    with pytest.raises(ValueError):
        FanOutSpec(items_key="topics", item_key="topic", extra="oops")  # type: ignore[call-arg,unused-ignore]


# ---------------------------------------------------------------------------
# EdgeSpec.fan_out tests
# ---------------------------------------------------------------------------


def test_edge_spec_fan_out_default_none() -> None:
    edge = EdgeSpec(source="a", target="b")
    assert edge.fan_out is None


def test_edge_spec_fan_out_accepted() -> None:
    edge = EdgeSpec(
        source="a",
        target="b",
        fan_out=FanOutSpec(items_key="topics", item_key="topic"),
    )
    assert edge.fan_out is not None
    assert edge.fan_out.items_key == "topics"
    assert edge.fan_out.item_key == "topic"


def test_edge_spec_fan_out_rejects_combined_with_condition() -> None:
    with pytest.raises(ValueError, match="cannot both be specified"):
        EdgeSpec(
            source="a",
            target="b",
            condition="some_condition",
            fan_out=FanOutSpec(items_key="topics", item_key="topic"),
        )


# ---------------------------------------------------------------------------
# GraphSpec with fan_out edge
# ---------------------------------------------------------------------------


def test_graph_spec_accepts_fan_out_edge() -> None:
    payload = _base_payload()
    payload["edges"] = [
        {
            "source": "node_a",
            "target": "node_b",
            "fan_out": {"items_key": "items", "item_key": "item"},
        },
        {"source": "node_b", "target": "END"},
    ]
    spec = GraphSpec.model_validate(payload)
    assert spec.edges[0].fan_out is not None
    assert spec.edges[0].fan_out.items_key == "items"
    assert spec.edges[0].fan_out.item_key == "item"


def test_graph_spec_accepts_reducer_add_in_state_schema() -> None:
    payload = _base_payload()
    payload["state_schema"] = {
        "topics": {"type": "list"},
        "results": {"type": "list", "reducer": "add"},
    }
    spec = GraphSpec.model_validate(payload)
    assert spec.state_schema["topics"].reducer is None
    assert spec.state_schema["results"].reducer == "add"


def test_graph_spec_json_schema_includes_fan_out() -> None:
    schema = GraphSpec.model_json_schema()
    # EdgeSpec should reference FanOutSpec
    defs = schema.get("$defs", {})
    assert "FanOutSpec" in defs or any("fan_out" in str(v) for v in defs.values())
