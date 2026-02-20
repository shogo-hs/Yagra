from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from yagra.application.use_cases.workflow_edit_session import load_workflow_edit_session
from yagra.application.use_cases.workflow_form_model import (
    WorkflowCatalogIssue,
    WorkflowCatalogPreview,
    WorkflowEdgeFormItem,
    WorkflowFormView,
    WorkflowNodeFormItem,
    _as_optional_mapping,
    _as_optional_string,
    _ensure_mapping,
    _try_load_prompt_ref,
    build_workflow_catalog_preview,
    build_workflow_form_view,
)

FIXTURES_ROOT = Path(__file__).resolve().parents[2] / "fixtures"
WORKFLOW_ROOT = FIXTURES_ROOT / "workflows"


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


def _write_workflow(path: Path, payload: dict[str, Any]) -> Path:
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


def test_build_workflow_form_view_includes_path_based_prompt_ref() -> None:
    workflow_path = WORKFLOW_ROOT / "loop-split.yaml"
    session = load_workflow_edit_session(workflow_path=workflow_path, bundle_root=FIXTURES_ROOT)

    view = build_workflow_form_view(
        workflow=session.workflow,
        ui_state=session.ui_state,
        workflow_path=workflow_path,
        bundle_root=FIXTURES_ROOT,
    )

    assert view.revision == session.revision
    assert len(view.nodes) == 3
    planner = next(item for item in view.nodes if item.id == "planner")
    assert planner.prompt_ref == "prompts/support_prompts.yaml#planner"
    assert view.prompt_catalog_keys == ()

    assert len(view.edges) == 3
    retry_edge = next(item for item in view.edges if item.condition == "retry")
    assert retry_edge.source == "evaluator"
    assert retry_edge.target == "planner"


def test_build_workflow_form_view_handles_prompt_ref_and_model(tmp_path: Path) -> None:
    payload = _base_payload()
    payload["nodes"][1]["params"]["prompt_ref"] = "prompts/support_prompts.yaml#planner"
    workflow_path = _write_workflow(tmp_path / "ref.yaml", payload)
    session = load_workflow_edit_session(workflow_path=workflow_path)

    view = build_workflow_form_view(
        workflow=session.workflow,
        ui_state=session.ui_state,
        workflow_path=workflow_path,
    )

    planner = next(item for item in view.nodes if item.id == "planner")
    assert planner.prompt_ref == "prompts/support_prompts.yaml#planner"
    assert planner.model == {"provider": "openai", "name": "gpt-4.1-mini"}
    assert view.prompt_catalog_keys == ()


def test_build_workflow_form_view_allows_missing_nodes_and_edges(tmp_path: Path) -> None:
    workflow_path = _write_workflow(tmp_path / "empty.yaml", {})
    session = load_workflow_edit_session(workflow_path=workflow_path)

    view = build_workflow_form_view(
        workflow=session.workflow,
        ui_state=session.ui_state,
        workflow_path=workflow_path,
    )

    assert view.revision == session.revision
    assert view.nodes == ()
    assert view.edges == ()


def test_build_workflow_catalog_preview_collects_keys(tmp_path: Path) -> None:
    catalog_path = (FIXTURES_ROOT / "prompts" / "support_prompts.yaml").resolve()
    payload = _base_payload()
    payload["params"] = {"prompt_catalog": str(catalog_path)}
    workflow_path = _write_workflow(tmp_path / "catalog-preview.yaml", payload)

    preview = build_workflow_catalog_preview(
        workflow=payload,
        workflow_path=workflow_path,
        bundle_root=FIXTURES_ROOT,
    )

    assert preview.prompt_catalog_path == str(catalog_path)
    assert "planner" in preview.prompt_catalog_keys
    assert preview.issues == ()


def test_build_workflow_catalog_preview_reports_missing_and_invalid_catalogs(
    tmp_path: Path,
) -> None:
    payload = _base_payload()
    payload["params"] = {
        "prompt_catalog": "prompts/missing.yaml",
    }
    workflow_path = _write_workflow(tmp_path / "catalog-preview-error.yaml", payload)

    preview = build_workflow_catalog_preview(
        workflow=payload,
        workflow_path=workflow_path,
    )

    issue_codes = {issue.code for issue in preview.issues}
    assert "catalog_not_found" in issue_codes


# ---------------------------------------------------------------------------
# to_dict() methods for dataclasses (lines 38, 63, 86, 108, 125)
# ---------------------------------------------------------------------------


