from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
import yaml

from yagra.application.use_cases.workflow_edit_session import (
    _collect_changes,
    _ensure_mapping,
    _path_token,
    build_workflow_diff,
    compute_workflow_revision,
    load_workflow_edit_session,
    resolve_ui_state_path,
)


def _base_payload() -> dict[str, Any]:
    return {
        "version": "1.0",
        "start_at": "router",
        "end_at": ["finish"],
        "nodes": [
            {"id": "router", "handler": "router_handler"},
            {"id": "planner", "handler": "planner_handler"},
            {"id": "finish", "handler": "finish_handler"},
        ],
        "edges": [
            {"source": "router", "target": "planner", "condition": "needs_plan"},
            {"source": "router", "target": "finish", "condition": "direct_answer"},
            {"source": "planner", "target": "finish"},
        ],
        "params": {},
    }


def _write_workflow(path: Path, payload: dict[str, Any]) -> Path:
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


def test_load_workflow_edit_session_loads_revision_and_validation(tmp_path: Path) -> None:
    workflow_path = _write_workflow(tmp_path / "workflow.yaml", _base_payload())
    ui_state_path = resolve_ui_state_path(workflow_path)
    ui_state_path.write_text('{"positions":{"router":{"x":10,"y":20}}}\n', encoding="utf-8")

    session = load_workflow_edit_session(workflow_path=workflow_path)

    assert session.validation_report.is_valid is True
    assert session.ui_state["positions"]["router"]["x"] == 10
    assert session.revision == compute_workflow_revision(session.workflow, session.ui_state)


def test_build_workflow_diff_returns_summary_and_unified_diff(tmp_path: Path) -> None:
    base_workflow = _base_payload()
    candidate_workflow = _base_payload()
    candidate_workflow["params"] = {"temperature": 0.1}
    candidate_ui_state = {"positions": {"router": {"x": 120, "y": 240}}}
    workflow_path = _write_workflow(tmp_path / "workflow.yaml", base_workflow)

    result = build_workflow_diff(
        base_workflow=base_workflow,
        candidate_workflow=candidate_workflow,
        base_ui_state={},
        candidate_ui_state=candidate_ui_state,
        workflow_path=workflow_path,
    )

    assert result.base_revision != result.candidate_revision
    assert result.summary["total"] >= 1
    assert result.summary["params"] >= 1
    assert result.summary["ui_state"] >= 1
    assert "candidate/workflow.yaml" in result.yaml_unified_diff
    assert result.validation_report.is_valid is True


def test_build_workflow_diff_returns_validation_errors_for_invalid_candidate(
    tmp_path: Path,
) -> None:
    base_workflow = _base_payload()
    invalid_candidate = _base_payload()
    del invalid_candidate["edges"]
    workflow_path = _write_workflow(tmp_path / "workflow.yaml", base_workflow)

    result = build_workflow_diff(
        base_workflow=base_workflow,
        candidate_workflow=invalid_candidate,
        base_ui_state={},
        candidate_ui_state={},
        workflow_path=workflow_path,
    )

    assert result.validation_report.is_valid is False
    assert any(issue.code == "schema_error" for issue in result.validation_report.issues)


# ---------------------------------------------------------------------------
# _load_workflow_mapping: error paths (lines 246-247)
# ---------------------------------------------------------------------------


def test_load_workflow_edit_session_raises_on_missing_file(tmp_path: Path) -> None:
    """Lines 246-247: missing workflow file raises ValueError."""
    with pytest.raises(ValueError, match="Failed to load workflow"):
        load_workflow_edit_session(workflow_path=tmp_path / "missing.yaml")


def test_load_workflow_edit_session_raises_on_invalid_yaml(tmp_path: Path) -> None:
    """Lines 246-247: YAML parse error raises ValueError."""
    bad_yaml = tmp_path / "bad.yaml"
    bad_yaml.write_text("key: [\ninvalid: yaml:", encoding="utf-8")
    with pytest.raises(ValueError, match="Failed to load workflow"):
        load_workflow_edit_session(workflow_path=bad_yaml)


# ---------------------------------------------------------------------------
# _load_ui_state_mapping: error paths (lines 267-268)
# ---------------------------------------------------------------------------


def test_load_workflow_edit_session_raises_on_invalid_ui_state_json(tmp_path: Path) -> None:
    """Lines 267-268: invalid JSON in ui_state raises ValueError."""
    workflow_path = _write_workflow(tmp_path / "workflow.yaml", _base_payload())
    ui_state_path = resolve_ui_state_path(workflow_path)
    ui_state_path.write_text("not valid json {{{", encoding="utf-8")
    with pytest.raises(ValueError, match="Failed to load ui_state"):
        load_workflow_edit_session(workflow_path=workflow_path)


def test_load_workflow_edit_session_raises_on_os_error_for_ui_state(tmp_path: Path) -> None:
    """Lines 267-268: OS error reading ui_state raises ValueError."""
    workflow_path = _write_workflow(tmp_path / "workflow.yaml", _base_payload())
    ui_state_path = resolve_ui_state_path(workflow_path)
    ui_state_path.write_text("{}", encoding="utf-8")

    with patch("pathlib.Path.read_text", side_effect=OSError("IO error")):
        with pytest.raises(ValueError, match="Failed to load"):
            load_workflow_edit_session(workflow_path=workflow_path)


