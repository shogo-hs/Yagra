from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest

from graphyml.domain.services.schema_validator import (
    GraphSchemaValidationError,
    validate_graph_spec,
)


def _base_payload() -> dict[str, Any]:
    return {
        "version": "1.0",
        "start_at": "router",
        "end_at": ["finish"],
        "nodes": [
            {"id": "router", "handler": "route_handler"},
            {"id": "planner", "handler": "plan_handler"},
            {"id": "tool", "handler": "tool_handler"},
            {"id": "finish", "handler": "finish_handler"},
        ],
        "edges": [
            {"source": "router", "target": "planner", "condition": "needs_plan"},
            {"source": "router", "target": "finish", "condition": "is_done"},
            {"source": "planner", "target": "tool"},
            {"source": "tool", "target": "router"},
        ],
        "params": {"temperature": 0.1},
    }


def test_validate_graph_spec_accepts_branch_and_loop() -> None:
    payload = _base_payload()

    spec = validate_graph_spec(payload)

    assert spec.start_at == "router"
    assert spec.end_at == ["finish"]
    assert any(edge.condition == "needs_plan" for edge in spec.edges)
    assert any(edge.source == "tool" and edge.target == "router" for edge in spec.edges)


def test_validate_graph_spec_rejects_duplicated_node_ids() -> None:
    payload = deepcopy(_base_payload())
    payload["nodes"].append({"id": "planner", "handler": "duplicate_handler"})

    with pytest.raises(GraphSchemaValidationError, match="ノードIDが重複"):
        validate_graph_spec(payload)


def test_validate_graph_spec_rejects_unknown_start_at() -> None:
    payload = deepcopy(_base_payload())
    payload["start_at"] = "unknown_start"

    with pytest.raises(GraphSchemaValidationError, match="start_at"):
        validate_graph_spec(payload)


def test_validate_graph_spec_rejects_unknown_edge_target() -> None:
    payload = deepcopy(_base_payload())
    payload["edges"].append({"source": "router", "target": "ghost"})

    with pytest.raises(GraphSchemaValidationError, match="edge.target"):
        validate_graph_spec(payload)


def test_validate_graph_spec_rejects_empty_edges() -> None:
    payload = deepcopy(_base_payload())
    payload["edges"] = []

    with pytest.raises(GraphSchemaValidationError, match="edges"):
        validate_graph_spec(payload)