def test_workflow_node_form_item_to_dict() -> None:
    # Covers WorkflowNodeFormItem.to_dict() (line 38)
    item = WorkflowNodeFormItem(
        id="node1",
        handler="llm",
        prompt_ref="prompts/foo.yaml",
        prompt_system="sys",
        prompt_user="user",
        model={"provider": "openai", "name": "gpt-4o"},
    )
    d = item.to_dict()
    assert d["id"] == "node1"
    assert d["handler"] == "llm"
    assert d["prompt_ref"] == "prompts/foo.yaml"
    assert d["prompt_system"] == "sys"
    assert d["prompt_user"] == "user"
    assert d["model"] == {"provider": "openai", "name": "gpt-4o"}


def test_workflow_edge_form_item_to_dict() -> None:
    # Covers WorkflowEdgeFormItem.to_dict() (line 63)
    item = WorkflowEdgeFormItem(index=0, source="a", target="b", condition="cond")
    d = item.to_dict()
    assert d["index"] == 0
    assert d["source"] == "a"
    assert d["target"] == "b"
    assert d["condition"] == "cond"


def test_workflow_form_view_to_dict() -> None:
    # Covers WorkflowFormView.to_dict() (line 86)
    node = WorkflowNodeFormItem(
        id="n1", handler="llm", prompt_ref=None, prompt_system=None, prompt_user=None, model=None
    )
    edge = WorkflowEdgeFormItem(index=0, source="n1", target="n1", condition=None)
    view = WorkflowFormView(
        revision="rev1",
        nodes=(node,),
        edges=(edge,),
        prompt_catalog_keys=("key1",),
    )
    d = view.to_dict()
    assert d["revision"] == "rev1"
    assert len(d["nodes"]) == 1
    assert len(d["edges"]) == 1
    assert d["prompt_catalog_keys"] == ["key1"]


def test_workflow_catalog_issue_to_dict() -> None:
    # Covers WorkflowCatalogIssue.to_dict() (line 108)
    issue = WorkflowCatalogIssue(
        code="catalog_not_found",
        message="not found",
        location=("params", "prompt_catalog"),
    )
    d = issue.to_dict()
    assert d["code"] == "catalog_not_found"
    assert d["message"] == "not found"
    assert d["location"] == ["params", "prompt_catalog"]


def test_workflow_catalog_preview_to_dict() -> None:
    # Covers WorkflowCatalogPreview.to_dict() (line 125)
    issue = WorkflowCatalogIssue(code="err", message="msg", location=("params",))
    preview = WorkflowCatalogPreview(
        prompt_catalog_path="/some/path.yaml",
        prompt_catalog_keys=("key1", "key2"),
        issues=(issue,),
    )
    d = preview.to_dict()
    assert d["prompt_catalog_path"] == "/some/path.yaml"
    assert d["prompt_catalog_keys"] == ["key1", "key2"]
    assert len(d["issues"]) == 1


# ---------------------------------------------------------------------------
# build_workflow_form_view: edge cases for nodes_raw/edges_raw (lines 177-198)
# ---------------------------------------------------------------------------


def test_build_workflow_form_view_nodes_raw_is_none(tmp_path: Path) -> None:
    # When nodes is explicitly None (line 177)
    payload: dict = {"nodes": None, "edges": []}
    workflow_path = _write_workflow(tmp_path / "null_nodes.yaml", payload)
    session = load_workflow_edit_session(workflow_path=workflow_path)
    view = build_workflow_form_view(
        workflow=session.workflow, ui_state=session.ui_state, workflow_path=workflow_path
    )
    assert view.nodes == ()


def test_build_workflow_form_view_edges_raw_is_none(tmp_path: Path) -> None:
    # When edges is explicitly None (line 179)
    payload: dict = {"nodes": [], "edges": None}
    workflow_path = _write_workflow(tmp_path / "null_edges.yaml", payload)
    session = load_workflow_edit_session(workflow_path=workflow_path)
    view = build_workflow_form_view(
        workflow=session.workflow, ui_state=session.ui_state, workflow_path=workflow_path
    )
    assert view.edges == ()


def test_build_workflow_form_view_nodes_raw_not_list_raises(tmp_path: Path) -> None:
    # When nodes is not a list, raises ValueError (line 181)
    payload = _base_payload()
    payload["nodes"] = "not_a_list"
    workflow_path = _write_workflow(tmp_path / "invalid_nodes.yaml", payload)
    with pytest.raises(ValueError, match="workflow.nodes must be a list"):
        build_workflow_form_view(workflow=payload, ui_state={}, workflow_path=workflow_path)