# ---------------------------------------------------------------------------
# resolve_ui_state_path with explicit path (line 101)
# ---------------------------------------------------------------------------


def test_resolve_ui_state_path_with_explicit_path(tmp_path: Path) -> None:
    """Line 101: when ui_state_path is explicitly provided, it is returned as-is."""
    explicit_path = tmp_path / "custom_ui_state.json"
    result = resolve_ui_state_path(
        workflow_path=tmp_path / "workflow.yaml",
        ui_state_path=explicit_path,
    )
    assert result == explicit_path.expanduser().resolve()


def test_load_workflow_edit_session_uses_explicit_ui_state_path(tmp_path: Path) -> None:
    """Line 101: explicit ui_state_path is used instead of default derived path."""
    workflow_path = _write_workflow(tmp_path / "workflow.yaml", _base_payload())
    custom_ui = tmp_path / "my_ui.json"
    custom_ui.write_text(json.dumps({"custom": True}), encoding="utf-8")

    session = load_workflow_edit_session(
        workflow_path=workflow_path,
        ui_state_path=custom_ui,
    )
    assert session.ui_state["custom"] is True


# ---------------------------------------------------------------------------
# _ensure_mapping: raises for non-mapping (line 286)
# ---------------------------------------------------------------------------


def test_ensure_mapping_raises_for_list() -> None:
    """Line 286: _ensure_mapping raises ValueError for a list."""
    with pytest.raises(ValueError, match="must be a mapping"):
        _ensure_mapping(["not", "a", "dict"], label="test label")


def test_ensure_mapping_raises_for_none() -> None:
    """Line 286: _ensure_mapping raises ValueError for None."""
    with pytest.raises(ValueError, match="must be a mapping"):
        _ensure_mapping(None, label="test label")


# ---------------------------------------------------------------------------
# _collect_changes: list add / list remove (lines 344-362)
# ---------------------------------------------------------------------------


def test_collect_changes_list_item_added() -> None:
    """Lines 344-352: when after has more items than before, 'add' changes are produced."""
    before = ["a", "b"]
    after = ["a", "b", "c"]
    changes = _collect_changes(before, after, path=("nodes",))
    add_changes = [c for c in changes if c.kind == "add"]
    assert len(add_changes) == 1
    assert add_changes[0].after == "c"
    assert add_changes[0].path == ("nodes", 2)


def test_collect_changes_list_item_removed() -> None:
    """Lines 354-362: when before has more items than after, 'remove' changes are produced."""
    before = ["a", "b", "c"]
    after = ["a", "b"]
    changes = _collect_changes(before, after, path=("edges",))
    remove_changes = [c for c in changes if c.kind == "remove"]
    assert len(remove_changes) == 1
    assert remove_changes[0].before == "c"
    assert remove_changes[0].path == ("edges", 2)


def test_collect_changes_list_all_items_added() -> None:
    """Lines 344-352: when before is empty and after has items, all are 'add' changes."""
    before: list[Any] = []
    after = [{"id": "x"}, {"id": "y"}]
    changes = _collect_changes(before, after, path=())
    assert all(c.kind == "add" for c in changes)
    assert len(changes) == 2


def test_collect_changes_list_all_items_removed() -> None:
    """Lines 354-362: when after is empty and before has items, all are 'remove' changes."""
    before = [1, 2, 3]
    after: list[Any] = []
    changes = _collect_changes(before, after, path=())
    assert all(c.kind == "remove" for c in changes)
    assert len(changes) == 3


# ---------------------------------------------------------------------------
# _build_summary via build_workflow_diff: category routing (lines 373, 403-404, 407, 415)
# ---------------------------------------------------------------------------


def test_build_workflow_diff_counts_edges_changes(tmp_path: Path) -> None:
    """Lines 403-404: changes to 'edges' are counted under 'edges' in summary."""
    base_workflow = _base_payload()
    candidate_workflow = _base_payload()
    candidate_workflow["edges"] = [
        {"source": "router", "target": "planner", "condition": "needs_plan"},
    ]
    workflow_path = _write_workflow(tmp_path / "workflow.yaml", base_workflow)

    result = build_workflow_diff(
        base_workflow=base_workflow,
        candidate_workflow=candidate_workflow,
        base_ui_state={},
        candidate_ui_state={},
        workflow_path=workflow_path,
    )

    assert result.summary["edges"] >= 1


def test_build_workflow_diff_counts_params_changes(tmp_path: Path) -> None:
    """Line 407: changes to 'params' are counted under 'params' in summary."""
    base_workflow = _base_payload()
    candidate_workflow = _base_payload()
    candidate_workflow["params"] = {"max_tokens": 1000}
    workflow_path = _write_workflow(tmp_path / "workflow.yaml", base_workflow)

    result = build_workflow_diff(
        base_workflow=base_workflow,
        candidate_workflow=candidate_workflow,
        base_ui_state={},
        candidate_ui_state={},
        workflow_path=workflow_path,
    )

    assert result.summary["params"] >= 1


