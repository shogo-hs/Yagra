"""Workflow Studio 用のローカル HTTP サーバーを提供する。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from os import PathLike
from pathlib import Path
from threading import Lock
from typing import Any
from urllib.parse import urlparse

from yagra.application.services.workflow_file_store import WorkflowBackupNotFoundError
from yagra.application.use_cases.workflow_edit_session import (
    WorkflowChange,
    WorkflowDiffResult,
    build_workflow_diff,
    load_workflow_edit_session,
)
from yagra.application.use_cases.workflow_form_model import (
    WorkflowEdgeFormItem,
    WorkflowFormView,
    WorkflowNodeFormItem,
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


@dataclass(slots=True)
class WorkflowStudioServerConfig:
    """Workflow Studio サーバー構成を保持する。"""

    workflow_path: Path
    bundle_root: Path | None
    ui_state_path: Path
    backup_dir: Path
    lock: Lock = field(default_factory=Lock)


def create_workflow_studio_server(
    workflow_path: str | PathLike[str],
    bundle_root: str | PathLike[str] | None = None,
    ui_state_path: str | PathLike[str] | None = None,
    backup_dir: str | PathLike[str] = ".yagra/backups",
    host: str = "127.0.0.1",
    port: int = 8787,
) -> ThreadingHTTPServer:
    """Workflow Studio ローカルサーバーを生成する。

    Args:
        workflow_path: 編集対象 workflow パス。
        bundle_root: 分割参照解決の基準ディレクトリ。
        ui_state_path: UI サイドカーパス。
        backup_dir: バックアップ格納ディレクトリ。
        host: バインドホスト。
        port: バインドポート。

    Returns:
        設定済み `ThreadingHTTPServer`。
    """
    workflow_abspath = Path(workflow_path).expanduser().resolve()
    bundle_root_path = Path(bundle_root).expanduser().resolve() if bundle_root is not None else None
    ui_state_abspath = (
        Path(ui_state_path).expanduser().resolve()
        if ui_state_path is not None
        else workflow_abspath.with_suffix(".workflow-ui.json")
    )
    backup_dir_path = Path(backup_dir).expanduser().resolve()

    config = WorkflowStudioServerConfig(
        workflow_path=workflow_abspath,
        bundle_root=bundle_root_path,
        ui_state_path=ui_state_abspath,
        backup_dir=backup_dir_path,
    )
    handler_class = _build_handler_class(config)
    return ThreadingHTTPServer((host, port), handler_class)


def _build_handler_class(
    config: WorkflowStudioServerConfig,
) -> type[BaseHTTPRequestHandler]:
    """設定を閉じ込めた HTTP Handler クラスを生成する。

    Args:
        config: サーバー設定。

    Returns:
        `BaseHTTPRequestHandler` 派生クラス。
    """

    class WorkflowStudioHandler(BaseHTTPRequestHandler):
        """Workflow Studio API のリクエストを処理する。"""

        _config = config

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
            """標準出力ログを抑制する。"""
            _ = (format, args)

        def do_GET(self) -> None:  # noqa: N802
            """GET リクエストを処理する。"""
            path = urlparse(self.path).path
            if path == "/":
                self._write_html(_studio_html())
                return
            if path == "/api/workflow/form":
                self._handle_get_form()
                return
            if path == "/api/workflow":
                self._handle_get_workflow()
                return
            self._write_json(404, {"error": "not_found"})

        def do_POST(self) -> None:  # noqa: N802
            """POST リクエストを処理する。"""
            path = urlparse(self.path).path
            try:
                body = self._read_json_body()
            except ValueError as exc:
                self._write_json(400, {"error": "invalid_json", "message": str(exc)})
                return

            if path == "/api/workflow/diff":
                self._handle_diff(body)
                return
            if path == "/api/workflow/form/preview":
                self._handle_form_preview(body)
                return
            if path == "/api/workflow/save":
                self._handle_save(body)
                return
            if path == "/api/workflow/rollback":
                self._handle_rollback(body)
                return

            self._write_json(404, {"error": "not_found"})

        def _handle_get_workflow(self) -> None:
            """現在の workflow を返す。"""
            with self._config.lock:
                try:
                    session = load_workflow_edit_session(
                        workflow_path=self._config.workflow_path,
                        bundle_root=self._config.bundle_root,
                        ui_state_path=self._config.ui_state_path,
                    )
                except ValueError as exc:
                    self._write_json(422, {"error": "load_failed", "message": str(exc)})
                    return

            self._write_json(
                200,
                {
                    "workflow": session.workflow,
                    "ui_state": session.ui_state,
                    "revision": session.revision,
                    "validation_report": _validation_report_to_dict(session.validation_report),
                },
            )

        def _handle_get_form(self) -> None:
            """フォーム編集向けの workflow 表示情報を返す。"""
            with self._config.lock:
                try:
                    session = load_workflow_edit_session(
                        workflow_path=self._config.workflow_path,
                        bundle_root=self._config.bundle_root,
                        ui_state_path=self._config.ui_state_path,
                    )
                    form_view = build_workflow_form_view(
                        workflow=session.workflow,
                        ui_state=session.ui_state,
                        workflow_path=self._config.workflow_path,
                        bundle_root=self._config.bundle_root,
                    )
                except ValueError as exc:
                    self._write_json(422, {"error": "load_failed", "message": str(exc)})
                    return

            payload = _form_view_to_dict(form_view)
            payload["workflow"] = session.workflow
            payload["ui_state"] = session.ui_state
            payload["validation_report"] = _validation_report_to_dict(session.validation_report)
            self._write_json(200, payload)

        def _handle_diff(self, body: dict[str, Any]) -> None:
            """編集案の差分を返す。"""
            candidate_workflow = body.get("workflow")
            candidate_ui_state = body.get("ui_state", {})
            base_revision = body.get("base_revision")
            if not isinstance(base_revision, str):
                self._write_json(400, {"error": "base_revision must be a string"})
                return
            if not isinstance(candidate_workflow, dict):
                self._write_json(400, {"error": "workflow must be a mapping"})
                return
            if not isinstance(candidate_ui_state, dict):
                self._write_json(400, {"error": "ui_state must be a mapping"})
                return

            with self._config.lock:
                try:
                    session = load_workflow_edit_session(
                        workflow_path=self._config.workflow_path,
                        bundle_root=self._config.bundle_root,
                        ui_state_path=self._config.ui_state_path,
                    )
                except ValueError as exc:
                    self._write_json(422, {"error": "load_failed", "message": str(exc)})
                    return

                if base_revision != session.revision:
                    self._write_json(
                        409,
                        {
                            "error": "revision_conflict",
                            "expected_revision": base_revision,
                            "actual_revision": session.revision,
                        },
                    )
                    return

                try:
                    diff_result = build_workflow_diff(
                        base_workflow=session.workflow,
                        candidate_workflow=candidate_workflow,
                        base_ui_state=session.ui_state,
                        candidate_ui_state=candidate_ui_state,
                        workflow_path=self._config.workflow_path,
                        bundle_root=self._config.bundle_root,
                    )
                except ValueError as exc:
                    self._write_json(400, {"error": "invalid_payload", "message": str(exc)})
                    return

            self._write_json(200, _diff_result_to_dict(diff_result))

        def _handle_form_preview(self, body: dict[str, Any]) -> None:
            """フォーム編集入力から差分プレビューを返す。"""
            base_revision = body.get("base_revision")
            node_creates = body.get("node_creates")
            node_edits = body.get("node_edits")
            edge_creates = body.get("edge_creates")
            edge_rewires = body.get("edge_rewires")
            edge_edits = body.get("edge_edits")
            candidate_ui_state = body.get("ui_state")
            if not isinstance(base_revision, str):
                self._write_json(400, {"error": "base_revision must be a string"})
                return
            if not isinstance(node_creates, list):
                self._write_json(400, {"error": "node_creates must be an array"})
                return
            if not isinstance(node_edits, list):
                self._write_json(400, {"error": "node_edits must be an array"})
                return
            if not isinstance(edge_creates, list):
                self._write_json(400, {"error": "edge_creates must be an array"})
                return
            if not isinstance(edge_rewires, list):
                self._write_json(400, {"error": "edge_rewires must be an array"})
                return
            if not isinstance(edge_edits, list):
                self._write_json(400, {"error": "edge_edits must be an array"})
                return
            if not isinstance(candidate_ui_state, dict):
                self._write_json(400, {"error": "ui_state must be a mapping"})
                return

            with self._config.lock:
                try:
                    session = load_workflow_edit_session(
                        workflow_path=self._config.workflow_path,
                        bundle_root=self._config.bundle_root,
                        ui_state_path=self._config.ui_state_path,
                    )
                except ValueError as exc:
                    self._write_json(422, {"error": "load_failed", "message": str(exc)})
                    return

                if base_revision != session.revision:
                    self._write_json(
                        409,
                        {
                            "error": "revision_conflict",
                            "expected_revision": base_revision,
                            "actual_revision": session.revision,
                        },
                    )
                    return

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
                        workflow_path=self._config.workflow_path,
                        bundle_root=self._config.bundle_root,
                    )
                except ValueError as exc:
                    self._write_json(400, {"error": "invalid_payload", "message": str(exc)})
                    return

            response_payload = _diff_result_to_dict(diff_result)
            response_payload["candidate_workflow"] = candidate_workflow
            response_payload["candidate_ui_state"] = candidate_ui_state
            self._write_json(200, response_payload)

        def _handle_save(self, body: dict[str, Any]) -> None:
            """編集案を保存する。"""
            candidate_workflow = body.get("workflow")
            candidate_ui_state = body.get("ui_state", {})
            base_revision = body.get("base_revision")
            if not isinstance(base_revision, str):
                self._write_json(400, {"error": "base_revision must be a string"})
                return
            if not isinstance(candidate_workflow, dict):
                self._write_json(400, {"error": "workflow must be a mapping"})
                return
            if not isinstance(candidate_ui_state, dict):
                self._write_json(400, {"error": "ui_state must be a mapping"})
                return

            with self._config.lock:
                try:
                    result = save_workflow_with_backup(
                        workflow_path=self._config.workflow_path,
                        candidate_workflow=candidate_workflow,
                        candidate_ui_state=candidate_ui_state,
                        base_revision=base_revision,
                        bundle_root=self._config.bundle_root,
                        ui_state_path=self._config.ui_state_path,
                        backup_dir=self._config.backup_dir,
                    )
                except WorkflowRevisionConflictError as exc:
                    self._write_json(
                        409,
                        {
                            "error": "revision_conflict",
                            "expected_revision": exc.expected_revision,
                            "actual_revision": exc.actual_revision,
                        },
                    )
                    return
                except WorkflowValidationFailedError as exc:
                    self._write_json(
                        422,
                        {
                            "error": "validation_failed",
                            "report": _validation_report_to_dict(exc.report),
                        },
                    )
                    return
                except ValueError as exc:
                    self._write_json(400, {"error": "invalid_payload", "message": str(exc)})
                    return

            self._write_json(
                200,
                {
                    "saved_revision": result.saved_revision,
                    "backup_id": result.backup_id,
                },
            )

        def _handle_rollback(self, body: dict[str, Any]) -> None:
            """バックアップIDを指定して復元する。"""
            backup_id = body.get("backup_id")
            if not isinstance(backup_id, str) or not backup_id.strip():
                self._write_json(400, {"error": "backup_id must be a non-empty string"})
                return

            with self._config.lock:
                try:
                    result = rollback_workflow_from_backup(
                        workflow_path=self._config.workflow_path,
                        ui_state_path=self._config.ui_state_path,
                        backup_dir=self._config.backup_dir,
                        backup_id=backup_id,
                    )
                except WorkflowBackupNotFoundError as exc:
                    self._write_json(404, {"error": "backup_not_found", "message": str(exc)})
                    return

            self._write_json(
                200,
                {
                    "restored_revision": result.restored_revision,
                    "backup_id": result.backup_id,
                },
            )

        def _read_json_body(self) -> dict[str, Any]:
            """リクエストボディを JSON 辞書として読み込む。"""
            raw_length = self.headers.get("Content-Length")
            if raw_length is None:
                return {}
            try:
                body_size = int(raw_length)
            except ValueError as exc:
                raise ValueError("invalid Content-Length") from exc

            payload = self.rfile.read(body_size)
            if not payload:
                return {}

            try:
                parsed = json.loads(payload.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError(f"request body is not valid JSON: {exc}") from exc

            if not isinstance(parsed, dict):
                raise ValueError("request body must be a JSON object")
            return parsed

        def _write_json(self, status_code: int, payload: dict[str, Any]) -> None:
            """JSON レスポンスを書き込む。"""
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _write_html(self, html_text: str) -> None:
            """HTML レスポンスを書き込む。"""
            body = html_text.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return WorkflowStudioHandler


def _diff_result_to_dict(result: WorkflowDiffResult) -> dict[str, Any]:
    """差分結果を API 応答形式へ変換する。

    Args:
        result: 変換対象の差分結果。

    Returns:
        JSON 互換辞書。
    """
    return {
        "base_revision": result.base_revision,
        "candidate_revision": result.candidate_revision,
        "summary": result.summary,
        "changes": [_change_to_dict(change) for change in result.changes],
        "yaml_unified_diff": result.yaml_unified_diff,
        "validation_report": _validation_report_to_dict(result.validation_report),
    }


def _form_view_to_dict(view: WorkflowFormView) -> dict[str, Any]:
    """フォーム表示モデルを API 応答形式へ変換する。

    Args:
        view: 変換対象のフォーム表示モデル。

    Returns:
        JSON 互換辞書。
    """
    return {
        "revision": view.revision,
        "nodes": [_node_form_item_to_dict(node) for node in view.nodes],
        "edges": [_edge_form_item_to_dict(edge) for edge in view.edges],
        "prompt_catalog_keys": list(view.prompt_catalog_keys),
        "model_catalog_keys": list(view.model_catalog_keys),
    }


def _node_form_item_to_dict(item: WorkflowNodeFormItem) -> dict[str, Any]:
    """ノードフォーム項目を API 応答形式へ変換する。

    Args:
        item: 変換対象のノードフォーム項目。

    Returns:
        JSON 互換辞書。
    """
    return {
        "id": item.id,
        "handler": item.handler,
        "prompt_ref": item.prompt_ref,
        "model_ref": item.model_ref,
        "prompt": item.prompt,
        "model": item.model,
    }


def _edge_form_item_to_dict(item: WorkflowEdgeFormItem) -> dict[str, Any]:
    """エッジフォーム項目を API 応答形式へ変換する。

    Args:
        item: 変換対象のエッジフォーム項目。

    Returns:
        JSON 互換辞書。
    """
    return {
        "index": item.index,
        "source": item.source,
        "target": item.target,
        "condition": item.condition,
    }


def _change_to_dict(change: WorkflowChange) -> dict[str, Any]:
    """変更イベントを API 応答形式へ変換する。

    Args:
        change: 変換対象の変更イベント。

    Returns:
        JSON 互換辞書。
    """
    return {
        "kind": change.kind,
        "path": list(change.path),
        "before": change.before,
        "after": change.after,
    }


def _validation_report_to_dict(report: WorkflowValidationReport) -> dict[str, Any]:
    """検証レポートを API 応答形式へ変換する。

    Args:
        report: 変換対象の検証レポート。

    Returns:
        JSON 互換辞書。
    """
    return {
        "is_valid": report.is_valid,
        "issues": [
            {"code": issue.code, "message": issue.message, "location": list(issue.location)}
            for issue in report.issues
        ],
    }


def _studio_html() -> str:
    """Workflow Studio のフォーム編集 UI HTML を返す。"""
    return """<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Yagra Workflow Studio</title>
  <style>
    :root {
      --bg: #f3f7fb;
      --panel: #ffffff;
      --line: #d5deea;
      --text: #1d2735;
      --muted: #5d6d84;
      --accent: #0a6fd8;
      --danger: #c62828;
      --ok: #2e7d32;
    }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: "Noto Sans JP", "Hiragino Kaku Gothic ProN", sans-serif; background: var(--bg); color: var(--text); line-height: 1.45; }
    .page { max-width: 1480px; margin: 0 auto; padding: 20px; }
    .header { background: linear-gradient(140deg, #ffffff 10%, #eaf3ff 100%); border: 1px solid var(--line); border-radius: 12px; padding: 16px; }
    h1 { margin: 0 0 8px; font-size: clamp(22px, 3vw, 30px); }
    .muted { color: var(--muted); font-size: 13px; }
    .toolbar { margin-top: 12px; display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
    button { border: 1px solid #0b63be; background: var(--accent); color: #fff; border-radius: 8px; padding: 7px 12px; font-weight: 700; cursor: pointer; }
    button.secondary { background: #fff; color: var(--accent); }
    input[type="text"], select, textarea { border: 1px solid var(--line); border-radius: 8px; padding: 7px 10px; width: 100%; font-size: 13px; background: #fff; color: var(--text); }
    textarea { min-height: 82px; line-height: 1.4; }
    .layout { margin-top: 14px; display: grid; grid-template-columns: 1.1fr 1fr .95fr; gap: 14px; align-items: start; }
    .panel { background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 12px; }
    h2 { margin: 0 0 8px; font-size: 18px; }
    h3 { margin: 0 0 8px; font-size: 15px; }
    pre { width: 100%; min-height: 160px; border: 1px solid var(--line); border-radius: 10px; padding: 10px; font-size: 12px; line-height: 1.45; background: #fff; overflow: auto; white-space: pre-wrap; }
    .danger { color: var(--danger); font-weight: 700; }
    .ok { color: var(--ok); font-weight: 700; }
    .inline-row { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
    .field { margin-bottom: 10px; }
    .field > label { display: block; margin-bottom: 4px; color: var(--muted); font-size: 12px; font-weight: 700; }
    .split { border-top: 1px dashed var(--line); margin: 12px 0; padding-top: 12px; }
    .stack { display: grid; gap: 14px; }
    .raw textarea { min-height: 220px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; }
    .hint { font-size: 12px; color: var(--muted); }
    .graph-canvas { position: relative; width: 100%; min-height: 360px; border: 1px solid var(--line); border-radius: 10px; background: linear-gradient(180deg, #fdfefe 0%, #f3f8ff 100%); overflow: hidden; }
    .graph-edge-layer { position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: auto; }
    .graph-node-layer { position: absolute; inset: 0; pointer-events: none; }
    .graph-node { position: absolute; width: 140px; padding: 8px; border: 1px solid #8da8cb; border-radius: 10px; background: #fff; box-shadow: 0 2px 7px rgba(35, 70, 120, 0.14); cursor: grab; touch-action: none; user-select: none; }
    .graph-node { pointer-events: auto; }
    .graph-node.dragging { opacity: .72; cursor: grabbing; }
    .graph-node.selected { border-color: #0b63be; box-shadow: 0 4px 10px rgba(10, 111, 216, 0.24); }
    .graph-node-title { font-size: 12px; font-weight: 700; }
    .graph-node-sub { font-size: 11px; color: var(--muted); margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .graph-node-ports { margin-top: 8px; display: flex; justify-content: flex-end; }
    .port-btn { border: 1px solid #0b63be; background: #fff; color: var(--accent); border-radius: 6px; padding: 2px 6px; font-size: 11px; font-weight: 700; cursor: pointer; }
    .mode { font-size: 12px; color: var(--muted); margin-bottom: 6px; }
    .guide { margin-bottom: 8px; padding: 8px 10px; border: 1px dashed var(--line); border-radius: 8px; background: #f8fbff; font-size: 12px; color: #2a4365; }
    .guide strong { display: block; margin-bottom: 4px; }
    .selection-summary { margin-bottom: 8px; padding: 8px 10px; border: 1px solid var(--line); border-radius: 8px; background: #fff; font-size: 12px; color: #344968; line-height: 1.5; }
    .selection-summary b { color: #1d2735; }
    .inline-row button { width: 100%; }
    @media (max-width: 1240px) { .layout { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <div class="page">
    <section class="header">
      <h1>Yagra Workflow Studio</h1>
      <div class="muted">M-09: DnD node/edge editing + form editing</div>
      <div class="toolbar">
        <button id="loadBtn">Load</button>
        <button id="previewBtn" class="secondary">Preview Diff</button>
        <button id="saveBtn">Save</button>
        <input id="backupIdInput" type="text" placeholder="rollback backup_id" style="max-width: 360px;" />
        <button id="rollbackBtn" class="secondary">Rollback</button>
      </div>
      <div class="muted" id="revisionLabel">revision: -</div>
      <div class="muted" id="statusLabel">status: idle</div>
    </section>
    <section class="layout">
      <article class="panel stack">
        <div>
          <h2>Node Form</h2>
          <div class="field">
            <label for="nodeSelect">Node</label>
            <select id="nodeSelect"></select>
          </div>
          <div class="inline-row">
            <div class="field">
              <label for="nodePromptRefInput">prompt_ref</label>
              <input id="nodePromptRefInput" type="text" list="promptRefOptions" placeholder="planner" />
            </div>
            <div class="field">
              <label for="nodeModelRefInput">model_ref</label>
              <input id="nodeModelRefInput" type="text" list="modelRefOptions" placeholder="default" />
            </div>
          </div>
          <div class="field">
            <label for="nodePromptJsonInput">prompt (JSON object)</label>
            <textarea id="nodePromptJsonInput" placeholder='{"system": "..."}'></textarea>
          </div>
          <div class="field">
            <label for="nodeModelJsonInput">model (JSON object)</label>
            <textarea id="nodeModelJsonInput" placeholder='{"provider":"openai","name":"gpt-4.1-mini"}'></textarea>
          </div>
          <button id="applyNodeBtn" class="secondary">Apply Node Edit</button>
          <div class="hint">空文字は該当フィールド削除として扱います。</div>
        </div>
        <div class="split">
          <h2>Add Node</h2>
          <div class="inline-row">
            <div class="field">
              <label for="nodeCreateIdInput">node id</label>
              <input id="nodeCreateIdInput" type="text" placeholder="review" />
            </div>
            <div class="field">
              <label for="nodeCreateHandlerInput">handler</label>
              <input id="nodeCreateHandlerInput" type="text" placeholder="review_handler" />
            </div>
          </div>
          <button id="addNodeBtn" class="secondary">Add Node</button>
          <div class="hint">位置は自動配置されます。追加後にキャンバス上でドラッグして調整できます。</div>
        </div>
        <div class="split">
          <h2>Edge Form</h2>
          <div class="field">
            <label for="edgeSelect">Edge</label>
            <select id="edgeSelect"></select>
          </div>
          <div class="field">
            <label for="edgeConditionInput">condition</label>
            <input id="edgeConditionInput" type="text" placeholder="retry / done" />
          </div>
          <div class="inline-row">
            <button id="applyEdgeBtn" class="secondary" type="button">Apply Edge Edit</button>
            <button id="toggleRewireBtn" class="secondary" type="button">Enable Rewire Mode</button>
          </div>
          <div class="hint">ノードの Connect ボタンをドラッグして接続追加。Rewire Mode では選択エッジを、ドラッグ起点ノード→ドロップ先ノードへ再接続します。</div>
        </div>
      </article>
      <article class="panel stack">
        <div>
          <h2>Graph Canvas</h2>
          <div class="guide">
            <strong>Quick Guide</strong>
            1) Add Node で追加<br />
            2) ノードの Connect をドラッグして接続追加<br />
            3) エッジ線をクリックして選択し、Enable Rewire Mode 後に Connect をドラッグして再接続<br />
            4) Preview Diff を確認して Save
          </div>
          <div id="selectionSummary" class="selection-summary"></div>
          <div id="connectionModeLabel" class="mode">connection mode: idle</div>
          <div id="graphCanvas" class="graph-canvas">
            <svg id="graphEdgeLayer" class="graph-edge-layer"></svg>
            <div id="graphNodeLayer" class="graph-node-layer"></div>
          </div>
        </div>
        <div>
          <h2>Validation</h2>
          <pre id="validationView"></pre>
        </div>
        <div>
          <h2>Diff</h2>
          <pre id="diffView"></pre>
        </div>
        <div>
          <h2>Pending Form Edits</h2>
          <pre id="pendingView"></pre>
        </div>
      </article>
      <article class="panel stack raw">
        <div>
          <h2>Workflow (JSON: read only)</h2>
          <textarea id="workflowEditor" readonly></textarea>
        </div>
        <div>
          <h2>UI State (JSON: read only)</h2>
          <textarea id="uiStateEditor" readonly></textarea>
        </div>
      </article>
    </section>
    <datalist id="promptRefOptions"></datalist>
    <datalist id="modelRefOptions"></datalist>
  </div>
  <script>
    const state = {
      revision: null,
      workflow: {},
      uiState: {},
      formNodes: [],
      formEdges: [],
      pendingNodeCreates: [],
      pendingNodeEdits: [],
      pendingEdgeCreates: [],
      pendingEdgeRewires: [],
      pendingEdgeEdits: [],
      promptCatalogKeys: [],
      modelCatalogKeys: [],
      activeRewireEdgeIndex: null,
      dragNode: null,
      dragConnection: null,
    };

    const workflowEditor = document.getElementById("workflowEditor");
    const uiStateEditor = document.getElementById("uiStateEditor");
    const validationView = document.getElementById("validationView");
    const diffView = document.getElementById("diffView");
    const pendingView = document.getElementById("pendingView");
    const revisionLabel = document.getElementById("revisionLabel");
    const statusLabel = document.getElementById("statusLabel");
    const backupIdInput = document.getElementById("backupIdInput");
    const nodeSelect = document.getElementById("nodeSelect");
    const edgeSelect = document.getElementById("edgeSelect");
    const nodePromptRefInput = document.getElementById("nodePromptRefInput");
    const nodeModelRefInput = document.getElementById("nodeModelRefInput");
    const nodePromptJsonInput = document.getElementById("nodePromptJsonInput");
    const nodeModelJsonInput = document.getElementById("nodeModelJsonInput");
    const nodeCreateIdInput = document.getElementById("nodeCreateIdInput");
    const nodeCreateHandlerInput = document.getElementById("nodeCreateHandlerInput");
    const edgeConditionInput = document.getElementById("edgeConditionInput");
    const promptRefOptions = document.getElementById("promptRefOptions");
    const modelRefOptions = document.getElementById("modelRefOptions");
    const graphCanvas = document.getElementById("graphCanvas");
    const graphEdgeLayer = document.getElementById("graphEdgeLayer");
    const graphNodeLayer = document.getElementById("graphNodeLayer");
    const connectionModeLabel = document.getElementById("connectionModeLabel");
    const selectionSummary = document.getElementById("selectionSummary");
    const toggleRewireBtn = document.getElementById("toggleRewireBtn");

    function setStatus(message, isError = false) {
      statusLabel.textContent = `status: ${message}`;
      statusLabel.className = isError ? "danger" : "ok";
    }

    function errorMessage(err) {
      if (err instanceof Error) return err.message;
      return String(err);
    }

    function escapeHtml(value) {
      return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
    }

    function parseJsonObject(raw, label) {
      try {
        const value = String(raw || "").trim();
        if (!value) return {};
        const parsed = JSON.parse(value);
        if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
          throw new Error("must be object");
        }
        return parsed;
      } catch (err) {
        throw new Error(`${label} is invalid JSON object: ${errorMessage(err)}`);
      }
    }

    function deepClone(value) {
      return JSON.parse(JSON.stringify(value));
    }

    function clamp(value, min, max) {
      return Math.min(max, Math.max(min, value));
    }

    function canvasMetrics() {
      const rect = graphCanvas.getBoundingClientRect();
      const width = Math.max(320, Math.floor(rect.width || graphCanvas.clientWidth || 320));
      const height = Math.max(360, Math.floor(rect.height || graphCanvas.clientHeight || 360));
      return { width, height };
    }

    function defaultNodePosition(index) {
      const { width } = canvasMetrics();
      const nodeWidth = 140;
      const paddingX = 16;
      const gapX = 24;
      const gapY = 96;
      const usableWidth = Math.max(nodeWidth, width - paddingX * 2);
      const columns = Math.max(
        1,
        Math.floor((usableWidth + gapX) / (nodeWidth + gapX)),
      );
      const col = index % columns;
      const row = Math.floor(index / columns);
      return {
        x: paddingX + col * (nodeWidth + gapX),
        y: 24 + row * gapY,
      };
    }

    function ensurePositionsContainer() {
      if (!state.uiState || typeof state.uiState !== "object" || Array.isArray(state.uiState)) {
        state.uiState = {};
      }
      if (
        !state.uiState.positions ||
        typeof state.uiState.positions !== "object" ||
        Array.isArray(state.uiState.positions)
      ) {
        state.uiState.positions = {};
      }
      return state.uiState.positions;
    }

    function ensureUiStatePositions() {
      const positions = ensurePositionsContainer();
      for (const [index, node] of state.formNodes.entries()) {
        const raw = positions[node.id];
        if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
          positions[node.id] = defaultNodePosition(index);
          continue;
        }
        const x = Number(raw.x);
        const y = Number(raw.y);
        if (!Number.isFinite(x) || !Number.isFinite(y)) {
          positions[node.id] = defaultNodePosition(index);
          continue;
        }
        positions[node.id] = { x: clamp(x, 0, 3000), y: clamp(y, 0, 3000) };
      }
    }

    function getNodePosition(nodeId) {
      ensureUiStatePositions();
      const positions = ensurePositionsContainer();
      const index = state.formNodes.findIndex(node => node.id === nodeId);
      const fallback = defaultNodePosition(index >= 0 ? index : 0);
      const raw = positions[nodeId];
      if (!raw || typeof raw !== "object") {
        return fallback;
      }
      return {
        x: Number.isFinite(Number(raw.x)) ? Number(raw.x) : fallback.x,
        y: Number.isFinite(Number(raw.y)) ? Number(raw.y) : fallback.y,
      };
    }

    function nodeCenter(nodeId) {
      const pos = getNodePosition(nodeId);
      return { x: pos.x + 70, y: pos.y + 30 };
    }

    function toCanvasPoint(clientX, clientY) {
      const rect = graphCanvas.getBoundingClientRect();
      return { x: clientX - rect.left, y: clientY - rect.top };
    }

    function resolveDropNodeId(target) {
      if (!(target instanceof Element)) return null;
      const nodeEl = target.closest(".graph-node");
      if (!(nodeEl instanceof HTMLElement)) return null;
      return nodeEl.dataset.nodeId || null;
    }

    function updateConnectionModeLabel() {
      if (state.activeRewireEdgeIndex === null) {
        connectionModeLabel.textContent = "connection mode: create edge (drag Connect from source to target)";
        return;
      }
      connectionModeLabel.textContent = `connection mode: rewire edge[${state.activeRewireEdgeIndex}] (drag Connect for new source/target)`;
    }

    function updateRewireButton() {
      if (state.activeRewireEdgeIndex === null) {
        toggleRewireBtn.textContent = "Enable Rewire Mode";
        toggleRewireBtn.classList.add("secondary");
        return;
      }
      toggleRewireBtn.textContent = `Disable Rewire Mode (edge[${state.activeRewireEdgeIndex}])`;
      toggleRewireBtn.classList.remove("secondary");
    }

    function renderSelectionSummary() {
      const selectedNodeId = nodeSelect.value || "-";
      const selectedEdgeIndex = Number(edgeSelect.value);
      const selectedEdge = state.formEdges.find(item => item.index === selectedEdgeIndex);
      const selectedEdgeText = selectedEdge
        ? `[${selectedEdge.index}] ${selectedEdge.source} -> ${selectedEdge.target}`
        : "-";
      const pendingTotal =
        state.pendingNodeCreates.length +
        state.pendingNodeEdits.length +
        state.pendingEdgeCreates.length +
        state.pendingEdgeRewires.length +
        state.pendingEdgeEdits.length;
      const rewireText =
        state.activeRewireEdgeIndex === null
          ? "OFF"
          : `ON (edge[${state.activeRewireEdgeIndex}])`;
      selectionSummary.innerHTML =
        `<b>Selected Node:</b> ${escapeHtml(selectedNodeId)}<br />` +
        `<b>Selected Edge:</b> ${escapeHtml(selectedEdgeText)}<br />` +
        `<b>Rewire Mode:</b> ${escapeHtml(rewireText)}<br />` +
        `<b>Pending Edits:</b> ${pendingTotal}`;
    }

    function selectEdge(edgeIndex, announce = false) {
      const edge = state.formEdges.find(item => item.index === edgeIndex);
      if (!edge) return;
      edgeSelect.value = String(edgeIndex);
      renderEdgeForm(edgeIndex);
      if (state.activeRewireEdgeIndex !== null) {
        state.activeRewireEdgeIndex = edgeIndex;
      }
      updateConnectionModeLabel();
      updateRewireButton();
      renderSelectionSummary();
      renderGraph();
      if (announce) {
        setStatus(`edge selected: [${edge.index}] ${edge.source} -> ${edge.target}`);
      }
    }

    function clearPendingEdits() {
      state.pendingNodeCreates = [];
      state.pendingNodeEdits = [];
      state.pendingEdgeCreates = [];
      state.pendingEdgeRewires = [];
      state.pendingEdgeEdits = [];
    }

    function upsertNodeCreate(edit) {
      const idx = state.pendingNodeCreates.findIndex(item => item.node_id === edit.node_id);
      if (idx >= 0) {
        state.pendingNodeCreates[idx] = { ...state.pendingNodeCreates[idx], ...edit };
      } else {
        state.pendingNodeCreates.push(edit);
      }
    }

    function upsertNodeEdit(edit) {
      const idx = state.pendingNodeEdits.findIndex(item => item.node_id === edit.node_id);
      if (idx >= 0) {
        state.pendingNodeEdits[idx] = { ...state.pendingNodeEdits[idx], ...edit };
      } else {
        state.pendingNodeEdits.push(edit);
      }
    }

    function appendEdgeCreate(edit) {
      state.pendingEdgeCreates.push(edit);
    }

    function upsertEdgeRewire(edit) {
      const idx = state.pendingEdgeRewires.findIndex(item => item.edge_index === edit.edge_index);
      if (idx >= 0) {
        state.pendingEdgeRewires[idx] = { ...state.pendingEdgeRewires[idx], ...edit };
      } else {
        state.pendingEdgeRewires.push(edit);
      }
    }

    function upsertEdgeEdit(edit) {
      const idx = state.pendingEdgeEdits.findIndex(item => item.edge_index === edit.edge_index);
      if (idx >= 0) {
        state.pendingEdgeEdits[idx] = { ...state.pendingEdgeEdits[idx], ...edit };
      } else {
        state.pendingEdgeEdits.push(edit);
      }
    }

    function renderPending() {
      const payload = {
        node_creates: state.pendingNodeCreates,
        node_edits: state.pendingNodeEdits,
        edge_creates: state.pendingEdgeCreates,
        edge_rewires: state.pendingEdgeRewires,
        edge_edits: state.pendingEdgeEdits,
      };
      pendingView.textContent = JSON.stringify(payload, null, 2);
      renderSelectionSummary();
    }

    function renderEditors() {
      workflowEditor.value = JSON.stringify(state.workflow || {}, null, 2);
      uiStateEditor.value = JSON.stringify(state.uiState || {}, null, 2);
    }

    function renderCatalogOptions() {
      promptRefOptions.innerHTML = "";
      for (const key of state.promptCatalogKeys) {
        const option = document.createElement("option");
        option.value = key;
        promptRefOptions.appendChild(option);
      }
      modelRefOptions.innerHTML = "";
      for (const key of state.modelCatalogKeys) {
        const option = document.createElement("option");
        option.value = key;
        modelRefOptions.appendChild(option);
      }
    }

    function rebuildFormStateFromWorkflow() {
      const nodes = Array.isArray(state.workflow.nodes) ? state.workflow.nodes : [];
      state.formNodes = nodes
        .filter(node => node && typeof node === "object" && typeof node.id === "string")
        .map(node => {
          const params = node.params && typeof node.params === "object" ? node.params : {};
          return {
            id: node.id,
            handler: typeof node.handler === "string" ? node.handler : "",
            prompt_ref: typeof params.prompt_ref === "string" ? params.prompt_ref : null,
            model_ref: typeof params.model_ref === "string" ? params.model_ref : null,
            prompt: params.prompt && typeof params.prompt === "object" ? params.prompt : null,
            model: params.model && typeof params.model === "object" ? params.model : null,
          };
        });

      const edges = Array.isArray(state.workflow.edges) ? state.workflow.edges : [];
      state.formEdges = edges
        .map((edge, index) => {
          if (!edge || typeof edge !== "object") return null;
          if (typeof edge.source !== "string" || typeof edge.target !== "string") return null;
          return {
            index,
            source: edge.source,
            target: edge.target,
            condition: typeof edge.condition === "string" ? edge.condition : null,
          };
        })
        .filter(Boolean);

      ensureUiStatePositions();
    }

    function renderNodeOptions() {
      const current = nodeSelect.value;
      nodeSelect.innerHTML = "";
      for (const node of state.formNodes) {
        const option = document.createElement("option");
        option.value = node.id;
        option.textContent = `${node.id} (${node.handler})`;
        nodeSelect.appendChild(option);
      }
      if (!state.formNodes.length) {
        nodePromptRefInput.value = "";
        nodeModelRefInput.value = "";
        nodePromptJsonInput.value = "";
        nodeModelJsonInput.value = "";
        return;
      }
      const target = state.formNodes.some(node => node.id === current)
        ? current
        : state.formNodes[0].id;
      nodeSelect.value = target;
      renderNodeForm(target);
    }

    function renderEdgeOptions() {
      const current = edgeSelect.value;
      edgeSelect.innerHTML = "";
      for (const edge of state.formEdges) {
        const option = document.createElement("option");
        option.value = String(edge.index);
        option.textContent = `[${edge.index}] ${edge.source} -> ${edge.target}`;
        edgeSelect.appendChild(option);
      }
      if (!state.formEdges.length) {
        edgeConditionInput.value = "";
        state.activeRewireEdgeIndex = null;
        updateConnectionModeLabel();
        updateRewireButton();
        renderSelectionSummary();
        return;
      }
      const target = state.formEdges.some(edge => String(edge.index) === current)
        ? current
        : String(state.formEdges[0].index);
      edgeSelect.value = target;
      renderEdgeForm(Number(target));
      if (state.activeRewireEdgeIndex !== null) {
        state.activeRewireEdgeIndex = Number(target);
      }
      updateConnectionModeLabel();
      updateRewireButton();
      renderSelectionSummary();
    }

    function renderNodeForm(nodeId) {
      const node = state.formNodes.find(item => item.id === nodeId);
      if (!node) return;
      nodePromptRefInput.value = node.prompt_ref || "";
      nodeModelRefInput.value = node.model_ref || "";
      nodePromptJsonInput.value = node.prompt ? JSON.stringify(node.prompt, null, 2) : "";
      nodeModelJsonInput.value = node.model ? JSON.stringify(node.model, null, 2) : "";
    }

    function renderEdgeForm(edgeIndex) {
      const edge = state.formEdges.find(item => item.index === edgeIndex);
      if (!edge) return;
      edgeConditionInput.value = edge.condition || "";
    }

    function renderValidation(report) {
      if (!report) {
        validationView.textContent = "-";
        return;
      }
      if (report.is_valid) {
        validationView.textContent = "workflow validation passed";
        return;
      }
      const lines = ["workflow validation failed:"];
      for (const issue of report.issues || []) {
        lines.push(`- [${issue.code}] ${issue.message} @ ${JSON.stringify(issue.location || [])}`);
      }
      validationView.textContent = lines.join("\\n");
    }

    function renderDiff(data) {
      const summary = data.summary || {};
      const lines = [
        `summary: total=${summary.total || 0}, nodes=${summary.nodes || 0}, edges=${summary.edges || 0}, params=${summary.params || 0}, ui_state=${summary.ui_state || 0}, other=${summary.other || 0}`,
        "",
        "yaml diff:",
        data.yaml_unified_diff || "(no yaml changes)",
      ];
      diffView.textContent = lines.join("\\n");
    }

    function ensureWorkflowArrays() {
      if (!Array.isArray(state.workflow.nodes)) state.workflow.nodes = [];
      if (!Array.isArray(state.workflow.edges)) state.workflow.edges = [];
    }

    function collectKnownNodeIds() {
      ensureWorkflowArrays();
      const ids = new Set();
      for (const node of state.workflow.nodes) {
        if (node && typeof node === "object" && typeof node.id === "string") {
          ids.add(node.id);
        }
      }
      return ids;
    }

    function normalizeCondition(value) {
      if (value === null || value === undefined) return null;
      const text = String(value).trim();
      return text ? text : null;
    }

    function suggestNodeCreatePosition() {
      const selectedNodeId = nodeSelect.value;
      if (selectedNodeId) {
        const selectedIndex = state.formNodes.findIndex(node => node.id === selectedNodeId);
        if (selectedIndex >= 0) {
          const base = getNodePosition(selectedNodeId);
          const { width, height } = canvasMetrics();
          const maxX = Math.max(10, width - 150);
          const maxY = Math.max(10, height - 72);
          return {
            x: clamp(base.x + 170, 10, maxX),
            y: clamp(base.y, 10, maxY),
          };
        }
      }
      const fallback = defaultNodePosition(state.formNodes.length);
      const { width, height } = canvasMetrics();
      return {
        x: clamp(fallback.x, 10, Math.max(10, width - 150)),
        y: clamp(fallback.y, 10, Math.max(10, height - 72)),
      };
    }

    function applyNodeCreateToWorkflow(create) {
      ensureWorkflowArrays();
      const knownNodeIds = collectKnownNodeIds();
      if (knownNodeIds.has(create.node_id)) {
        throw new Error(`node already exists: ${create.node_id}`);
      }

      const nodePayload = {
        id: create.node_id,
        handler: create.handler,
      };
      state.workflow.nodes.push(nodePayload);

      const index = state.workflow.nodes.length - 1;
      const fallback = defaultNodePosition(index);
      const positions = ensurePositionsContainer();
      positions[create.node_id] = create.position
        ? { x: create.position.x, y: create.position.y }
        : fallback;
    }

    function applyNodeEditToWorkflow(edit) {
      ensureWorkflowArrays();
      const targetNode = state.workflow.nodes.find(node => node && node.id === edit.node_id);
      if (!targetNode) {
        throw new Error(`node not found: ${edit.node_id}`);
      }
      const params = targetNode.params && typeof targetNode.params === "object" ? targetNode.params : {};
      targetNode.params = params;

      if ("prompt_ref" in edit) {
        if (!edit.prompt_ref) delete params.prompt_ref;
        else params.prompt_ref = edit.prompt_ref;
      }
      if ("model_ref" in edit) {
        if (!edit.model_ref) delete params.model_ref;
        else params.model_ref = edit.model_ref;
      }
      if ("prompt" in edit) {
        if (edit.prompt === null) delete params.prompt;
        else params.prompt = deepClone(edit.prompt);
      }
      if ("model" in edit) {
        if (edit.model === null) delete params.model;
        else params.model = deepClone(edit.model);
      }
    }

    function applyEdgeCreateToWorkflow(create) {
      ensureWorkflowArrays();
      const knownNodeIds = collectKnownNodeIds();
      if (!knownNodeIds.has(create.source)) {
        throw new Error(`edge source node not found: ${create.source}`);
      }
      if (!knownNodeIds.has(create.target)) {
        throw new Error(`edge target node not found: ${create.target}`);
      }
      const edgePayload = {
        source: create.source,
        target: create.target,
      };
      const condition = normalizeCondition(create.condition);
      if (condition !== null) {
        edgePayload.condition = condition;
      }
      state.workflow.edges.push(edgePayload);
    }

    function applyEdgeRewireToWorkflow(edit) {
      ensureWorkflowArrays();
      const knownNodeIds = collectKnownNodeIds();
      const edge = state.workflow.edges[edit.edge_index];
      if (!edge || typeof edge !== "object") {
        throw new Error(`edge not found: ${edit.edge_index}`);
      }
      if ("source" in edit) {
        if (!knownNodeIds.has(edit.source)) {
          throw new Error(`edge source node not found: ${edit.source}`);
        }
        edge.source = edit.source;
      }
      if ("target" in edit) {
        if (!knownNodeIds.has(edit.target)) {
          throw new Error(`edge target node not found: ${edit.target}`);
        }
        edge.target = edit.target;
      }
      if ("condition" in edit) {
        const condition = normalizeCondition(edit.condition);
        if (condition === null) {
          delete edge.condition;
        } else {
          edge.condition = condition;
        }
      }
    }

    function applyEdgeEditToWorkflow(edit) {
      ensureWorkflowArrays();
      const edge = state.workflow.edges[edit.edge_index];
      if (!edge || typeof edge !== "object") {
        throw new Error(`edge not found: ${edit.edge_index}`);
      }
      const condition = normalizeCondition(edit.condition);
      if (condition === null) delete edge.condition;
      else edge.condition = condition;
    }

    function renderGraph() {
      ensureUiStatePositions();
      const canvasRect = graphCanvas.getBoundingClientRect();
      const width = Math.max(320, Math.floor(canvasRect.width || graphCanvas.clientWidth || 320));
      const height = Math.max(360, Math.floor(canvasRect.height || graphCanvas.clientHeight || 360));

      graphEdgeLayer.setAttribute("viewBox", `0 0 ${width} ${height}`);
      graphEdgeLayer.setAttribute("width", String(width));
      graphEdgeLayer.setAttribute("height", String(height));
      graphEdgeLayer.replaceChildren();
      graphNodeLayer.replaceChildren();

      const activeEdgeIndex = Number(edgeSelect.value);
      for (const edge of state.formEdges) {
        const source = nodeCenter(edge.source);
        const target = nodeCenter(edge.target);
        const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
        line.setAttribute("x1", String(source.x));
        line.setAttribute("y1", String(source.y));
        line.setAttribute("x2", String(target.x));
        line.setAttribute("y2", String(target.y));
        const isHighlighted =
          edge.index === state.activeRewireEdgeIndex || edge.index === activeEdgeIndex;
        line.setAttribute("stroke", isHighlighted ? "#0a6fd8" : "#8ea4c6");
        line.setAttribute("stroke-width", isHighlighted ? "2.4" : "1.4");
        line.setAttribute("pointer-events", "stroke");
        line.style.cursor = "pointer";
        line.addEventListener("click", event => {
          event.stopPropagation();
          selectEdge(edge.index, true);
        });
        graphEdgeLayer.appendChild(line);

        const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
        text.setAttribute("x", String((source.x + target.x) / 2));
        text.setAttribute("y", String((source.y + target.y) / 2 - 6));
        text.setAttribute("fill", "#446189");
        text.setAttribute("font-size", "10");
        text.setAttribute("text-anchor", "middle");
        text.style.cursor = "pointer";
        text.textContent = edge.condition ? `[${edge.index}] ${edge.condition}` : `[${edge.index}]`;
        text.addEventListener("click", event => {
          event.stopPropagation();
          selectEdge(edge.index, true);
        });
        graphEdgeLayer.appendChild(text);
      }

      if (state.dragConnection) {
        const source = nodeCenter(state.dragConnection.sourceNodeId);
        const ghost = document.createElementNS("http://www.w3.org/2000/svg", "line");
        ghost.setAttribute("x1", String(source.x));
        ghost.setAttribute("y1", String(source.y));
        ghost.setAttribute("x2", String(state.dragConnection.pointerX));
        ghost.setAttribute("y2", String(state.dragConnection.pointerY));
        ghost.setAttribute("stroke", "#0a6fd8");
        ghost.setAttribute("stroke-width", "2");
        ghost.setAttribute("stroke-dasharray", "5 4");
        graphEdgeLayer.appendChild(ghost);
      }

      for (const node of state.formNodes) {
        const pos = getNodePosition(node.id);
        const nodeEl = document.createElement("div");
        nodeEl.className = "graph-node";
        if (node.id === nodeSelect.value) nodeEl.classList.add("selected");
        if (state.dragNode && state.dragNode.nodeId === node.id) nodeEl.classList.add("dragging");
        nodeEl.dataset.nodeId = node.id;
        nodeEl.style.left = `${Math.round(pos.x)}px`;
        nodeEl.style.top = `${Math.round(pos.y)}px`;
        nodeEl.innerHTML = `
          <div class="graph-node-title">${escapeHtml(node.id)}</div>
          <div class="graph-node-sub">${escapeHtml(node.handler)}</div>
          <div class="graph-node-ports">
            <button type="button" class="port-btn" data-connect="true">Connect</button>
          </div>
        `;

        nodeEl.addEventListener("pointerdown", event => startNodeDrag(event, node.id));
        const connectBtn = nodeEl.querySelector("[data-connect]");
        if (connectBtn instanceof HTMLElement) {
          connectBtn.addEventListener("pointerdown", event => startConnectionDrag(event, node.id));
        }
        nodeEl.addEventListener("click", event => {
          if (event.target instanceof Element && event.target.closest("[data-connect]")) return;
          nodeSelect.value = node.id;
          renderNodeForm(node.id);
          renderSelectionSummary();
          renderGraph();
        });

        graphNodeLayer.appendChild(nodeEl);
      }
    }

    async function loadWorkflow() {
      setStatus("loading...");
      const res = await fetch("/api/workflow/form");
      const data = await res.json();
      if (!res.ok) {
        setStatus(data.message || data.error || "load failed", true);
        return;
      }

      state.workflow = data.workflow || {};
      state.uiState = data.ui_state || {};
      state.formNodes = data.nodes || [];
      state.formEdges = data.edges || [];
      state.promptCatalogKeys = data.prompt_catalog_keys || [];
      state.modelCatalogKeys = data.model_catalog_keys || [];
      clearPendingEdits();
      state.activeRewireEdgeIndex = null;
      state.dragNode = null;
      state.dragConnection = null;
      state.revision = data.revision;

      renderCatalogOptions();
      rebuildFormStateFromWorkflow();
      renderNodeOptions();
      renderEdgeOptions();
      renderEditors();
      renderPending();
      renderGraph();
      updateConnectionModeLabel();
      updateRewireButton();
      renderSelectionSummary();
      revisionLabel.textContent = `revision: ${state.revision}`;
      renderValidation(data.validation_report);
      diffView.textContent = "";
      setStatus("loaded");
    }

    function collectNodeCreateFromForm() {
      const nodeId = nodeCreateIdInput.value.trim();
      const handler = nodeCreateHandlerInput.value.trim();
      if (!nodeId) throw new Error("node id is required");
      if (!handler) throw new Error("handler is required");
      return {
        node_id: nodeId,
        handler,
        position: suggestNodeCreatePosition(),
      };
    }

    function collectNodeEditFromForm() {
      const nodeId = nodeSelect.value;
      if (!nodeId) throw new Error("node is not selected");
      const promptRef = nodePromptRefInput.value.trim();
      const modelRef = nodeModelRefInput.value.trim();
      const promptRaw = nodePromptJsonInput.value.trim();
      const modelRaw = nodeModelJsonInput.value.trim();
      return {
        node_id: nodeId,
        prompt_ref: promptRef || null,
        model_ref: modelRef || null,
        prompt: promptRaw ? parseJsonObject(promptRaw, "prompt") : null,
        model: modelRaw ? parseJsonObject(modelRaw, "model") : null,
      };
    }

    function collectEdgeEditFromForm() {
      if (!edgeSelect.value) throw new Error("edge is not selected");
      const condition = edgeConditionInput.value.trim();
      return {
        edge_index: Number(edgeSelect.value),
        condition: condition || null,
      };
    }

    async function applyNodeCreate() {
      if (!state.revision) {
        setStatus("load first", true);
        return;
      }
      try {
        const create = collectNodeCreateFromForm();
        upsertNodeCreate(create);
        applyNodeCreateToWorkflow(create);
        rebuildFormStateFromWorkflow();
        renderNodeOptions();
        nodeSelect.value = create.node_id;
        renderNodeForm(create.node_id);
        renderEdgeOptions();
        renderEditors();
        renderPending();
        renderGraph();
        nodeCreateIdInput.value = "";
        nodeCreateHandlerInput.value = "";
        setStatus(`node created: ${create.node_id} (auto placed)`);
      } catch (err) {
        setStatus(errorMessage(err), true);
      }
    }

    async function applyNodeEdit() {
      if (!state.revision) {
        setStatus("load first", true);
        return;
      }

      try {
        const edit = collectNodeEditFromForm();
        upsertNodeEdit(edit);
        applyNodeEditToWorkflow(edit);
        rebuildFormStateFromWorkflow();
        renderNodeOptions();
        renderEditors();
        renderPending();
        renderGraph();
        setStatus(`node edit applied: ${edit.node_id}`);
      } catch (err) {
        setStatus(errorMessage(err), true);
      }
    }

    async function applyEdgeEdit() {
      if (!state.revision) {
        setStatus("load first", true);
        return;
      }

      try {
        const edit = collectEdgeEditFromForm();
        upsertEdgeEdit(edit);
        applyEdgeEditToWorkflow(edit);
        rebuildFormStateFromWorkflow();
        renderEdgeOptions();
        renderEditors();
        renderPending();
        renderGraph();
        setStatus(`edge edit applied: [${edit.edge_index}]`);
      } catch (err) {
        setStatus(errorMessage(err), true);
      }
    }

    function toggleRewireMode() {
      if (!edgeSelect.value) {
        setStatus("edge is not selected", true);
        return;
      }
      const selectedEdgeIndex = Number(edgeSelect.value);
      if (state.activeRewireEdgeIndex === selectedEdgeIndex) {
        state.activeRewireEdgeIndex = null;
        updateConnectionModeLabel();
        updateRewireButton();
        renderSelectionSummary();
        renderGraph();
        setStatus("rewire mode disabled");
        return;
      }
      state.activeRewireEdgeIndex = selectedEdgeIndex;
      updateConnectionModeLabel();
      updateRewireButton();
      renderSelectionSummary();
      renderGraph();
      setStatus(`rewire mode enabled: edge[${state.activeRewireEdgeIndex}]`);
    }

    function startConnectionDrag(event, sourceNodeId) {
      if (!state.revision) return;
      if (event.button !== 0) return;

      if (state.activeRewireEdgeIndex !== null) {
        const edge = state.formEdges.find(item => item.index === state.activeRewireEdgeIndex);
        if (!edge) {
          setStatus("selected edge not found", true);
          state.activeRewireEdgeIndex = null;
          updateConnectionModeLabel();
          updateRewireButton();
          renderSelectionSummary();
          return;
        }
      }

      const point = toCanvasPoint(event.clientX, event.clientY);
      state.dragConnection = {
        sourceNodeId,
        rewireEdgeIndex: state.activeRewireEdgeIndex,
        pointerX: point.x,
        pointerY: point.y,
      };
      const modeText =
        state.activeRewireEdgeIndex === null
          ? `create edge from ${sourceNodeId}`
          : `rewire edge[${state.activeRewireEdgeIndex}] with source ${sourceNodeId}`;
      setStatus(`${modeText}: drop on target node`);
      renderGraph();
      event.preventDefault();
      event.stopPropagation();
    }

    function startNodeDrag(event, nodeId) {
      if (!state.revision) return;
      if (event.button !== 0) return;
      if (event.target instanceof Element && event.target.closest("[data-connect]")) {
        return;
      }

      const current = getNodePosition(nodeId);
      const point = toCanvasPoint(event.clientX, event.clientY);
      state.dragNode = {
        nodeId,
        offsetX: point.x - current.x,
        offsetY: point.y - current.y,
      };
      event.preventDefault();
    }

    function applyConnectionResult(connection, targetNodeId) {
      if (connection.sourceNodeId === targetNodeId) {
        throw new Error("source and target must be different");
      }

      if (connection.rewireEdgeIndex !== null) {
        const edit = {
          edge_index: connection.rewireEdgeIndex,
          source: connection.sourceNodeId,
          target: targetNodeId,
        };
        upsertEdgeRewire(edit);
        applyEdgeRewireToWorkflow(edit);
        state.activeRewireEdgeIndex = null;
        rebuildFormStateFromWorkflow();
        renderNodeOptions();
        renderEdgeOptions();
        edgeSelect.value = String(edit.edge_index);
        renderEdgeForm(edit.edge_index);
        renderEditors();
        renderPending();
        updateConnectionModeLabel();
        updateRewireButton();
        renderSelectionSummary();
        setStatus(`edge rewired: [${edit.edge_index}] ${edit.source} -> ${edit.target}`);
        return;
      }
      const create = {
        source: connection.sourceNodeId,
        target: targetNodeId,
      };
      appendEdgeCreate(create);
      applyEdgeCreateToWorkflow(create);
      rebuildFormStateFromWorkflow();
      renderNodeOptions();
      renderEdgeOptions();
      renderEditors();
      renderPending();
      renderSelectionSummary();
      setStatus(`edge created: ${create.source} -> ${create.target}`);
    }

    function handleGlobalPointerMove(event) {
      if (state.dragNode) {
        const point = toCanvasPoint(event.clientX, event.clientY);
        const canvasRect = graphCanvas.getBoundingClientRect();
        const maxX = Math.max(10, canvasRect.width - 150);
        const maxY = Math.max(10, canvasRect.height - 72);
        const x = clamp(point.x - state.dragNode.offsetX, 10, maxX);
        const y = clamp(point.y - state.dragNode.offsetY, 10, maxY);
        const positions = ensurePositionsContainer();
        positions[state.dragNode.nodeId] = { x, y };
        renderGraph();
        return;
      }

      if (state.dragConnection) {
        const point = toCanvasPoint(event.clientX, event.clientY);
        state.dragConnection.pointerX = point.x;
        state.dragConnection.pointerY = point.y;
        renderGraph();
      }
    }

    function handleGlobalPointerUp(event) {
      if (state.dragNode) {
        const nodeId = state.dragNode.nodeId;
        state.dragNode = null;
        renderGraph();
        renderEditors();
        setStatus(`node moved: ${nodeId}`);
        return;
      }

      if (state.dragConnection) {
        const connection = state.dragConnection;
        state.dragConnection = null;
        const targetNodeId = resolveDropNodeId(event.target);
        if (!targetNodeId) {
          setStatus("connection canceled");
          renderGraph();
          return;
        }
        try {
          applyConnectionResult(connection, targetNodeId);
        } catch (err) {
          setStatus(errorMessage(err), true);
        }
        renderGraph();
      }
    }

    async function previewDiff() {
      if (!state.revision) {
        setStatus("load first", true);
        return;
      }
      setStatus("previewing...");
      const res = await fetch("/api/workflow/form/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          base_revision: state.revision,
          node_creates: state.pendingNodeCreates,
          node_edits: state.pendingNodeEdits,
          edge_creates: state.pendingEdgeCreates,
          edge_rewires: state.pendingEdgeRewires,
          edge_edits: state.pendingEdgeEdits,
          ui_state: state.uiState,
        }),
      });
      const data = await res.json();
      if (res.status === 409) {
        setStatus("revision conflict. reload required", true);
        revisionLabel.textContent = `revision: ${data.actual_revision}`;
        return;
      }
      if (!res.ok) {
        setStatus(data.message || data.error || "diff failed", true);
        return;
      }
      state.workflow = data.candidate_workflow || state.workflow;
      state.uiState = data.candidate_ui_state || state.uiState;
      clearPendingEdits();
      state.activeRewireEdgeIndex = null;
      rebuildFormStateFromWorkflow();
      renderNodeOptions();
      renderEdgeOptions();
      renderEditors();
      renderPending();
      renderGraph();
      updateConnectionModeLabel();
      updateRewireButton();
      renderSelectionSummary();
      renderValidation(data.validation_report);
      renderDiff(data);
      setStatus("diff ready");
    }

    async function saveWorkflow() {
      if (!state.revision) {
        setStatus("load first", true);
        return;
      }
      setStatus("saving...");
      const res = await fetch("/api/workflow/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          workflow: state.workflow,
          ui_state: state.uiState,
          base_revision: state.revision,
        }),
      });
      const data = await res.json();
      if (res.status === 409) {
        setStatus("revision conflict. reload required", true);
        revisionLabel.textContent = `revision: ${data.actual_revision}`;
        return;
      }
      if (res.status === 422) {
        renderValidation(data.report);
        setStatus("validation failed", true);
        return;
      }
      if (!res.ok) {
        setStatus(data.message || data.error || "save failed", true);
        return;
      }
      state.revision = data.saved_revision;
      clearPendingEdits();
      state.activeRewireEdgeIndex = null;
      revisionLabel.textContent = `revision: ${state.revision}`;
      backupIdInput.value = data.backup_id || "";
      setStatus(`saved (backup: ${data.backup_id})`);
      await loadWorkflow();
    }

    async function rollbackWorkflow() {
      const backupId = backupIdInput.value.trim();
      if (!backupId) {
        setStatus("backup_id is required", true);
        return;
      }
      setStatus("rolling back...");
      const res = await fetch("/api/workflow/rollback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ backup_id: backupId }),
      });
      const data = await res.json();
      if (!res.ok) {
        setStatus(data.message || data.error || "rollback failed", true);
        return;
      }
      state.revision = data.restored_revision;
      revisionLabel.textContent = `revision: ${state.revision}`;
      setStatus(`rolled back (${backupId})`);
      await loadWorkflow();
    }

    document.getElementById("loadBtn").addEventListener("click", loadWorkflow);
    document.getElementById("previewBtn").addEventListener("click", previewDiff);
    document.getElementById("saveBtn").addEventListener("click", saveWorkflow);
    document.getElementById("rollbackBtn").addEventListener("click", rollbackWorkflow);
    document.getElementById("addNodeBtn").addEventListener("click", applyNodeCreate);
    document.getElementById("applyNodeBtn").addEventListener("click", applyNodeEdit);
    document.getElementById("applyEdgeBtn").addEventListener("click", applyEdgeEdit);
    toggleRewireBtn.addEventListener("click", toggleRewireMode);
    nodeSelect.addEventListener("change", () => {
      renderNodeForm(nodeSelect.value);
      renderSelectionSummary();
      renderGraph();
    });
    edgeSelect.addEventListener("change", () => {
      const edgeIndex = Number(edgeSelect.value);
      renderEdgeForm(edgeIndex);
      if (state.activeRewireEdgeIndex !== null) {
        state.activeRewireEdgeIndex = edgeIndex;
      }
      updateConnectionModeLabel();
      updateRewireButton();
      renderSelectionSummary();
      renderGraph();
    });
    window.addEventListener("pointermove", handleGlobalPointerMove);
    window.addEventListener("pointerup", handleGlobalPointerUp);
    window.addEventListener("resize", renderGraph);
    updateConnectionModeLabel();
    updateRewireButton();
    renderSelectionSummary();
    loadWorkflow();
  </script>
</body>
</html>
"""
