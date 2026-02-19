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


# --- Cases where workflow.nodes / workflow.edges are not lists (line 40, 42) ---


def test_apply_form_edits_rejects_nodes_not_list() -> None:
    workflow = _base_payload()
    workflow["nodes"] = "not a list"
    with pytest.raises(ValueError, match="workflow.nodes must be a list"):
        apply_form_edits(workflow=workflow)


def test_apply_form_edits_rejects_edges_not_list() -> None:
    workflow = _base_payload()
    workflow["edges"] = {"bad": "value"}
    with pytest.raises(ValueError, match="workflow.edges must be a list"):
        apply_form_edits(workflow=workflow)


# --- node create validation (line 68, 70, 80) ---


def test_apply_form_edits_node_create_empty_node_id() -> None:
    with pytest.raises(ValueError, match="node create requires non-empty 'node_id'"):
        apply_form_edits(
            workflow=_base_payload(),
            node_creates=[{"node_id": "   ", "handler": "h"}],
        )


def test_apply_form_edits_node_create_node_id_not_str() -> None:
    with pytest.raises(ValueError, match="node create requires non-empty 'node_id'"):
        apply_form_edits(
            workflow=_base_payload(),
            node_creates=[{"node_id": 123, "handler": "h"}],
        )


def test_apply_form_edits_node_create_empty_handler() -> None:
    with pytest.raises(ValueError, match="node create requires non-empty 'handler'"):
        apply_form_edits(
            workflow=_base_payload(),
            node_creates=[{"node_id": "new_node", "handler": ""}],
        )


def test_apply_form_edits_node_create_handler_not_str() -> None:
    with pytest.raises(ValueError, match="node create requires non-empty 'handler'"):
        apply_form_edits(
            workflow=_base_payload(),
            node_creates=[{"node_id": "new_node", "handler": None}],
        )


def test_apply_form_edits_node_create_params_not_mapping() -> None:
    with pytest.raises(ValueError, match="node params must be a mapping"):
        apply_form_edits(
            workflow=_base_payload(),
            node_creates=[{"node_id": "new_node", "handler": "h", "params": "bad"}],
        )


def test_apply_form_edits_node_create_without_params() -> None:
    patched = apply_form_edits(
        workflow=_base_payload(),
        node_creates=[{"node_id": "new_node", "handler": "h"}],
    )
    new_node = next(n for n in patched["nodes"] if n["id"] == "new_node")
    assert new_node["handler"] == "h"
    assert "params" not in new_node


# --- node edit validation (line 102, 108, 114) ---


def test_apply_form_edits_node_edit_empty_node_id() -> None:
    with pytest.raises(ValueError, match="node edit requires non-empty 'node_id'"):
        apply_form_edits(
            workflow=_base_payload(),
            node_edits=[{"node_id": "", "prompt_ref": "x"}],
        )


def test_apply_form_edits_node_edit_node_id_not_str() -> None:
    with pytest.raises(ValueError, match="node edit requires non-empty 'node_id'"):
        apply_form_edits(
            workflow=_base_payload(),
            node_edits=[{"node_id": 0, "prompt_ref": "x"}],
        )


def test_apply_form_edits_node_edit_node_payload_not_mapping() -> None:
    from collections.abc import Mapping as AbcMapping

    class _NonDictNode(AbcMapping):
        def __init__(self, id_: str) -> None:
            self._id = id_

        def __getitem__(self, key: str) -> object:
            if key == "id":
                return self._id
            raise KeyError(key)

        def __iter__(self):
            yield "id"

        def __len__(self) -> int:
            return 1

    workflow = _base_payload()
    workflow["nodes"][0] = _NonDictNode("router")
    with pytest.raises(ValueError, match="node payload must be a mapping"):
        apply_form_edits(
            workflow=workflow,
            node_edits=[{"node_id": "router", "prompt_ref": "x"}],
        )


def test_apply_form_edits_node_edit_params_not_dict() -> None:
    workflow = _base_payload()
    workflow["nodes"][0]["params"] = "bad_params"
    with pytest.raises(ValueError, match="node params must be a mapping"):
        apply_form_edits(
            workflow=workflow,
            node_edits=[{"node_id": "router", "prompt_ref": "x"}],
        )


def test_apply_form_edits_node_edit_creates_params_when_missing() -> None:
    patched = apply_form_edits(
        workflow=_base_payload(),
        node_edits=[{"node_id": "router", "prompt_ref": "router_prompt"}],
    )
    router_node = next(n for n in patched["nodes"] if n["id"] == "router")
    assert "params" in router_node
    assert router_node["params"]["prompt_ref"] == "router_prompt"


