from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest

from yagra.application.use_cases.workflow_form_patcher import apply_form_edits


def _base_payload() -> dict[str, Any]:
    return {
        "version": "1.0",
        "start_at": "router",
        "end_at": ["finish"],
        "nodes": [
            {"id": "router", "handler": "router_handler"},
            {
                "id": "planner",
                "handler": "planner_handler",
                "params": {
                    "prompt_ref": "planner",
                    "model": {"provider": "openai", "name": "gpt-4.1-mini"},
                },
            },
            {"id": "finish", "handler": "finish_handler"},
        ],
        "edges": [
            {"source": "router", "target": "planner", "condition": "needs_plan"},
            {"source": "planner", "target": "finish"},
        ],
        "params": {},
    }


def test_apply_form_edits_updates_node_and_edge() -> None:
    workflow = _base_payload()
    patched = apply_form_edits(
        workflow=workflow,
        node_edits=[
            {
                "node_id": "planner",
                "prompt_ref": "planner_v2",
                "model": {"provider": "openai", "name": "gpt-4.1-nano"},
            }
        ],
        edge_edits=[{"edge_index": 1, "condition": "done"}],
    )

    assert patched is not workflow
    planner_params = patched["nodes"][1]["params"]
    assert planner_params["prompt_ref"] == "planner_v2"
    assert planner_params["model"]["name"] == "gpt-4.1-nano"
    assert patched["edges"][1]["condition"] == "done"
    assert workflow["edges"][1].get("condition") is None


def test_apply_form_edits_clears_optional_fields() -> None:
    workflow = deepcopy(_base_payload())
    patched = apply_form_edits(
        workflow=workflow,
        node_edits=[
            {
                "node_id": "planner",
                "prompt_ref": "",
                "model": None,
            }
        ],
        edge_edits=[{"edge_index": 0, "condition": ""}],
    )

    planner_params = patched["nodes"][1]["params"]
    assert "prompt_ref" not in planner_params
    assert "model" not in planner_params
    assert "condition" not in patched["edges"][0]


def test_apply_form_edits_rejects_invalid_targets() -> None:
    workflow = _base_payload()
    with pytest.raises(ValueError, match="node not found"):
        apply_form_edits(
            workflow=workflow,
            node_edits=[{"node_id": "unknown", "prompt_ref": "planner"}],
            edge_edits=[],
        )

    with pytest.raises(ValueError, match="edge index out of range"):
        apply_form_edits(
            workflow=workflow,
            node_edits=[],
            edge_edits=[{"edge_index": 9, "condition": "x"}],
        )


def test_apply_form_edits_supports_create_and_rewire() -> None:
    workflow = _base_payload()

    patched = apply_form_edits(
        workflow=workflow,
        node_creates=[
            {
                "node_id": "review",
                "handler": "review_handler",
                "params": {"prompt_ref": "review.default"},
            }
        ],
        edge_creates=[
            {"source": "review", "target": "finish"},
        ],
        edge_rewires=[{"edge_index": 1, "target": "review"}],
    )

    review_node = next(node for node in patched["nodes"] if node["id"] == "review")
    assert review_node["handler"] == "review_handler"
    assert review_node["params"]["prompt_ref"] == "review.default"

    rewired = patched["edges"][1]
    assert rewired["source"] == "planner"
    assert rewired["target"] == "review"

    created = patched["edges"][-1]
    assert created["source"] == "review"
    assert created["target"] == "finish"
    assert "condition" not in created


def test_apply_form_edits_rejects_duplicate_create_and_invalid_rewire() -> None:
    workflow = _base_payload()

    with pytest.raises(ValueError, match="node already exists"):
        apply_form_edits(
            workflow=workflow,
            node_creates=[{"node_id": "planner", "handler": "planner_handler"}],
        )

    with pytest.raises(ValueError, match="edge source node not found"):
        apply_form_edits(
            workflow=workflow,
            edge_creates=[{"source": "unknown", "target": "finish"}],
        )

    with pytest.raises(ValueError, match="edge rewire requires at least one"):
        apply_form_edits(
            workflow=workflow,
            edge_rewires=[{"edge_index": 0}],
        )
