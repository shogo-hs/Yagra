"""Unit tests for edge_rule_validator to improve coverage."""

from __future__ import annotations

from yagra.application.services.edge_rule_validator import (
    collect_edge_rule_issues,
)
from yagra.domain.entities.graph_schema import EdgeSpec, GraphSpec, NodeSpec


def _make_spec(
    nodes: list[dict],
    edges: list[dict],
    start_at: str = "a",
    end_at: list[str] | None = None,
) -> GraphSpec:
    return GraphSpec(
        version="1.0",
        start_at=start_at,
        end_at=end_at or ["a"],
        nodes=[NodeSpec(**n) for n in nodes],
        edges=[EdgeSpec(**e) for e in edges],
    )


# ---------------------------------------------------------------------------
# Lines 49-58: duplicate conditional edge label for the same source
# ---------------------------------------------------------------------------


def test_collect_edge_rule_issues_detects_duplicate_conditional_label() -> None:
    """Lines 49-58: duplicate condition label from the same source raises an issue."""
    spec = _make_spec(
        nodes=[
            {"id": "router", "handler": "llm"},
            {"id": "path_a", "handler": "h"},
            {"id": "path_b", "handler": "h"},
            {"id": "path_c", "handler": "h"},
        ],
        edges=[
            {"source": "router", "target": "path_a", "condition": "yes"},
            {"source": "router", "target": "path_b", "condition": "yes"},  # duplicate
            {"source": "router", "target": "path_c", "condition": "no"},
        ],
        start_at="router",
        end_at=["path_a", "path_b", "path_c"],
    )
    issues = collect_edge_rule_issues(spec)
    duplicate_issues = [i for i in issues if "duplicate conditional edge label" in i.message]
    assert len(duplicate_issues) == 1
    assert duplicate_issues[0].location == ("edges", 1, "condition")


def test_collect_edge_rule_issues_multiple_duplicate_labels() -> None:
    """Lines 49-58: multiple duplicate labels produce multiple issues."""
    spec = _make_spec(
        nodes=[
            {"id": "router", "handler": "llm"},
            {"id": "a", "handler": "h"},
            {"id": "b", "handler": "h"},
            {"id": "c", "handler": "h"},
            {"id": "d", "handler": "h"},
        ],
        edges=[
            {"source": "router", "target": "a", "condition": "x"},
            {"source": "router", "target": "b", "condition": "x"},  # dup of x
            {"source": "router", "target": "c", "condition": "y"},
            {"source": "router", "target": "d", "condition": "y"},  # dup of y
        ],
        start_at="router",
        end_at=["a", "b", "c", "d"],
    )
    issues = collect_edge_rule_issues(spec)
    duplicate_issues = [i for i in issues if "duplicate conditional edge label" in i.message]
    assert len(duplicate_issues) == 2


# ---------------------------------------------------------------------------
# Line 77: fan_out + conditional conflict
# ---------------------------------------------------------------------------


def test_collect_edge_rule_issues_fanout_with_conditional_conflict() -> None:
    """Line 77: fan_out edge combined with conditional edge from same source produces issue."""
    spec = _make_spec(
        nodes=[
            {"id": "src", "handler": "h"},
            {"id": "target_a", "handler": "h"},
            {"id": "target_b", "handler": "h"},
            {"id": "end", "handler": "h"},
        ],
        edges=[
            {
                "source": "src",
                "target": "target_a",
                "fan_out": {"items_key": "items", "item_key": "item"},
            },
            {
                "source": "src",
                "target": "target_b",
                "condition": "done",
            },
        ],
        start_at="src",
        end_at=["target_a", "target_b"],
    )
    issues = collect_edge_rule_issues(spec)
    fanout_conflict = [i for i in issues if "fan_out edge cannot be combined" in i.message]
    assert len(fanout_conflict) >= 2
    locations = {i.location for i in fanout_conflict}
    assert ("edges", 0, "fan_out") in locations
    assert ("edges", 1, "condition") in locations


# ---------------------------------------------------------------------------
# Line 86: node_index is None (conditional label source not in nodes)
# ---------------------------------------------------------------------------


