from __future__ import annotations

from copy import deepcopy
from typing import Any

from yagra.domain.entities import GraphSpec
from yagra.domain.services.schema_validator import collect_graph_structure_issues


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


def test_collect_graph_structure_issues_accepts_branch_and_loop() -> None:
    payload = _base_payload()
    spec = GraphSpec.model_validate(payload)

    issues = collect_graph_structure_issues(spec)

    assert spec.start_at == "router"
    assert spec.end_at == ["finish"]
    assert any(edge.condition == "needs_plan" for edge in spec.edges)
    assert any(edge.source == "tool" and edge.target == "router" for edge in spec.edges)
    assert issues == []


def test_collect_graph_structure_issues_detects_duplicated_node_ids() -> None:
    payload = deepcopy(_base_payload())
    payload["nodes"].append({"id": "planner", "handler": "duplicate_handler"})
    spec = GraphSpec.model_validate(payload)

    issues = collect_graph_structure_issues(spec)

    assert any(issue.location == ("nodes", 1, "id") for issue in issues)
    assert any(issue.location == ("nodes", 4, "id") for issue in issues)


def test_collect_graph_structure_issues_detects_unknown_start_at() -> None:
    payload = deepcopy(_base_payload())
    payload["start_at"] = "unknown_start"
    spec = GraphSpec.model_validate(payload)

    issues = collect_graph_structure_issues(spec)

    assert any(issue.location == ("start_at",) for issue in issues)


def test_collect_graph_structure_issues_detects_unknown_edge_target() -> None:
    payload = deepcopy(_base_payload())
    payload["edges"].append({"source": "router", "target": "ghost"})
    spec = GraphSpec.model_validate(payload)

    issues = collect_graph_structure_issues(spec)

    assert any(issue.location == ("edges", 4, "target") for issue in issues)


def test_graph_spec_model_validate_accepts_empty_edges() -> None:
    payload = deepcopy(_base_payload())
    payload["edges"] = []

    spec = GraphSpec.model_validate(payload)
    assert spec.edges == []
