from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from yagra.application.use_cases.workflow_edit_session import (
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
    invalid_candidate["edges"] = []
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