def test_collect_edge_rule_issues_skips_hint_when_source_node_not_found() -> None:
    """Line 86: if conditional edge source is not in nodes, the continue fires (no hint)."""
    from unittest.mock import MagicMock

    # Build a mock GraphSpec where a conditional edge references a node not in spec.nodes
    # This is a structure error but edge_rule_validator handles it gracefully with continue.
    mock_spec = MagicMock()

    # Nodes list does NOT contain "ghost_source"
    node_a = NodeSpec(id="path_a", handler="h")
    node_b = NodeSpec(id="path_b", handler="h")
    mock_spec.nodes = [node_a, node_b]

    # Edges reference "ghost_source" which is not in nodes
    from yagra.domain.entities.graph_schema import EdgeSpec

    edge1 = EdgeSpec(source="ghost_source", target="path_a", condition="yes")
    edge2 = EdgeSpec(source="ghost_source", target="path_b", condition="no")
    mock_spec.edges = [edge1, edge2]

    issues = collect_edge_rule_issues(mock_spec)
    # No info-level hint should be emitted when source node is not found
    info_issues = [i for i in issues if i.severity == "info"]
    assert len(info_issues) == 0


# ---------------------------------------------------------------------------
# Lines 94-95: llm handler branch source hint (with inline prompt)
# ---------------------------------------------------------------------------


def test_collect_edge_rule_issues_emits_hint_for_llm_branch_source_with_inline_prompt() -> None:
    """Lines 94-95: llm handler as branch source with inline prompt emits an info hint."""
    spec = _make_spec(
        nodes=[
            {
                "id": "classifier",
                "handler": "llm",
                "params": {
                    "prompt": {"system": "classify", "user": "input"},
                    "model": "gpt-4o-mini",
                },
            },
            {"id": "path_a", "handler": "h"},
            {"id": "path_b", "handler": "h"},
        ],
        edges=[
            {"source": "classifier", "target": "path_a", "condition": "yes"},
            {"source": "classifier", "target": "path_b", "condition": "no"},
        ],
        start_at="classifier",
        end_at=["path_a", "path_b"],
    )
    issues = collect_edge_rule_issues(spec)
    info_issues = [i for i in issues if i.severity == "info"]
    assert len(info_issues) == 1
    hint = info_issues[0]
    assert "classifier" in hint.message
    assert "llm" in hint.message
    assert "yes" in hint.message or "no" in hint.message
    assert hint.location == ("nodes", 0, "handler")


def test_collect_edge_rule_issues_skips_hint_for_llm_with_prompt_ref() -> None:
    """Line 93: llm with prompt_ref (no inline prompt) does not emit hint."""
    spec = _make_spec(
        nodes=[
            {
                "id": "classifier",
                "handler": "llm",
                "params": {
                    "prompt_ref": "prompts/classify.yaml",
                },
            },
            {"id": "path_a", "handler": "h"},
            {"id": "path_b", "handler": "h"},
        ],
        edges=[
            {"source": "classifier", "target": "path_a", "condition": "yes"},
            {"source": "classifier", "target": "path_b", "condition": "no"},
        ],
        start_at="classifier",
        end_at=["path_a", "path_b"],
    )
    issues = collect_edge_rule_issues(spec)
    info_issues = [i for i in issues if i.severity == "info"]
    assert len(info_issues) == 0


def test_collect_edge_rule_issues_skips_hint_when_no_prompt_key() -> None:
    """Line 92: llm with no 'prompt' key in params does not emit hint."""
    spec = _make_spec(
        nodes=[
            {
                "id": "classifier",
                "handler": "llm",
                "params": {},
            },
            {"id": "path_a", "handler": "h"},
            {"id": "path_b", "handler": "h"},
        ],
        edges=[
            {"source": "classifier", "target": "path_a", "condition": "yes"},
            {"source": "classifier", "target": "path_b", "condition": "no"},
        ],
        start_at="classifier",
        end_at=["path_a", "path_b"],
    )
    issues = collect_edge_rule_issues(spec)
    info_issues = [i for i in issues if i.severity == "info"]
    assert len(info_issues) == 0