# --- edge edit validation (line 134, 140, 143) ---


def test_apply_form_edits_edge_edit_index_not_int() -> None:
    with pytest.raises(ValueError, match="edge edit requires integer 'edge_index'"):
        apply_form_edits(
            workflow=_base_payload(),
            edge_edits=[{"edge_index": "0", "condition": "x"}],
        )


def test_apply_form_edits_edge_edit_payload_not_mapping() -> None:
    workflow = _base_payload()
    workflow["edges"][0] = "corrupted"
    with pytest.raises(ValueError, match="edge payload must be a mapping"):
        apply_form_edits(
            workflow=workflow,
            edge_edits=[{"edge_index": 0, "condition": "x"}],
        )


def test_apply_form_edits_edge_edit_without_condition_key() -> None:
    workflow = _base_payload()
    patched = apply_form_edits(
        workflow=workflow,
        edge_edits=[{"edge_index": 0}],
    )
    assert patched["edges"][0].get("condition") == "needs_plan"


# --- edge create with/without condition (line 185-190) ---


def test_apply_form_edits_edge_create_with_condition() -> None:
    patched = apply_form_edits(
        workflow=_base_payload(),
        edge_creates=[{"source": "planner", "target": "finish", "condition": "done"}],
    )
    created = patched["edges"][-1]
    assert created["source"] == "planner"
    assert created["target"] == "finish"
    assert created["condition"] == "done"


def test_apply_form_edits_edge_create_with_empty_condition() -> None:
    patched = apply_form_edits(
        workflow=_base_payload(),
        edge_creates=[{"source": "planner", "target": "finish", "condition": ""}],
    )
    created = patched["edges"][-1]
    assert "condition" not in created


def test_apply_form_edits_edge_create_with_null_condition() -> None:
    patched = apply_form_edits(
        workflow=_base_payload(),
        edge_creates=[{"source": "planner", "target": "finish", "condition": None}],
    )
    created = patched["edges"][-1]
    assert "condition" not in created


# --- edge rewire validation (line 214, 216, 220) ---


def test_apply_form_edits_edge_rewire_index_not_int() -> None:
    with pytest.raises(ValueError, match="edge rewire requires integer 'edge_index'"):
        apply_form_edits(
            workflow=_base_payload(),
            edge_rewires=[{"edge_index": "0", "target": "finish"}],
        )


def test_apply_form_edits_edge_rewire_index_out_of_range() -> None:
    with pytest.raises(ValueError, match="edge index out of range"):
        apply_form_edits(
            workflow=_base_payload(),
            edge_rewires=[{"edge_index": 99, "target": "finish"}],
        )


def test_apply_form_edits_edge_rewire_payload_not_mapping() -> None:
    workflow = _base_payload()
    workflow["edges"][0] = "corrupted"
    with pytest.raises(ValueError, match="edge payload must be a mapping"):
        apply_form_edits(
            workflow=workflow,
            edge_rewires=[{"edge_index": 0, "target": "finish"}],
        )


# --- edge rewire condition update (line 237-244) ---


def test_apply_form_edits_edge_rewire_sets_condition() -> None:
    patched = apply_form_edits(
        workflow=_base_payload(),
        edge_rewires=[{"edge_index": 1, "condition": "finished"}],
    )
    assert patched["edges"][1]["condition"] == "finished"


def test_apply_form_edits_edge_rewire_clears_condition_with_none() -> None:
    patched = apply_form_edits(
        workflow=_base_payload(),
        edge_rewires=[{"edge_index": 0, "condition": None}],
    )
    assert "condition" not in patched["edges"][0]


def test_apply_form_edits_edge_rewire_clears_condition_with_empty_str() -> None:
    patched = apply_form_edits(
        workflow=_base_payload(),
        edge_rewires=[{"edge_index": 0, "condition": ""}],
    )
    assert "condition" not in patched["edges"][0]


# --- Each branch of _apply_optional_string_field (line 263, 266-267, 269) ---


def test_apply_form_edits_optional_string_field_not_in_edit() -> None:
    workflow = _base_payload()
    patched = apply_form_edits(
        workflow=workflow,
        node_edits=[{"node_id": "planner"}],
    )
    assert patched["nodes"][1]["params"]["prompt_ref"] == "planner"


def test_apply_form_edits_optional_string_field_none_removes_key() -> None:
    patched = apply_form_edits(
        workflow=_base_payload(),
        node_edits=[{"node_id": "planner", "prompt_ref": None}],
    )
    assert "prompt_ref" not in patched["nodes"][1]["params"]