def test_build_workflow_form_view_edges_raw_not_list_raises(tmp_path: Path) -> None:
    # When edges is not a list, raises ValueError (line 183)
    payload = _base_payload()
    payload["edges"] = "not_a_list"
    workflow_path = _write_workflow(tmp_path / "invalid_edges.yaml", payload)
    with pytest.raises(ValueError, match="workflow.edges must be a list"):
        build_workflow_form_view(workflow=payload, ui_state={}, workflow_path=workflow_path)


def test_build_workflow_form_view_skips_non_mapping_node(tmp_path: Path) -> None:
    # When a node entry is not a Mapping, it is skipped (line 188)
    payload = _base_payload()
    payload["nodes"] = ["not_a_mapping", {"id": "finish", "handler": "finish_handler"}]
    payload["edges"] = []
    workflow_path = _write_workflow(tmp_path / "bad_node.yaml", payload)
    view = build_workflow_form_view(workflow=payload, ui_state={}, workflow_path=workflow_path)
    assert len(view.nodes) == 1
    assert view.nodes[0].id == "finish"


def test_build_workflow_form_view_skips_node_with_missing_id_or_handler(tmp_path: Path) -> None:
    # When node has no id or no handler, it is skipped (line 193)
    payload = _base_payload()
    payload["nodes"] = [
        {"id": "ok_node", "handler": "h1"},
        {"handler": "h2"},  # missing id
        {"id": "no_handler_node"},  # missing handler
    ]
    payload["edges"] = []
    workflow_path = _write_workflow(tmp_path / "missing_fields.yaml", payload)
    view = build_workflow_form_view(workflow=payload, ui_state={}, workflow_path=workflow_path)
    assert len(view.nodes) == 1
    assert view.nodes[0].id == "ok_node"


def test_build_workflow_form_view_skips_node_with_non_mapping_params(tmp_path: Path) -> None:
    # When params is not a Mapping (not None), node is skipped (line 198)
    payload = _base_payload()
    payload["nodes"] = [
        {"id": "bad_params_node", "handler": "h1", "params": "not_a_mapping"},
        {"id": "good_node", "handler": "h2"},
    ]
    payload["edges"] = []
    workflow_path = _write_workflow(tmp_path / "bad_params.yaml", payload)
    view = build_workflow_form_view(workflow=payload, ui_state={}, workflow_path=workflow_path)
    assert all(n.id != "bad_params_node" for n in view.nodes)
    assert any(n.id == "good_node" for n in view.nodes)


def test_build_workflow_form_view_skips_non_mapping_edge(tmp_path: Path) -> None:
    # When an edge entry is not a Mapping, it is skipped (line 239)
    payload = _base_payload()
    payload["edges"] = ["not_a_mapping", {"source": "router", "target": "finish"}]
    workflow_path = _write_workflow(tmp_path / "bad_edge.yaml", payload)
    view = build_workflow_form_view(workflow=payload, ui_state={}, workflow_path=workflow_path)
    assert len(view.edges) == 1


def test_build_workflow_form_view_skips_edge_with_missing_source_or_target(tmp_path: Path) -> None:
    # When edge is missing source or target string, it is skipped (line 245)
    payload = _base_payload()
    payload["edges"] = [
        {"source": "router", "target": "finish"},  # valid
        {"source": "router"},  # missing target
        {"target": "finish"},  # missing source
        {"source": 123, "target": "finish"},  # source not str
    ]
    workflow_path = _write_workflow(tmp_path / "missing_edge_fields.yaml", payload)
    view = build_workflow_form_view(workflow=payload, ui_state={}, workflow_path=workflow_path)
    assert len(view.edges) == 1


def test_build_workflow_form_view_skips_edge_with_non_string_condition(tmp_path: Path) -> None:
    # When condition is not None and not str, edge is skipped (line 247)
    payload = _base_payload()
    payload["edges"] = [
        {"source": "router", "target": "finish", "condition": 42},  # invalid condition type
        {"source": "router", "target": "planner"},  # valid, no condition
    ]
    workflow_path = _write_workflow(tmp_path / "bad_condition.yaml", payload)
    view = build_workflow_form_view(workflow=payload, ui_state={}, workflow_path=workflow_path)
    assert len(view.edges) == 1
    assert view.edges[0].condition is None


