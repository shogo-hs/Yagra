"""Tests for fan-out/Send API support in build_state_schema_type and build_state_graph."""

from __future__ import annotations

import operator
from typing import get_args, get_type_hints

import pytest

from yagra.application.use_cases.state_graph_builder import (
    GraphBuildError,
    build_state_schema_type,
)
from yagra.domain.entities.graph_schema import StateFieldSpec


def _field(type_name: str, reducer: str | None = None) -> StateFieldSpec:
    return StateFieldSpec(type=type_name, reducer=reducer)


# ---------------------------------------------------------------------------
# build_state_schema_type with reducer: add
# ---------------------------------------------------------------------------


def test_build_state_schema_type_reducer_add_produces_annotated_list() -> None:
    schema = {"results": _field("list", reducer="add")}
    result = build_state_schema_type(schema)
    hints = get_type_hints(result, include_extras=True)
    results_hint = hints["results"]

    # Should be Annotated[list, operator.add]
    args = get_args(results_hint)
    assert args[0] is list
    assert args[1] is operator.add


def test_build_state_schema_type_reducer_none_produces_plain_list() -> None:
    schema = {"items": _field("list")}
    result = build_state_schema_type(schema)
    hints = get_type_hints(result, include_extras=True)
    # Without reducer, should be plain list (not Annotated)
    assert hints["items"] is list


def test_build_state_schema_type_mixed_reducer_and_plain() -> None:
    schema = {
        "topics": _field("list"),
        "summaries": _field("list", reducer="add"),
        "title": _field("str"),
    }
    result = build_state_schema_type(schema)
    hints = get_type_hints(result, include_extras=True)

    # Plain list (no reducer)
    assert hints["topics"] is list
    # str
    assert hints["title"] is str
    # Annotated list with add reducer
    summaries_args = get_args(hints["summaries"])
    assert summaries_args[0] is list
    assert summaries_args[1] is operator.add


# ---------------------------------------------------------------------------
# Fan-out edge conflicts and validation
# ---------------------------------------------------------------------------


def test_build_state_graph_fan_out_conflict_with_conditional_edge_raises() -> None:
    from yagra.adapters.outbound import InMemoryNodeRegistry
    from yagra.domain.entities import GraphSpec

    payload = {
        "version": "1.0",
        "start_at": "node_a",
        "end_at": ["node_b"],
        "nodes": [
            {"id": "node_a", "handler": "h"},
            {"id": "node_b", "handler": "h"},
        ],
        "edges": [
            # Both conditional and fan_out from same source is not allowed at schema level
            # But we can test mixing fan_out with unconditional
            {
                "source": "node_a",
                "target": "node_b",
                "fan_out": {"items_key": "items", "item_key": "item"},
            },
            {"source": "node_a", "target": "node_b"},  # also unconditional = conflict
        ],
    }

    from yagra.application.use_cases.state_graph_builder import build_state_graph

    spec = GraphSpec.model_validate(payload)
    registry = InMemoryNodeRegistry({"h": lambda s: s})

    with pytest.raises(GraphBuildError, match="fan_out edge cannot be combined"):
        build_state_graph(spec, registry)


def test_build_state_graph_multiple_fan_out_from_same_source_raises() -> None:
    from yagra.adapters.outbound import InMemoryNodeRegistry
    from yagra.application.use_cases.state_graph_builder import build_state_graph
    from yagra.domain.entities import GraphSpec

    payload = {
        "version": "1.0",
        "start_at": "node_a",
        "end_at": ["node_b"],
        "nodes": [
            {"id": "node_a", "handler": "h"},
            {"id": "node_b", "handler": "h"},
        ],
        "edges": [
            {
                "source": "node_a",
                "target": "node_b",
                "fan_out": {"items_key": "items1", "item_key": "item1"},
            },
            {
                "source": "node_a",
                "target": "node_b",
                "fan_out": {"items_key": "items2", "item_key": "item2"},
            },
        ],
    }

    spec = GraphSpec.model_validate(payload)
    registry = InMemoryNodeRegistry({"h": lambda s: s})

    with pytest.raises(GraphBuildError, match="multiple fan_out edges"):
        build_state_graph(spec, registry)


def test_build_fan_out_dispatcher_raises_on_non_list_state() -> None:
    from yagra.application.use_cases.state_graph_builder import (
        _build_fan_out_dispatcher,
        _FanOutWithTarget,
    )

    fanout = _FanOutWithTarget(target="node_b", items_key="items", item_key="item")
    dispatcher = _build_fan_out_dispatcher(fanout)

    with pytest.raises(GraphBuildError, match="fan_out requires state"):
        dispatcher({"items": "not_a_list"})


def test_build_fan_out_dispatcher_returns_sends() -> None:
    from langgraph.types import Send

    from yagra.application.use_cases.state_graph_builder import (
        _build_fan_out_dispatcher,
        _FanOutWithTarget,
    )

    fanout = _FanOutWithTarget(target="summarize", items_key="topics", item_key="topic")
    dispatcher = _build_fan_out_dispatcher(fanout)

    result = dispatcher({"topics": ["AI", "ML", "DL"]})
    assert len(result) == 3
    assert all(isinstance(s, Send) for s in result)
    assert result[0].node == "summarize"
    assert result[0].arg == {"topic": "AI"}
    assert result[1].arg == {"topic": "ML"}
    assert result[2].arg == {"topic": "DL"}
