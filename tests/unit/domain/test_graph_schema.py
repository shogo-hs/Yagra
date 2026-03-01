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


def test_collect_graph_structure_issues_detects_edge_from_end_at_node() -> None:
    payload = deepcopy(_base_payload())
    # Add an edge from finish (end_at node) to another node
    payload["nodes"].append({"id": "after_finish", "handler": "after_handler"})
    payload["edges"].append({"source": "finish", "target": "after_finish"})
    spec = GraphSpec.model_validate(payload)

    issues = collect_graph_structure_issues(spec)

    assert any(issue.location == ("edges", len(spec.edges) - 1, "source") for issue in issues)


def test_collect_graph_structure_issues_accepts_end_at_node_as_edge_target() -> None:
    # Incoming edges to an end_at node are valid
    payload = deepcopy(_base_payload())
    spec = GraphSpec.model_validate(payload)

    issues = collect_graph_structure_issues(spec)

    assert issues == []


def test_graph_spec_model_validate_accepts_empty_edges() -> None:
    payload = deepcopy(_base_payload())
    payload["edges"] = []

    spec = GraphSpec.model_validate(payload)
    assert spec.edges == []


def test_graph_spec_json_schema_has_descriptions() -> None:
    schema = GraphSpec.model_json_schema()
    # Top-level properties should have description fields
    props = schema.get("properties", {})
    assert "description" in props.get("version", {})
    assert "description" in props.get("start_at", {})
    assert "description" in props.get("nodes", {})


# ---------------------------------------------------------------------------
# Lines 76-77: end_at references undefined node
# ---------------------------------------------------------------------------


def test_collect_graph_structure_issues_detects_unknown_end_at() -> None:
    """Lines 76-77: end_at references an undefined node, issue is appended."""
    payload = deepcopy(_base_payload())
    payload["end_at"] = ["nonexistent_end"]
    # Override start_at to avoid a second issue
    payload["start_at"] = "router"
    spec = GraphSpec.model_validate(payload)

    issues = collect_graph_structure_issues(spec)

    end_at_issues = [i for i in issues if i.location == ("end_at", 0)]
    assert len(end_at_issues) == 1
    assert "end_at" in end_at_issues[0].message
    assert "nonexistent_end" in end_at_issues[0].message


def test_collect_graph_structure_issues_end_at_with_suggestion() -> None:
    """Lines 76-77: end_at with a close match provides suggestion in context."""
    payload = deepcopy(_base_payload())
    # "finsh" is close to "finish" — should trigger fuzzy suggestion
    payload["end_at"] = ["finsh"]
    spec = GraphSpec.model_validate(payload)

    issues = collect_graph_structure_issues(spec)

    end_at_issues = [i for i in issues if i.location == ("end_at", 0)]
    assert len(end_at_issues) == 1
    issue = end_at_issues[0]
    assert issue.context is not None
    assert issue.context["suggestion"] == "finish"


def test_collect_graph_structure_issues_end_at_no_suggestion_when_no_match() -> None:
    """Lines 76-77: end_at with no close match results in suggestion=None."""
    payload = deepcopy(_base_payload())
    payload["end_at"] = ["zzzzz_no_match"]
    spec = GraphSpec.model_validate(payload)

    issues = collect_graph_structure_issues(spec)

    end_at_issues = [i for i in issues if i.location == ("end_at", 0)]
    assert len(end_at_issues) == 1
    issue = end_at_issues[0]
    assert issue.context is not None
    assert issue.context["suggestion"] is None


# ---------------------------------------------------------------------------
# Lines 135-136: edge.source references undefined node
# ---------------------------------------------------------------------------


def test_collect_graph_structure_issues_detects_unknown_edge_source() -> None:
    """Lines 135-136: edge.source references an undefined node, issue is appended."""
    payload = deepcopy(_base_payload())
    payload["edges"].append({"source": "ghost_node", "target": "finish"})
    spec = GraphSpec.model_validate(payload)

    issues = collect_graph_structure_issues(spec)

    source_issues = [
        i
        for i in issues
        if i.location == ("edges", len(spec.edges) - 1, "source") and "edge.source" in i.message
    ]
    assert len(source_issues) == 1
    assert "ghost_node" in source_issues[0].message


# ---------------------------------------------------------------------------
# Fallback validation
# ---------------------------------------------------------------------------