# ---------------------------------------------------------------------------
# build_workflow_catalog_preview: non-mapping params (lines 285-287)
# ---------------------------------------------------------------------------


def test_build_workflow_catalog_preview_non_mapping_params(tmp_path: Path) -> None:
    # When workflow.params is not a Mapping, returns invalid_workflow_params issue (lines 285-297)
    payload = dict(_base_payload())
    payload["params"] = "not_a_mapping"
    workflow_path = _write_workflow(tmp_path / "bad_params_catalog.yaml", payload)
    preview = build_workflow_catalog_preview(workflow=payload, workflow_path=workflow_path)
    issue_codes = {issue.code for issue in preview.issues}
    assert "invalid_workflow_params" in issue_codes


def test_build_workflow_catalog_preview_no_params_key(tmp_path: Path) -> None:
    # When workflow has no 'params' key at all (params_raw is None), defaults to {} (line 285)
    payload = dict(_base_payload())
    del payload["params"]
    workflow_path = _write_workflow(tmp_path / "no_params.yaml", payload)
    preview = build_workflow_catalog_preview(workflow=payload, workflow_path=workflow_path)
    assert preview.prompt_catalog_path is None
    assert preview.prompt_catalog_keys == ()
    assert preview.issues == ()


def test_build_workflow_catalog_preview_no_catalog_path(tmp_path: Path) -> None:
    # When prompt_catalog is absent, returns empty issues and no keys (line 323 of _resolve_catalog_setting)
    payload = _base_payload()
    payload["params"] = {}
    workflow_path = _write_workflow(tmp_path / "no_catalog.yaml", payload)
    preview = build_workflow_catalog_preview(workflow=payload, workflow_path=workflow_path)
    assert preview.prompt_catalog_path is None
    assert preview.prompt_catalog_keys == ()
    assert preview.issues == ()


def test_build_workflow_catalog_preview_catalog_path_not_string(tmp_path: Path) -> None:
    # When prompt_catalog value is not a string, returns catalog_path_type_error (line 325)
    payload = _base_payload()
    payload["params"] = {"prompt_catalog": 42}
    workflow_path = _write_workflow(tmp_path / "non_str_catalog.yaml", payload)
    preview = build_workflow_catalog_preview(workflow=payload, workflow_path=workflow_path)
    issue_codes = {issue.code for issue in preview.issues}
    assert "catalog_path_type_error" in issue_codes


def test_build_workflow_catalog_preview_catalog_path_empty_string(tmp_path: Path) -> None:
    # When prompt_catalog is an empty/whitespace string, returns no issues (line 337)
    payload = _base_payload()
    payload["params"] = {"prompt_catalog": "   "}
    workflow_path = _write_workflow(tmp_path / "empty_catalog.yaml", payload)
    preview = build_workflow_catalog_preview(workflow=payload, workflow_path=workflow_path)
    assert preview.prompt_catalog_path is None
    assert preview.issues == ()


def test_build_workflow_catalog_preview_catalog_load_error(tmp_path: Path) -> None:
    # When catalog file exists but fails to parse (YAML error) (lines 361-362)
    catalog_path = tmp_path / "bad_catalog.yaml"
    catalog_path.write_text("key: [unclosed bracket\n", encoding="utf-8")
    payload = _base_payload()
    payload["params"] = {"prompt_catalog": str(catalog_path)}
    workflow_path = _write_workflow(tmp_path / "bad_catalog_workflow.yaml", payload)
    preview = build_workflow_catalog_preview(workflow=payload, workflow_path=workflow_path)
    issue_codes = {issue.code for issue in preview.issues}
    assert "catalog_load_error" in issue_codes


def test_build_workflow_catalog_preview_catalog_not_mapping(tmp_path: Path) -> None:
    # When catalog file content is not a mapping (e.g. a list) (line 375)
    catalog_path = tmp_path / "list_catalog.yaml"
    catalog_path.write_text("- item1\n- item2\n", encoding="utf-8")
    payload = _base_payload()
    payload["params"] = {"prompt_catalog": str(catalog_path)}
    workflow_path = _write_workflow(tmp_path / "list_catalog_workflow.yaml", payload)
    preview = build_workflow_catalog_preview(workflow=payload, workflow_path=workflow_path)
    issue_codes = {issue.code for issue in preview.issues}
    assert "catalog_not_mapping" in issue_codes


