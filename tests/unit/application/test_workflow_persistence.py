from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
import yaml

from yagra.application.use_cases.workflow_edit_session import load_workflow_edit_session
from yagra.application.use_cases.workflow_persistence import (
    WorkflowRevisionConflictError,
    rollback_workflow_from_backup,
    save_workflow_with_backup,
)
from yagra.application.use_cases.workflow_validation_reporter import WorkflowValidationFailedError


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


def test_save_workflow_with_backup_and_rollback(tmp_path: Path) -> None:
    workflow_path = _write_workflow(tmp_path / "workflow.yaml", _base_payload())
    backup_root = tmp_path / ".yagra-backups"
    before_session = load_workflow_edit_session(workflow_path=workflow_path)

    candidate_workflow = deepcopy(before_session.workflow)
    candidate_workflow["params"] = {"temperature": 0.2}
    candidate_ui_state = {"positions": {"router": {"x": 30, "y": 40}}}
    save_result = save_workflow_with_backup(
        workflow_path=workflow_path,
        candidate_workflow=candidate_workflow,
        candidate_ui_state=candidate_ui_state,
        base_revision=before_session.revision,
        backup_dir=backup_root,
    )

    after_save_session = load_workflow_edit_session(workflow_path=workflow_path)
    assert after_save_session.revision == save_result.saved_revision
    assert after_save_session.workflow["params"]["temperature"] == 0.2
    assert after_save_session.ui_state["positions"]["router"]["x"] == 30

    rollback_result = rollback_workflow_from_backup(
        workflow_path=workflow_path,
        backup_id=save_result.backup_id,
        backup_dir=backup_root,
    )
    after_rollback_session = load_workflow_edit_session(workflow_path=workflow_path)
    assert after_rollback_session.revision == rollback_result.restored_revision
    assert after_rollback_session.revision == before_session.revision
    assert after_rollback_session.workflow["params"] == {}
    assert after_rollback_session.ui_state == {}
    assert rollback_result.safety_backup_id

    restore_latest_result = rollback_workflow_from_backup(
        workflow_path=workflow_path,
        backup_id=rollback_result.safety_backup_id,
        backup_dir=backup_root,
    )
    after_restore_latest_session = load_workflow_edit_session(workflow_path=workflow_path)
    assert after_restore_latest_session.revision == restore_latest_result.restored_revision
    assert after_restore_latest_session.revision == after_save_session.revision
    assert after_restore_latest_session.workflow["params"]["temperature"] == 0.2
    assert after_restore_latest_session.ui_state["positions"]["router"]["x"] == 30


def test_save_workflow_with_backup_raises_revision_conflict(tmp_path: Path) -> None:
    workflow_path = _write_workflow(tmp_path / "workflow.yaml", _base_payload())
    backup_root = tmp_path / ".yagra-backups"
    before_session = load_workflow_edit_session(workflow_path=workflow_path)

    first_candidate = deepcopy(before_session.workflow)
    first_candidate["params"] = {"temperature": 0.3}
    save_workflow_with_backup(
        workflow_path=workflow_path,
        candidate_workflow=first_candidate,
        candidate_ui_state={},
        base_revision=before_session.revision,
        backup_dir=backup_root,
    )

    second_candidate = deepcopy(first_candidate)
    second_candidate["params"] = {"temperature": 0.5}
    with pytest.raises(WorkflowRevisionConflictError):
        save_workflow_with_backup(
            workflow_path=workflow_path,
            candidate_workflow=second_candidate,
            candidate_ui_state={},
            base_revision=before_session.revision,
            backup_dir=backup_root,
        )


def test_save_workflow_with_backup_raises_validation_error(tmp_path: Path) -> None:
    workflow_path = _write_workflow(tmp_path / "workflow.yaml", _base_payload())
    backup_root = tmp_path / ".yagra-backups"
    before_session = load_workflow_edit_session(workflow_path=workflow_path)

    invalid_candidate = deepcopy(before_session.workflow)
    del invalid_candidate["edges"]
    with pytest.raises(WorkflowValidationFailedError):
        save_workflow_with_backup(
            workflow_path=workflow_path,
            candidate_workflow=invalid_candidate,
            candidate_ui_state={},
            base_revision=before_session.revision,
            backup_dir=backup_root,
        )
