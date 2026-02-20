from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
import yaml

from yagra.application.services.workflow_file_store import WorkflowBackupNotFoundError
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


def test_save_workflow_with_backup_restores_on_write_failure(tmp_path: Path) -> None:
    """Lines 130-136: if atomic write fails, the backup is restored and exception re-raised."""
    workflow_path = _write_workflow(tmp_path / "workflow.yaml", _base_payload())
    backup_root = tmp_path / ".yagra-backups"
    before_session = load_workflow_edit_session(workflow_path=workflow_path)

    candidate_workflow = deepcopy(before_session.workflow)
    candidate_workflow["params"] = {"temperature": 0.9}

    with patch(
        "yagra.application.use_cases.workflow_persistence.WorkflowFileStore.write_workflow_atomic",
        side_effect=OSError("disk full"),
    ):
        with pytest.raises(OSError, match="disk full"):
            save_workflow_with_backup(
                workflow_path=workflow_path,
                candidate_workflow=candidate_workflow,
                candidate_ui_state={},
                base_revision=before_session.revision,
                backup_dir=backup_root,
            )

    # After the failure the original workflow should still be intact
    restored_session = load_workflow_edit_session(workflow_path=workflow_path)
    assert restored_session.workflow["params"] == {}


def test_rollback_workflow_raises_when_backup_not_found(tmp_path: Path) -> None:
    """Line 171: rollback raises WorkflowBackupNotFoundError when backup does not exist."""
    workflow_path = _write_workflow(tmp_path / "workflow.yaml", _base_payload())
    backup_root = tmp_path / ".yagra-backups"

    with pytest.raises(WorkflowBackupNotFoundError, match="backup not found"):
        rollback_workflow_from_backup(
            workflow_path=workflow_path,
            backup_id="nonexistent_id",
            backup_dir=backup_root,
        )


def test_rollback_workflow_restores_safety_backup_on_failure(tmp_path: Path) -> None:
    """Lines 187-193: if restore fails, the safety backup is restored and exception re-raised."""
    workflow_path = _write_workflow(tmp_path / "workflow.yaml", _base_payload())
    backup_root = tmp_path / ".yagra-backups"
    before_session = load_workflow_edit_session(workflow_path=workflow_path)

    # Create initial save so we have a backup to roll back to
    candidate_workflow = deepcopy(before_session.workflow)
    candidate_workflow["params"] = {"temperature": 0.7}
    save_result = save_workflow_with_backup(
        workflow_path=workflow_path,
        candidate_workflow=candidate_workflow,
        candidate_ui_state={"x": 1},
        base_revision=before_session.revision,
        backup_dir=backup_root,
    )

    after_save_session = load_workflow_edit_session(workflow_path=workflow_path)

    call_count = 0

    original_restore = None

    from yagra.application.services.workflow_file_store import WorkflowFileStore

    original_restore = WorkflowFileStore.restore_backup

    def _failing_restore(self, workflow_path, ui_state_path, backup_id):  # noqa: ANN001
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise OSError("simulated restore failure")
        return original_restore(self, workflow_path, ui_state_path, backup_id)

    with patch.object(WorkflowFileStore, "restore_backup", _failing_restore):
        with pytest.raises(OSError, match="simulated restore failure"):
            rollback_workflow_from_backup(
                workflow_path=workflow_path,
                backup_id=save_result.backup_id,
                backup_dir=backup_root,
            )

    # The safety backup restore (2nd call) should have put back the post-save state
    recovered_session = load_workflow_edit_session(workflow_path=workflow_path)
    assert recovered_session.revision == after_save_session.revision


def test_save_workflow_with_backup_ensure_mapping_raises_for_non_mapping(
    tmp_path: Path,
) -> None:
    """Line 229: _ensure_mapping raises ValueError when payload is not a Mapping."""
    workflow_path = _write_workflow(tmp_path / "workflow.yaml", _base_payload())
    backup_root = tmp_path / ".yagra-backups"
    before_session = load_workflow_edit_session(workflow_path=workflow_path)

    with pytest.raises(ValueError, match="must be a mapping"):
        save_workflow_with_backup(
            workflow_path=workflow_path,
            candidate_workflow=["not", "a", "dict"],  # type: ignore[arg-type]
            candidate_ui_state={},
            base_revision=before_session.revision,
            backup_dir=backup_root,
        )


def test_save_workflow_with_backup_with_explicit_ui_state_path(tmp_path: Path) -> None:
    """Covers ui_state_path parameter passing through resolve_ui_state_path."""
    workflow_path = _write_workflow(tmp_path / "workflow.yaml", _base_payload())
    ui_state_path = tmp_path / "custom_ui.json"
    backup_root = tmp_path / ".yagra-backups"
    before_session = load_workflow_edit_session(
        workflow_path=workflow_path, ui_state_path=ui_state_path
    )

    candidate_workflow = deepcopy(before_session.workflow)
    candidate_workflow["params"] = {"temperature": 0.5}
    save_result = save_workflow_with_backup(
        workflow_path=workflow_path,
        candidate_workflow=candidate_workflow,
        candidate_ui_state={"custom": True},
        base_revision=before_session.revision,
        backup_dir=backup_root,
        ui_state_path=ui_state_path,
    )

    assert save_result.saved_revision
    assert ui_state_path.exists()