def test_build_workflow_catalog_preview_with_bundle_root(tmp_path: Path) -> None:
    # Uses bundle_root for resolving catalog path (line 408)
    bundle_root = tmp_path / "bundle"
    bundle_root.mkdir()
    catalog_path = bundle_root / "catalog.yaml"
    catalog_path.write_text("key1:\n  nested: value\n", encoding="utf-8")
    payload = _base_payload()
    payload["params"] = {"prompt_catalog": "catalog.yaml"}
    workflow_path = _write_workflow(tmp_path / "bundle_catalog.yaml", payload)
    preview = build_workflow_catalog_preview(
        workflow=payload, workflow_path=workflow_path, bundle_root=bundle_root
    )
    assert "key1" in preview.prompt_catalog_keys
    assert preview.issues == ()


def test_collect_key_paths_nested_mapping(tmp_path: Path) -> None:
    # Covers nested mapping in _collect_key_paths (line 428-429)
    catalog_path = tmp_path / "nested_catalog.yaml"
    catalog_path.write_text(
        "parent:\n  child1: val\n  child2:\n    grandchild: val\n", encoding="utf-8"
    )
    payload = _base_payload()
    payload["params"] = {"prompt_catalog": str(catalog_path)}
    workflow_path = _write_workflow(tmp_path / "nested_workflow.yaml", payload)
    preview = build_workflow_catalog_preview(workflow=payload, workflow_path=workflow_path)
    assert "parent" in preview.prompt_catalog_keys
    assert "parent.child1" in preview.prompt_catalog_keys
    assert "parent.child2" in preview.prompt_catalog_keys
    assert "parent.child2.grandchild" in preview.prompt_catalog_keys


def test_collect_key_paths_skips_non_string_keys(tmp_path: Path) -> None:
    # Catalog dicts with non-string keys are skipped (line 425 continue)
    # We create a catalog file but then exercise _collect_key_paths directly with a non-string key
    from yagra.application.use_cases.workflow_form_model import _collect_key_paths

    payload_with_non_str_key: dict = {"valid_key": "value", 42: "ignored"}
    result = _collect_key_paths(payload_with_non_str_key, prefix="")
    assert "valid_key" in result
    assert len(result) == 1  # non-string key 42 is skipped


# ---------------------------------------------------------------------------
# _try_load_prompt_ref: direct tests (lines 463-480)
# ---------------------------------------------------------------------------


def test_try_load_prompt_ref_simple_file(tmp_path: Path) -> None:
    # Simple file without anchor (line 463, 480)
    prompt_file = tmp_path / "prompt.yaml"
    prompt_file.write_text("system: Hello {name}\nuser: Ask {query}\n", encoding="utf-8")
    result = _try_load_prompt_ref(
        prompt_ref="prompt.yaml",
        workflow_path=tmp_path / "workflow.yaml",
        bundle_root=None,
    )
    assert isinstance(result, dict)
    assert "system" in result


def test_try_load_prompt_ref_with_anchor(tmp_path: Path) -> None:
    # With '#section' anchor (lines 459-461, 476-478)
    prompt_file = tmp_path / "prompts.yaml"
    prompt_file.write_text(
        "planner:\n  system: Plan {task}\nother:\n  user: Hello\n", encoding="utf-8"
    )
    result = _try_load_prompt_ref(
        prompt_ref="prompts.yaml#planner",
        workflow_path=tmp_path / "workflow.yaml",
        bundle_root=None,
    )
    assert isinstance(result, dict)
    assert "system" in result


def test_try_load_prompt_ref_with_anchor_empty_section(tmp_path: Path) -> None:
    # Anchor with empty/whitespace section name treated as None (line 461)
    prompt_file = tmp_path / "prompts.yaml"
    prompt_file.write_text("key: value\n", encoding="utf-8")
    result = _try_load_prompt_ref(
        prompt_ref="prompts.yaml#",
        workflow_path=tmp_path / "workflow.yaml",
        bundle_root=None,
    )
    # empty anchor treated as no section, returns full content
    assert result == {"key": "value"}


def test_try_load_prompt_ref_with_bundle_root(tmp_path: Path) -> None:
    # Uses bundle_root for path resolution (line 469)
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    prompt_file = bundle / "prompt.yaml"
    prompt_file.write_text("user: Translate {text}\n", encoding="utf-8")
    result = _try_load_prompt_ref(
        prompt_ref="prompt.yaml",
        workflow_path=tmp_path / "workflow.yaml",
        bundle_root=bundle,
    )
    assert isinstance(result, dict)
    assert "user" in result