def test_apply_form_edits_optional_string_field_not_str_raises() -> None:
    with pytest.raises(ValueError, match="prompt_ref must be a string or null"):
        apply_form_edits(
            workflow=_base_payload(),
            node_edits=[{"node_id": "planner", "prompt_ref": 123}],
        )


def test_apply_form_edits_optional_string_field_empty_removes_key() -> None:
    patched = apply_form_edits(
        workflow=_base_payload(),
        node_edits=[{"node_id": "planner", "prompt_ref": "   "}],
    )
    assert "prompt_ref" not in patched["nodes"][1]["params"]


# --- Each branch of _apply_optional_mapping_field (line 293, 299) ---


def test_apply_form_edits_optional_mapping_field_not_in_edit() -> None:
    patched = apply_form_edits(
        workflow=_base_payload(),
        node_edits=[{"node_id": "planner"}],
    )
    assert patched["nodes"][1]["params"]["model"]["name"] == "gpt-4.1-mini"


def test_apply_form_edits_optional_mapping_field_none_removes_key() -> None:
    patched = apply_form_edits(
        workflow=_base_payload(),
        node_edits=[{"node_id": "planner", "model": None}],
    )
    assert "model" not in patched["nodes"][1]["params"]


def test_apply_form_edits_optional_mapping_field_not_mapping_raises() -> None:
    with pytest.raises(ValueError, match="model must be a mapping or null"):
        apply_form_edits(
            workflow=_base_payload(),
            node_edits=[{"node_id": "planner", "model": "bad_value"}],
        )


# --- _build_node_index validation (line 318, 322, 324) ---


def test_apply_form_edits_node_index_node_not_mapping() -> None:
    workflow = _base_payload()
    workflow["nodes"].append("not_a_mapping")
    with pytest.raises(ValueError, match="node payload must be a mapping"):
        apply_form_edits(workflow=workflow)


def test_apply_form_edits_node_index_node_id_not_str() -> None:
    workflow = _base_payload()
    workflow["nodes"].append({"id": 999, "handler": "h"})
    with pytest.raises(ValueError, match="node id must be a non-empty string"):
        apply_form_edits(workflow=workflow)


def test_apply_form_edits_node_index_node_id_empty() -> None:
    workflow = _base_payload()
    workflow["nodes"].append({"id": "", "handler": "h"})
    with pytest.raises(ValueError, match="node id must be a non-empty string"):
        apply_form_edits(workflow=workflow)


def test_apply_form_edits_node_index_duplicate_node_id() -> None:
    workflow = _base_payload()
    workflow["nodes"].append({"id": "router", "handler": "h"})
    with pytest.raises(ValueError, match="duplicated node id in workflow"):
        apply_form_edits(workflow=workflow)


# --- _required_node_reference validation (line 348) ---


def test_apply_form_edits_edge_create_source_not_str() -> None:
    with pytest.raises(ValueError, match="edge source must be a non-empty string"):
        apply_form_edits(
            workflow=_base_payload(),
            edge_creates=[{"source": None, "target": "finish"}],
        )


def test_apply_form_edits_edge_create_source_empty_str() -> None:
    with pytest.raises(ValueError, match="edge source must be a non-empty string"):
        apply_form_edits(
            workflow=_base_payload(),
            edge_creates=[{"source": "", "target": "finish"}],
        )


def test_apply_form_edits_edge_create_target_not_str() -> None:
    with pytest.raises(ValueError, match="edge target must be a non-empty string"):
        apply_form_edits(
            workflow=_base_payload(),
            edge_creates=[{"source": "router", "target": 0}],
        )


# --- _normalize_optional_condition validation (line 369, 371) ---


def test_apply_form_edits_condition_not_str_raises() -> None:
    with pytest.raises(ValueError, match="edge condition must be a string or null"):
        apply_form_edits(
            workflow=_base_payload(),
            edge_edits=[{"edge_index": 0, "condition": 123}],
        )


def test_apply_form_edits_condition_not_str_in_rewire_raises() -> None:
    with pytest.raises(ValueError, match="edge condition must be a string or null"):
        apply_form_edits(
            workflow=_base_payload(),
            edge_rewires=[{"edge_index": 0, "condition": ["bad"]}],
        )


# --- _ensure_mapping validation (line 390) ---


def test_apply_form_edits_workflow_not_mapping_raises() -> None:
    with pytest.raises(ValueError, match="workflow must be a mapping"):
        apply_form_edits(workflow="not a mapping")  # type: ignore[arg-type]
