"""Workflow 編集結果の保存とロールバックを提供する。"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from typing import Any

from yagra.application.services.workflow_file_store import (
    WorkflowBackupNotFoundError,
    WorkflowFileStore,
)
from yagra.application.use_cases.workflow_edit_session import (
    compute_workflow_revision,
    resolve_ui_state_path,
)
from yagra.application.use_cases.workflow_validation_reporter import (
    WorkflowValidationFailedError,
    validate_workflow_payload_for_ui,
)


class WorkflowRevisionConflictError(ValueError):
    """workflow 保存時に revision が競合した場合の例外。"""

    def __init__(self, expected_revision: str, actual_revision: str) -> None:
        """Initializes with conflict information.

        Args:
            expected_revision: クライアントが想定した revision。
            actual_revision: 現在の revision。
        """
        self.expected_revision = expected_revision
        self.actual_revision = actual_revision
        super().__init__(
            f"workflow revision conflict: expected={expected_revision}, actual={actual_revision}"
        )


@dataclass(frozen=True, slots=True)
class WorkflowSaveResult:
    """workflow 保存結果を保持する。"""

    saved_revision: str
    backup_id: str


@dataclass(frozen=True, slots=True)
class WorkflowRollbackResult:
    """workflow ロールバック結果を保持する。"""

    restored_revision: str
    backup_id: str
    safety_backup_id: str


def save_workflow_with_backup(
    workflow_path: str | PathLike[str],
    candidate_workflow: Mapping[str, Any],
    candidate_ui_state: Mapping[str, Any],
    base_revision: str,
    bundle_root: str | PathLike[str] | None = None,
    ui_state_path: str | PathLike[str] | None = None,
    backup_dir: str | PathLike[str] = ".yagra/backups",
) -> WorkflowSaveResult:
    """Workflow 編集案を検証し、バックアップ付きで保存する。

    Args:
        workflow_path: 保存対象 workflow パス。
        candidate_workflow: 保存候補 workflow データ。
        candidate_ui_state: 保存候補 UI サイドカーデータ。
        base_revision: 保存要求の基準 revision。
        bundle_root: 分割参照解決の基準ディレクトリ。
        ui_state_path: 保存対象 UI サイドカーパス。
        backup_dir: バックアップ格納ルートディレクトリ。

    Returns:
        保存結果を表す `WorkflowSaveResult`。

    Raises:
        ValueError: 入力データが辞書形式でない場合。
        WorkflowRevisionConflictError: revision が一致しない場合。
        WorkflowValidationFailedError: 保存候補の検証に失敗した場合。
    """
    workflow_abspath = Path(workflow_path).expanduser().resolve()
    ui_state_abspath = resolve_ui_state_path(
        workflow_path=workflow_abspath,
        ui_state_path=ui_state_path,
    )
    store = WorkflowFileStore(backup_root=backup_dir)

    current_workflow = store.load_workflow(workflow_abspath)
    current_ui_state = store.load_ui_state(ui_state_abspath)
    current_revision = compute_workflow_revision(current_workflow, current_ui_state)
    if current_revision != base_revision:
        raise WorkflowRevisionConflictError(
            expected_revision=base_revision,
            actual_revision=current_revision,
        )

    candidate_workflow_payload = _ensure_mapping(
        candidate_workflow,
        label="candidate workflow",
    )
    candidate_ui_state_payload = _ensure_mapping(
        candidate_ui_state,
        label="candidate ui_state",
    )
    validation_report = validate_workflow_payload_for_ui(
        payload=deepcopy(candidate_workflow_payload),
        workflow_path=workflow_abspath,
        bundle_root=bundle_root,
    )
    if not validation_report.is_valid:
        raise WorkflowValidationFailedError(validation_report)

    backup_record = store.create_backup(
        workflow_path=workflow_abspath,
        ui_state_path=ui_state_abspath,
        workflow_payload=current_workflow,
        ui_state_payload=current_ui_state,
    )

    try:
        store.write_workflow_atomic(workflow_abspath, candidate_workflow_payload)
        store.write_ui_state_atomic(ui_state_abspath, candidate_ui_state_payload)
    except Exception:
        store.restore_backup(
            workflow_path=workflow_abspath,
            ui_state_path=ui_state_abspath,
            backup_id=backup_record.backup_id,
        )
        raise

    saved_revision = compute_workflow_revision(
        candidate_workflow_payload, candidate_ui_state_payload
    )
    return WorkflowSaveResult(saved_revision=saved_revision, backup_id=backup_record.backup_id)


def rollback_workflow_from_backup(
    workflow_path: str | PathLike[str],
    backup_id: str,
    ui_state_path: str | PathLike[str] | None = None,
    backup_dir: str | PathLike[str] = ".yagra/backups",
) -> WorkflowRollbackResult:
    """Restores workflow from the specified backup.

    Args:
        workflow_path: 復元対象 workflow パス。
        backup_id: 復元対象バックアップID。
        ui_state_path: 復元対象 UI サイドカーパス。
        backup_dir: バックアップ格納ルートディレクトリ。

    Returns:
        復元結果を表す `WorkflowRollbackResult`。

    Raises:
        WorkflowBackupNotFoundError: バックアップが存在しない場合。
    """
    workflow_abspath = Path(workflow_path).expanduser().resolve()
    ui_state_abspath = resolve_ui_state_path(
        workflow_path=workflow_abspath,
        ui_state_path=ui_state_path,
    )
    store = WorkflowFileStore(backup_root=backup_dir)
    if not store.backup_exists(workflow_path=workflow_abspath, backup_id=backup_id):
        raise WorkflowBackupNotFoundError(f"backup not found: {backup_id}")

    current_workflow = store.load_workflow(workflow_abspath)
    current_ui_state = store.load_ui_state(ui_state_abspath)
    safety_backup_record = store.create_backup(
        workflow_path=workflow_abspath,
        ui_state_path=ui_state_abspath,
        workflow_payload=current_workflow,
        ui_state_payload=current_ui_state,
    )
    try:
        store.restore_backup(
            workflow_path=workflow_abspath,
            ui_state_path=ui_state_abspath,
            backup_id=backup_id,
        )
    except Exception:
        store.restore_backup(
            workflow_path=workflow_abspath,
            ui_state_path=ui_state_abspath,
            backup_id=safety_backup_record.backup_id,
        )
        raise

    restored_workflow = store.load_workflow(workflow_abspath)
    restored_ui_state = store.load_ui_state(ui_state_abspath)
    restored_revision = compute_workflow_revision(restored_workflow, restored_ui_state)
    return WorkflowRollbackResult(
        restored_revision=restored_revision,
        backup_id=backup_id,
        safety_backup_id=safety_backup_record.backup_id,
    )


__all__ = [
    "WorkflowBackupNotFoundError",
    "WorkflowRevisionConflictError",
    "WorkflowRollbackResult",
    "WorkflowSaveResult",
    "rollback_workflow_from_backup",
    "save_workflow_with_backup",
]


def _ensure_mapping(payload: Mapping[str, Any], label: str) -> dict[str, Any]:
    """Validates that the input is dict-compatible and converts it to a dict.

    Args:
        payload: 検証対象データ。
        label: エラー文言で使う入力名。

    Returns:
        shallow copy した辞書データ。

    Raises:
        ValueError: payload が辞書互換でない場合。
    """
    if not isinstance(payload, Mapping):
        raise ValueError(f"{label} must be a mapping")
    return dict(payload)