def test_build_workflow_diff_counts_other_changes(tmp_path: Path) -> None:
    """Line 415: changes to non-standard top-level keys are counted under 'other' in summary."""
    base_workflow = _base_payload()
    candidate_workflow = _base_payload()
    candidate_workflow["version"] = "2.0"  # version key falls into "other"
    workflow_path = _write_workflow(tmp_path / "workflow.yaml", base_workflow)

    result = build_workflow_diff(
        base_workflow=base_workflow,
        candidate_workflow=candidate_workflow,
        base_ui_state={},
        candidate_ui_state={},
        workflow_path=workflow_path,
    )

    assert result.summary["other"] >= 1


def test_build_summary_empty_path_counts_as_other(tmp_path: Path) -> None:
    """Line 373: WorkflowChange with empty path is counted as 'other'."""
    from yagra.application.use_cases.workflow_edit_session import (
        WorkflowChange,
        _build_summary,
    )

    changes = [
        WorkflowChange(kind="update", path=(), before="old", after="new"),
    ]
    summary = _build_summary(changes)
    assert summary["other"] == 1
    assert summary["total"] == 1


# ---------------------------------------------------------------------------
# _path_token: non-str/int value (line 452)
# ---------------------------------------------------------------------------


def test_path_token_converts_non_str_int_to_str() -> None:
    """Line 452: _path_token returns str() for non-str/int values."""
    result = _path_token(3.14)
    assert result == "3.14"

    result2 = _path_token(None)
    assert result2 == "None"

    result3 = _path_token((1, 2))
    assert result3 == "(1, 2)"


# ---------------------------------------------------------------------------
# _collect_changes: no changes when lists and values are equal
# ---------------------------------------------------------------------------


def test_collect_changes_identical_lists_no_changes() -> None:
    """Equal lists produce no changes."""
    before = [1, 2, 3]
    after = [1, 2, 3]
    changes = _collect_changes(before, after, path=())
    assert changes == []


def test_collect_changes_identical_scalars_no_changes() -> None:
    """Equal scalar values produce no changes."""
    changes = _collect_changes("hello", "hello", path=())
    assert changes == []


def test_build_workflow_diff_no_changes_empty_diff(tmp_path: Path) -> None:
    """When base and candidate are identical, diff should have zero total changes."""
    base_workflow = _base_payload()
    workflow_path = _write_workflow(tmp_path / "workflow.yaml", base_workflow)

    result = build_workflow_diff(
        base_workflow=base_workflow,
        candidate_workflow=base_workflow,
        base_ui_state={},
        candidate_ui_state={},
        workflow_path=workflow_path,
    )

    assert result.summary["total"] == 0
    assert result.yaml_unified_diff == ""
    assert result.base_revision == result.candidate_revision


# ---------------------------------------------------------------------------
# WorkflowChange.to_dict() (line 52) and WorkflowDiffResult.to_dict() (line 77)
# ---------------------------------------------------------------------------


def test_workflow_change_to_dict() -> None:
    """Line 52: WorkflowChange.to_dict() returns the expected dictionary."""
    from yagra.application.use_cases.workflow_edit_session import WorkflowChange

    change = WorkflowChange(kind="update", path=("nodes", 0, "id"), before="old", after="new")
    d = change.to_dict()

    assert d["kind"] == "update"
    assert d["path"] == ["nodes", 0, "id"]
    assert d["before"] == "old"
    assert d["after"] == "new"


def test_workflow_diff_result_to_dict(tmp_path: Path) -> None:
    """Line 77: WorkflowDiffResult.to_dict() returns the expected dictionary."""
    base_workflow = _base_payload()
    candidate_workflow = _base_payload()
    candidate_workflow["params"] = {"temperature": 0.5}
    workflow_path = _write_workflow(tmp_path / "workflow.yaml", base_workflow)

    result = build_workflow_diff(
        base_workflow=base_workflow,
        candidate_workflow=candidate_workflow,
        base_ui_state={},
        candidate_ui_state={},
        workflow_path=workflow_path,
    )

    d = result.to_dict()
    assert "base_revision" in d
    assert "candidate_revision" in d
    assert "summary" in d
    assert "changes" in d
    assert "yaml_unified_diff" in d
    assert "validation_report" in d


# ---------------------------------------------------------------------------
# _build_summary: nodes category (line 407)
# ---------------------------------------------------------------------------


def test_build_workflow_diff_counts_nodes_changes(tmp_path: Path) -> None:
    """Line 407: changes to 'nodes' are counted under 'nodes' in summary."""
    base_workflow = _base_payload()
    candidate_workflow = _base_payload()
    # Change a node's handler to trigger a nodes-category change
    candidate_workflow["nodes"][0]["handler"] = "new_handler"
    workflow_path = _write_workflow(tmp_path / "workflow.yaml", base_workflow)

    result = build_workflow_diff(
        base_workflow=base_workflow,
        candidate_workflow=candidate_workflow,
        base_ui_state={},
        candidate_ui_state={},
        workflow_path=workflow_path,
    )

    assert result.summary["nodes"] >= 1
