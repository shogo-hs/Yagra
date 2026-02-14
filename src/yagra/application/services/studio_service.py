"""Workflow Studio の入力境界実装を提供する。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import Any

from yagra.application.services.workflow_file_store import (
    WorkflowBackupNotFoundError,
    WorkflowFileStore,
)
from yagra.application.use_cases.workflow_edit_session import (
    WorkflowChange,
    WorkflowDiffResult,
    build_workflow_diff,
    load_workflow_edit_session,
)
from yagra.application.use_cases.workflow_form_model import (
    WorkflowCatalogPreview,
    WorkflowEdgeFormItem,
    WorkflowFormView,
    WorkflowNodeFormItem,
    build_workflow_catalog_preview,
    build_workflow_form_view,
)
from yagra.application.use_cases.workflow_form_patcher import apply_form_edits
from yagra.application.use_cases.workflow_persistence import (
    WorkflowRevisionConflictError,
    rollback_workflow_from_backup,
    save_workflow_with_backup,
)
from yagra.application.use_cases.workflow_validation_reporter import (
    WorkflowValidationFailedError,
    WorkflowValidationReport,
)
from yagra.ports.inbound import (
    StudioBadRequestError,
    StudioConflictError,
    StudioNotFoundError,
    StudioPort,
    StudioUnprocessableEntityError,
)

_WORKFLOW_EXTENSIONS = {".yaml", ".yml"}


@dataclass(slots=True)
class StudioSessionConfig:
    """Studio サービスの可変セッション設定。"""

    workflow_path: Path | None
    bundle_root: Path | None
    ui_state_path: Path | None
    ui_state_override: Path | None
    workspace_root: Path
    backup_dir: Path
    lock: Lock = field(default_factory=Lock)


def _resolve_workflow_path_in_workspace(raw_path: str, workspace_root: Path) -> Path:
    """ワークスペース内の workflow パスを絶対パスへ解決する。"""
    text = raw_path.strip()
    if not text:
        raise ValueError("workflow_path must be a non-empty string")
    source = Path(text).expanduser()
    candidate = source.resolve() if source.is_absolute() else (workspace_root / source).resolve()
    try:
        candidate.relative_to(workspace_root)
    except ValueError as exc:
        raise ValueError("workflow_path must be inside workspace_root") from exc

    if candidate.suffix.lower() not in _WORKFLOW_EXTENSIONS:
        raise ValueError("workflow_path must end with .yaml or .yml")
    return candidate


def _resolve_ui_state_for_target(workflow_path: Path, ui_state_override: Path | None) -> Path:
    """対象 workflow に対応する UI サイドカーパスを返す。"""
    if ui_state_override is not None:
        return ui_state_override
    return workflow_path.with_suffix(".workflow-ui.json")


def _list_workflow_candidates(workspace_root: Path) -> list[str]:
    """ワークスペース配下の workflow 候補一覧を返す。"""
    candidates: list[str] = []
    for path in sorted(workspace_root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in _WORKFLOW_EXTENSIONS:
            continue
        candidates.append(path.relative_to(workspace_root).as_posix())
    return candidates


def _build_initial_workflow_payload() -> dict[str, Any]:
    """新規作成時に使う最小 workflow payload を返す。"""
    return {
        "version": "1.0",
        "start_at": "start",
        "end_at": ["end"],
        "nodes": [
            {"id": "start", "handler": "start_handler"},
            {"id": "end", "handler": "end_handler"},
        ],
        "edges": [{"source": "start", "target": "end"}],
        "params": {},
    }


class StudioService(StudioPort):
    """Workflow Studio API が利用するアプリケーションサービス。"""

    def __init__(self, config: StudioSessionConfig) -> None:
        """サービスを初期化する。

        Args:
            config: Studio セッションの状態を保持する設定。
        """
        self._config = config

    def get_studio_target(self) -> dict[str, Any]:
        """Studio の現在ターゲット情報を返す。"""
        with self._config.lock:
            target_paths = self._active_target_paths()
            workflow_path = str(target_paths[0]) if target_paths is not None else None
            ui_state_path = str(target_paths[1]) if target_paths is not None else None
            workspace_root = str(self._config.workspace_root)
        return {
            "has_target": target_paths is not None,
            "workflow_path": workflow_path,
            "ui_state_path": ui_state_path,
            "workspace_root": workspace_root,
        }

    def get_studio_files(self) -> dict[str, Any]:
        """ワークスペース配下の workflow 候補一覧を返す。"""
        with self._config.lock:
            workspace_root = self._config.workspace_root
            workflows = _list_workflow_candidates(workspace_root)
        return {
            "workspace_root": str(workspace_root),
            "workflows": workflows,
        }

    def open_studio_target(self, body: dict[str, Any]) -> dict[str, Any]:
        """既存 workflow を Studio 編集対象として開く。"""
        workflow_path_raw = body.get("workflow_path")
        if not isinstance(workflow_path_raw, str):
            raise StudioBadRequestError(error="workflow_path must be a string")

        with self._config.lock:
            try:
                workflow_path = _resolve_workflow_path_in_workspace(
                    raw_path=workflow_path_raw,
                    workspace_root=self._config.workspace_root,
                )
            except ValueError as exc:
                raise StudioBadRequestError(
                    error="invalid_workflow_path",
                    message=str(exc),
                ) from exc

            if not workflow_path.exists() or not workflow_path.is_file():
                raise StudioNotFoundError(
                    error="workflow_not_found",
                    message=f"workflow not found: {workflow_path}",
                )

            ui_state_path = _resolve_ui_state_for_target(
                workflow_path=workflow_path,
                ui_state_override=self._config.ui_state_override,
            )
            self._config.workflow_path = workflow_path
            self._config.ui_state_path = ui_state_path

        return {
            "workflow_path": str(workflow_path),
            "ui_state_path": str(ui_state_path),
        }

    def create_studio_target(self, body: dict[str, Any]) -> dict[str, Any]:
        """新規 workflow を作成して Studio 編集対象として開く。"""
        workflow_path_raw = body.get("workflow_path")
        overwrite = body.get("overwrite", False)
        if not isinstance(workflow_path_raw, str):
            raise StudioBadRequestError(error="workflow_path must be a string")
        if not isinstance(overwrite, bool):
            raise StudioBadRequestError(error="overwrite must be a boolean")

        with self._config.lock:
            try:
                workflow_path = _resolve_workflow_path_in_workspace(
                    raw_path=workflow_path_raw,
                    workspace_root=self._config.workspace_root,
                )
            except ValueError as exc:
                raise StudioBadRequestError(
                    error="invalid_workflow_path",
                    message=str(exc),
                ) from exc

            if workflow_path.exists() and not overwrite:
                raise StudioConflictError(
                    error="workflow_exists",
                    message=f"workflow already exists: {workflow_path}",
                )
            if workflow_path.exists() and not workflow_path.is_file():
                raise StudioBadRequestError(
                    error="invalid_workflow_path",
                    message=f"workflow_path is not a file: {workflow_path}",
                )

            ui_state_path = _resolve_ui_state_for_target(
                workflow_path=workflow_path,
                ui_state_override=self._config.ui_state_override,
            )
            store = WorkflowFileStore(backup_root=self._config.backup_dir)
            store.write_workflow_atomic(
                workflow_path=workflow_path,
                payload=_build_initial_workflow_payload(),
            )
            store.write_ui_state_atomic(ui_state_path=ui_state_path, payload={})
            self._config.workflow_path = workflow_path
            self._config.ui_state_path = ui_state_path

        return {
            "workflow_path": str(workflow_path),
            "ui_state_path": str(ui_state_path),
        }

    def get_workflow(self) -> dict[str, Any]:
        """現在の workflow を返す。"""
        with self._config.lock:
            workflow_path, ui_state_path = self._require_active_target_paths()
            try:
                session = load_workflow_edit_session(
                    workflow_path=workflow_path,
                    bundle_root=self._config.bundle_root,
                    ui_state_path=ui_state_path,
                )
            except ValueError as exc:
                raise StudioUnprocessableEntityError(
                    error="load_failed",
                    message=str(exc),
                ) from exc

        return {
            "workflow": session.workflow,
            "ui_state": session.ui_state,
            "revision": session.revision,
            "validation_report": _validation_report_to_dict(session.validation_report),
        }

    def get_form(self) -> dict[str, Any]:
        """フォーム編集向けの workflow 表示情報を返す。"""
        with self._config.lock:
            workflow_path, ui_state_path = self._require_active_target_paths()
            try:
                session = load_workflow_edit_session(
                    workflow_path=workflow_path,
                    bundle_root=self._config.bundle_root,
                    ui_state_path=ui_state_path,
                )
                form_view = build_workflow_form_view(
                    workflow=session.workflow,
                    ui_state=session.ui_state,
                    workflow_path=workflow_path,
                    bundle_root=self._config.bundle_root,
                )
                catalog_preview = build_workflow_catalog_preview(
                    workflow=session.workflow,
                    workflow_path=workflow_path,
                    bundle_root=self._config.bundle_root,
                )
            except ValueError as exc:
                raise StudioUnprocessableEntityError(
                    error="load_failed",
                    message=str(exc),
                ) from exc

        payload = _form_view_to_dict(form_view)
        payload["workflow"] = session.workflow
        payload["ui_state"] = session.ui_state
        payload["catalog_preview"] = _catalog_preview_to_dict(catalog_preview)
        payload["validation_report"] = _validation_report_to_dict(session.validation_report)
        return payload

    def diff(self, body: dict[str, Any]) -> dict[str, Any]:
        """編集案の差分を返す。"""
        candidate_workflow = body.get("workflow")
        candidate_ui_state = body.get("ui_state", {})
        base_revision = body.get("base_revision")
        if not isinstance(base_revision, str):
            raise StudioBadRequestError(error="base_revision must be a string")
        if not isinstance(candidate_workflow, dict):
            raise StudioBadRequestError(error="workflow must be a mapping")
        if not isinstance(candidate_ui_state, dict):
            raise StudioBadRequestError(error="ui_state must be a mapping")

        with self._config.lock:
            workflow_path, ui_state_path = self._require_active_target_paths()
            try:
                session = load_workflow_edit_session(
                    workflow_path=workflow_path,
                    bundle_root=self._config.bundle_root,
                    ui_state_path=ui_state_path,
                )
            except ValueError as exc:
                raise StudioUnprocessableEntityError(
                    error="load_failed",
                    message=str(exc),
                ) from exc

            if base_revision != session.revision:
                raise StudioConflictError(
                    error="revision_conflict",
                    details={
                        "expected_revision": base_revision,
                        "actual_revision": session.revision,
                    },
                )

            try:
                diff_result = build_workflow_diff(
                    base_workflow=session.workflow,
                    candidate_workflow=candidate_workflow,
                    base_ui_state=session.ui_state,
                    candidate_ui_state=candidate_ui_state,
                    workflow_path=workflow_path,
                    bundle_root=self._config.bundle_root,
                )
            except ValueError as exc:
                raise StudioBadRequestError(
                    error="invalid_payload",
                    message=str(exc),
                ) from exc

        return _diff_result_to_dict(diff_result)

    def form_preview(self, body: dict[str, Any]) -> dict[str, Any]:
        """フォーム編集入力から差分プレビューを返す。"""
        base_revision = body.get("base_revision")
        node_creates = body.get("node_creates")
        node_edits = body.get("node_edits")
        edge_creates = body.get("edge_creates")
        edge_rewires = body.get("edge_rewires")
        edge_edits = body.get("edge_edits")
        candidate_ui_state = body.get("ui_state")
        if not isinstance(base_revision, str):
            raise StudioBadRequestError(error="base_revision must be a string")
        if not isinstance(node_creates, list):
            raise StudioBadRequestError(error="node_creates must be an array")
        if not isinstance(node_edits, list):
            raise StudioBadRequestError(error="node_edits must be an array")
        if not isinstance(edge_creates, list):
            raise StudioBadRequestError(error="edge_creates must be an array")
        if not isinstance(edge_rewires, list):
            raise StudioBadRequestError(error="edge_rewires must be an array")
        if not isinstance(edge_edits, list):
            raise StudioBadRequestError(error="edge_edits must be an array")
        if not isinstance(candidate_ui_state, dict):
            raise StudioBadRequestError(error="ui_state must be a mapping")

        with self._config.lock:
            workflow_path, ui_state_path = self._require_active_target_paths()
            try:
                session = load_workflow_edit_session(
                    workflow_path=workflow_path,
                    bundle_root=self._config.bundle_root,
                    ui_state_path=ui_state_path,
                )
            except ValueError as exc:
                raise StudioUnprocessableEntityError(
                    error="load_failed",
                    message=str(exc),
                ) from exc

            if base_revision != session.revision:
                raise StudioConflictError(
                    error="revision_conflict",
                    details={
                        "expected_revision": base_revision,
                        "actual_revision": session.revision,
                    },
                )

            try:
                candidate_workflow = apply_form_edits(
                    workflow=session.workflow,
                    node_creates=node_creates,
                    node_edits=node_edits,
                    edge_creates=edge_creates,
                    edge_rewires=edge_rewires,
                    edge_edits=edge_edits,
                )
                diff_result = build_workflow_diff(
                    base_workflow=session.workflow,
                    candidate_workflow=candidate_workflow,
                    base_ui_state=session.ui_state,
                    candidate_ui_state=candidate_ui_state,
                    workflow_path=workflow_path,
                    bundle_root=self._config.bundle_root,
                )
            except ValueError as exc:
                raise StudioBadRequestError(
                    error="invalid_payload",
                    message=str(exc),
                ) from exc

        response_payload = _diff_result_to_dict(diff_result)
        response_payload["candidate_workflow"] = candidate_workflow
        response_payload["candidate_ui_state"] = candidate_ui_state
        return response_payload

    def catalog_preview(self, body: dict[str, Any]) -> dict[str, Any]:
        """Workflow の catalog 設定プレビューを返す。"""
        candidate_workflow = body.get("workflow")
        if not isinstance(candidate_workflow, dict):
            raise StudioBadRequestError(error="workflow must be a mapping")

        with self._config.lock:
            workflow_path, _ = self._require_active_target_paths()
            try:
                catalog_preview = build_workflow_catalog_preview(
                    workflow=candidate_workflow,
                    workflow_path=workflow_path,
                    bundle_root=self._config.bundle_root,
                )
            except ValueError as exc:
                raise StudioBadRequestError(
                    error="invalid_payload",
                    message=str(exc),
                ) from exc

        return _catalog_preview_to_dict(catalog_preview)

    def save(self, body: dict[str, Any]) -> dict[str, Any]:
        """編集案を保存する。"""
        candidate_workflow = body.get("workflow")
        candidate_ui_state = body.get("ui_state", {})
        base_revision = body.get("base_revision")
        if not isinstance(base_revision, str):
            raise StudioBadRequestError(error="base_revision must be a string")
        if not isinstance(candidate_workflow, dict):
            raise StudioBadRequestError(error="workflow must be a mapping")
        if not isinstance(candidate_ui_state, dict):
            raise StudioBadRequestError(error="ui_state must be a mapping")

        with self._config.lock:
            workflow_path, ui_state_path = self._require_active_target_paths()
            try:
                result = save_workflow_with_backup(
                    workflow_path=workflow_path,
                    candidate_workflow=candidate_workflow,
                    candidate_ui_state=candidate_ui_state,
                    base_revision=base_revision,
                    bundle_root=self._config.bundle_root,
                    ui_state_path=ui_state_path,
                    backup_dir=self._config.backup_dir,
                )
            except WorkflowRevisionConflictError as exc:
                raise StudioConflictError(
                    error="revision_conflict",
                    details={
                        "expected_revision": exc.expected_revision,
                        "actual_revision": exc.actual_revision,
                    },
                ) from exc
            except WorkflowValidationFailedError as exc:
                raise StudioUnprocessableEntityError(
                    error="validation_failed",
                    details={"report": _validation_report_to_dict(exc.report)},
                ) from exc
            except ValueError as exc:
                raise StudioBadRequestError(
                    error="invalid_payload",
                    message=str(exc),
                ) from exc

        return {
            "saved_revision": result.saved_revision,
            "backup_id": result.backup_id,
        }

    def rollback(self, body: dict[str, Any]) -> dict[str, Any]:
        """バックアップ ID を指定して復元する。"""
        backup_id = body.get("backup_id")
        if not isinstance(backup_id, str) or not backup_id.strip():
            raise StudioBadRequestError(error="backup_id must be a non-empty string")

        with self._config.lock:
            workflow_path, ui_state_path = self._require_active_target_paths()
            try:
                result = rollback_workflow_from_backup(
                    workflow_path=workflow_path,
                    ui_state_path=ui_state_path,
                    backup_dir=self._config.backup_dir,
                    backup_id=backup_id,
                )
            except WorkflowBackupNotFoundError as exc:
                raise StudioNotFoundError(
                    error="backup_not_found",
                    message=str(exc),
                ) from exc

        return {
            "restored_revision": result.restored_revision,
            "backup_id": result.backup_id,
            "safety_backup_id": result.safety_backup_id,
        }

    def _active_target_paths(self) -> tuple[Path, Path] | None:
        """現在選択中の workflow/ui_state パスを返す。未選択時は `None`。"""
        workflow_path = self._config.workflow_path
        ui_state_path = self._config.ui_state_path
        if workflow_path is None or ui_state_path is None:
            return None
        return workflow_path, ui_state_path

    def _require_active_target_paths(self) -> tuple[Path, Path]:
        """現在選択中ターゲットを必須取得する。未選択時はエラーを送出する。"""
        target_paths = self._active_target_paths()
        if target_paths is not None:
            return target_paths
        raise StudioConflictError(
            error="studio_target_required",
            message="workflow target is not selected",
        )


def _diff_result_to_dict(result: WorkflowDiffResult) -> dict[str, Any]:
    """差分結果を API 応答形式へ変換する。"""
    return {
        "base_revision": result.base_revision,
        "candidate_revision": result.candidate_revision,
        "summary": result.summary,
        "changes": [_change_to_dict(change) for change in result.changes],
        "yaml_unified_diff": result.yaml_unified_diff,
        "validation_report": _validation_report_to_dict(result.validation_report),
    }


def _form_view_to_dict(view: WorkflowFormView) -> dict[str, Any]:
    """フォーム表示モデルを API 応答形式へ変換する。"""
    return {
        "revision": view.revision,
        "nodes": [_node_form_item_to_dict(node) for node in view.nodes],
        "edges": [_edge_form_item_to_dict(edge) for edge in view.edges],
        "prompt_catalog_keys": list(view.prompt_catalog_keys),
        "model_catalog_keys": list(view.model_catalog_keys),
    }


def _node_form_item_to_dict(item: WorkflowNodeFormItem) -> dict[str, Any]:
    """ノードフォーム項目を API 応答形式へ変換する。"""
    return {
        "id": item.id,
        "handler": item.handler,
        "prompt_ref": item.prompt_ref,
        "model_ref": item.model_ref,
        "prompt": item.prompt,
        "model": item.model,
    }


def _edge_form_item_to_dict(item: WorkflowEdgeFormItem) -> dict[str, Any]:
    """エッジフォーム項目を API 応答形式へ変換する。"""
    return {
        "index": item.index,
        "source": item.source,
        "target": item.target,
        "condition": item.condition,
    }


def _change_to_dict(change: WorkflowChange) -> dict[str, Any]:
    """変更イベントを API 応答形式へ変換する。"""
    return {
        "kind": change.kind,
        "path": list(change.path),
        "before": change.before,
        "after": change.after,
    }


def _validation_report_to_dict(report: WorkflowValidationReport) -> dict[str, Any]:
    """検証レポートを API 応答形式へ変換する。"""
    return {
        "is_valid": report.is_valid,
        "issues": [
            {"code": issue.code, "message": issue.message, "location": list(issue.location)}
            for issue in report.issues
        ],
    }


def _catalog_preview_to_dict(preview: WorkflowCatalogPreview) -> dict[str, Any]:
    """Catalog プレビュー結果を API 応答形式へ変換する。"""
    return {
        "prompt_catalog_path": preview.prompt_catalog_path,
        "model_catalog_path": preview.model_catalog_path,
        "prompt_catalog_keys": list(preview.prompt_catalog_keys),
        "model_catalog_keys": list(preview.model_catalog_keys),
        "issues": [
            {"code": issue.code, "message": issue.message, "location": list(issue.location)}
            for issue in preview.issues
        ],
    }