def test_try_load_prompt_ref_absolute_path(tmp_path: Path) -> None:
    # Absolute path (line 467)
    prompt_file = tmp_path / "abs_prompt.yaml"
    prompt_file.write_text("user: Hello {name}\n", encoding="utf-8")
    result = _try_load_prompt_ref(
        prompt_ref=str(prompt_file),
        workflow_path=tmp_path / "workflow.yaml",
        bundle_root=None,
    )
    assert isinstance(result, dict)
    assert "user" in result


def test_try_load_prompt_ref_file_not_found(tmp_path: Path) -> None:
    # File not found returns None (line 481-482)
    result = _try_load_prompt_ref(
        prompt_ref="nonexistent.yaml",
        workflow_path=tmp_path / "workflow.yaml",
        bundle_root=None,
    )
    assert result is None


def test_try_load_prompt_ref_anchor_data_not_dict(tmp_path: Path) -> None:
    # When file is a list and anchor is provided, returns None (line 479)
    prompt_file = tmp_path / "list.yaml"
    prompt_file.write_text("- item1\n- item2\n", encoding="utf-8")
    result = _try_load_prompt_ref(
        prompt_ref="list.yaml#section",
        workflow_path=tmp_path / "workflow.yaml",
        bundle_root=None,
    )
    assert result is None


# ---------------------------------------------------------------------------
# _as_optional_mapping and _as_optional_string helpers (lines 512, 530)
# ---------------------------------------------------------------------------


def test_as_optional_mapping_with_mapping() -> None:
    # Returns deepcopy dict when value is a Mapping
    result = _as_optional_mapping({"key": "value"})
    assert result == {"key": "value"}


def test_as_optional_mapping_with_non_mapping() -> None:
    # Returns None when value is not a Mapping (line 495 else branch, full function covered)
    assert _as_optional_mapping("string") is None
    assert _as_optional_mapping(42) is None
    assert _as_optional_mapping(None) is None


def test_as_optional_string_with_valid_string() -> None:
    # Returns stripped string when non-empty
    assert _as_optional_string("  hello  ") == "hello"
    assert _as_optional_string("value") == "value"


def test_as_optional_string_with_empty_string() -> None:
    # Returns None when string is empty or whitespace only (line 512)
    assert _as_optional_string("") is None
    assert _as_optional_string("   ") is None


def test_as_optional_string_with_non_string() -> None:
    # Returns None when value is not a string (line 508-509)
    assert _as_optional_string(42) is None
    assert _as_optional_string(None) is None


def test_ensure_mapping_raises_for_non_mapping() -> None:
    # Raises ValueError when payload is not a Mapping (line 530)
    with pytest.raises(ValueError, match="my_label must be a mapping"):
        _ensure_mapping("not_a_mapping", label="my_label")  # type: ignore[arg-type]


def test_ensure_mapping_returns_dict_copy() -> None:
    # Returns dict copy of Mapping
    result = _ensure_mapping({"a": 1, "b": 2}, label="test")
    assert result == {"a": 1, "b": 2}


# ---------------------------------------------------------------------------
# build_workflow_form_view: node with prompt_ref individual resolution (line 208-215)
# ---------------------------------------------------------------------------


def test_build_workflow_form_view_individual_prompt_ref_resolution(tmp_path: Path) -> None:
    # When whole-workflow resolution fails for a node, individual prompt_ref is tried (lines 208-215)
    prompt_file = tmp_path / "prompt.yaml"
    prompt_file.write_text("system: You are {role}.\nuser: Handle {task}.\n", encoding="utf-8")
    payload = {
        "version": "1.0",
        "start_at": "node1",
        "end_at": ["node1"],
        "nodes": [
            {
                "id": "node1",
                "handler": "llm",
                "params": {"prompt_ref": "prompt.yaml"},
            }
        ],
        "edges": [],
        "params": {},
    }
    workflow_path = _write_workflow(tmp_path / "wf.yaml", payload)
    session = load_workflow_edit_session(workflow_path=workflow_path)
    view = build_workflow_form_view(
        workflow=session.workflow,
        ui_state=session.ui_state,
        workflow_path=workflow_path,
        bundle_root=None,
    )
    assert len(view.nodes) == 1
    n = view.nodes[0]
    assert n.prompt_ref == "prompt.yaml"
    # Individual resolution should pick up system and user from the file
    assert n.prompt_system == "You are {role}."
    assert n.prompt_user == "Handle {task}."