def test_collect_graph_structure_issues_accepts_valid_fallback() -> None:
    payload = deepcopy(_base_payload())
    payload["nodes"][0]["fallback"] = "planner"
    spec = GraphSpec.model_validate(payload)

    issues = collect_graph_structure_issues(spec)
    fallback_issues = [i for i in issues if "fallback" in i.message]
    assert fallback_issues == []


def test_collect_graph_structure_issues_detects_undefined_fallback() -> None:
    payload = deepcopy(_base_payload())
    payload["nodes"][0]["fallback"] = "nonexistent"
    spec = GraphSpec.model_validate(payload)

    issues = collect_graph_structure_issues(spec)
    fallback_issues = [i for i in issues if "fallback" in i.message]
    assert len(fallback_issues) == 1
    assert fallback_issues[0].location == ("nodes", 0, "fallback")
    assert "nonexistent" in fallback_issues[0].message


def test_collect_graph_structure_issues_detects_self_referencing_fallback() -> None:
    payload = deepcopy(_base_payload())
    payload["nodes"][0]["fallback"] = "router"  # self-reference
    spec = GraphSpec.model_validate(payload)

    issues = collect_graph_structure_issues(spec)
    fallback_issues = [i for i in issues if "fallback" in i.message]
    assert len(fallback_issues) == 1
    assert "cannot reference itself" in fallback_issues[0].message


def test_collect_graph_structure_issues_fallback_fuzzy_suggestion() -> None:
    payload = deepcopy(_base_payload())
    payload["nodes"][0]["fallback"] = "planr"  # close to "planner"
    spec = GraphSpec.model_validate(payload)

    issues = collect_graph_structure_issues(spec)
    fallback_issues = [i for i in issues if "fallback" in i.message]
    assert len(fallback_issues) == 1
    assert fallback_issues[0].context is not None
    assert fallback_issues[0].context["suggestion"] == "planner"


# ---------------------------------------------------------------------------
# RetrySpec validation
# ---------------------------------------------------------------------------


def test_retry_spec_accepts_valid_config() -> None:
    from yagra.domain.entities.graph_schema import RetrySpec

    retry = RetrySpec(max_attempts=5, backoff="fixed", base_delay_seconds=1.0)
    assert retry.max_attempts == 5
    assert retry.backoff == "fixed"


def test_retry_spec_rejects_out_of_range_attempts() -> None:
    import pytest
    from pydantic import ValidationError

    from yagra.domain.entities.graph_schema import RetrySpec

    with pytest.raises(ValidationError):
        RetrySpec(max_attempts=0)
    with pytest.raises(ValidationError):
        RetrySpec(max_attempts=11)


def test_retry_spec_rejects_invalid_backoff() -> None:
    import pytest
    from pydantic import ValidationError

    from yagra.domain.entities.graph_schema import RetrySpec

    with pytest.raises(ValidationError):
        RetrySpec(backoff="random")  # type: ignore[arg-type]


def test_node_spec_accepts_retry_and_timeout() -> None:
    from yagra.domain.entities.graph_schema import NodeSpec

    node = NodeSpec.model_validate(
        {
            "id": "test",
            "handler": "llm",
            "retry": {"max_attempts": 5, "backoff": "fixed"},
            "timeout_seconds": 120,
            "fallback": "other_node",
        }
    )
    assert node.retry is not None
    assert node.retry.max_attempts == 5
    assert node.timeout_seconds == 120
    assert node.fallback == "other_node"


def test_node_spec_defaults_retry_to_none() -> None:
    from yagra.domain.entities.graph_schema import NodeSpec

    node = NodeSpec.model_validate({"id": "test", "handler": "llm"})
    assert node.retry is None
    assert node.timeout_seconds is None
    assert node.fallback is None


def test_collect_graph_structure_issues_edge_source_with_suggestion() -> None:
    """Lines 135-136: edge.source with a close match provides suggestion in context."""
    payload = deepcopy(_base_payload())
    # "routr" is close to "router"
    payload["edges"].append({"source": "routr", "target": "finish"})
    spec = GraphSpec.model_validate(payload)

    issues = collect_graph_structure_issues(spec)

    source_issues = [
        i
        for i in issues
        if len(i.location) == 3
        and i.location[0] == "edges"
        and i.location[2] == "source"
        and "edge.source" in i.message
    ]
    assert len(source_issues) >= 1
    issue = source_issues[0]
    assert issue.context is not None
    assert issue.context["suggestion"] == "router"
