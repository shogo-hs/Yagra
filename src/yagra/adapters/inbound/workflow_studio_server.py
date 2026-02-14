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
    """Workflow Studio の最小 UI HTML を返す。"""
    return """<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Yagra Workflow Studio</title>
  <style>
    :root {
      --bg: #f4f7fb;
      --panel: #ffffff;
      --line: #d5deea;
      --text: #1d2735;
      --muted: #5d6d84;
      --accent: #0a6fd8;
      --danger: #c62828;
    }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: "Noto Sans JP", "Hiragino Kaku Gothic ProN", sans-serif; background: var(--bg); color: var(--text); }
    .page { max-width: 1280px; margin: 0 auto; padding: 20px; }
    .header { background: linear-gradient(140deg, #ffffff 10%, #ecf4ff 100%); border: 1px solid var(--line); border-radius: 12px; padding: 16px; }
    h1 { margin: 0 0 8px; font-size: clamp(22px, 3vw, 30px); }
    .muted { color: var(--muted); font-size: 13px; }
    .toolbar { margin-top: 12px; display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
    button { border: 1px solid #0b63be; background: var(--accent); color: #fff; border-radius: 8px; padding: 7px 12px; font-weight: 700; cursor: pointer; }
    button.secondary { background: #fff; color: var(--accent); }
    input[type="text"] { border: 1px solid var(--line); border-radius: 8px; padding: 7px 10px; min-width: 320px; }
    .layout { margin-top: 14px; display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
    .panel { background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 12px; }
    h2 { margin: 0 0 8px; font-size: 18px; }
    textarea, pre { width: 100%; min-height: 260px; border: 1px solid var(--line); border-radius: 10px; padding: 10px; font-size: 12px; line-height: 1.45; background: #fff; }
    pre { overflow: auto; white-space: pre-wrap; }
    .danger { color: var(--danger); font-weight: 700; }
    .ok { color: #2e7d32; font-weight: 700; }
    .stack { display: grid; gap: 14px; }
    @media (max-width: 960px) { .layout { grid-template-columns: 1fr; } input[type="text"] { min-width: 0; width: 100%; } }
  </style>
</head>
<body>
  <div class="page">
    <section class="header">
      <h1>Yagra Workflow Studio</h1>
      <div class="muted">M-07 baseline: diff / save / rollback</div>
      <div class="toolbar">
        <button id="loadBtn">Load</button>
        <button id="diffBtn" class="secondary">Preview Diff</button>
        <button id="saveBtn">Save</button>
        <input id="backupIdInput" type="text" placeholder="rollback backup_id" />
        <button id="rollbackBtn" class="secondary">Rollback</button>
      </div>
      <div class="muted" id="revisionLabel">revision: -</div>
      <div class="muted" id="statusLabel">status: idle</div>
    </section>
    <section class="layout">
      <article class="panel stack">
        <div>
          <h2>Workflow (JSON)</h2>
          <textarea id="workflowEditor"></textarea>
        </div>
        <div>
          <h2>UI State (JSON)</h2>
          <textarea id="uiStateEditor"></textarea>
        </div>
      </article>
      <article class="panel stack">
        <div>
          <h2>Validation</h2>
          <pre id="validationView"></pre>
        </div>
        <div>
          <h2>Diff</h2>
          <pre id="diffView"></pre>
        </div>
      </article>
    </section>
  </div>
  <script>
    const state = { revision: null };
    const workflowEditor = document.getElementById("workflowEditor");
    const uiStateEditor = document.getElementById("uiStateEditor");
    const validationView = document.getElementById("validationView");
    const diffView = document.getElementById("diffView");
    const revisionLabel = document.getElementById("revisionLabel");
    const statusLabel = document.getElementById("statusLabel");
    const backupIdInput = document.getElementById("backupIdInput");

    function setStatus(message, isError = false) {
      statusLabel.textContent = `status: ${message}`;
      statusLabel.className = isError ? "danger" : "ok";
    }

    function parseJsonEditor(el, label) {
      try {
        const value = el.value.trim();
        if (!value) return {};
        const parsed = JSON.parse(value);
        if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
          throw new Error("must be object");
        }
        return parsed;
      } catch (err) {
        throw new Error(`${label} is invalid JSON object: ${err.message}`);
      }
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

    async function loadWorkflow() {
      setStatus("loading...");
      const res = await fetch("/api/workflow");
      const data = await res.json();
      if (!res.ok) {
        setStatus(data.message || data.error || "load failed", true);
        return;
      }
      workflowEditor.value = JSON.stringify(data.workflow || {}, null, 2);
      uiStateEditor.value = JSON.stringify(data.ui_state || {}, null, 2);
      state.revision = data.revision;
      revisionLabel.textContent = `revision: ${state.revision}`;
      renderValidation(data.validation_report);
      diffView.textContent = "";
      setStatus("loaded");
    }

    async function previewDiff() {
      if (!state.revision) {
        setStatus("load first", true);
        return;
      }
      let workflow;
      let uiState;
      try {
        workflow = parseJsonEditor(workflowEditor, "workflow");
        uiState = parseJsonEditor(uiStateEditor, "ui_state");
      } catch (err) {
        setStatus(err.message, true);
        return;
      }
      setStatus("diffing...");
      const res = await fetch("/api/workflow/diff", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ workflow, ui_state: uiState, base_revision: state.revision }),
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
      renderValidation(data.validation_report);
      const summary = data.summary || {};
      const lines = [
        `summary: total=${summary.total || 0}, nodes=${summary.nodes || 0}, edges=${summary.edges || 0}, params=${summary.params || 0}, ui_state=${summary.ui_state || 0}, other=${summary.other || 0}`,
        "",
        "yaml diff:",
        data.yaml_unified_diff || "(no yaml changes)",
      ];
      diffView.textContent = lines.join("\\n");
      setStatus("diff ready");
    }

    async function saveWorkflow() {
      if (!state.revision) {
        setStatus("load first", true);
        return;
      }
      let workflow;
      let uiState;
      try {
        workflow = parseJsonEditor(workflowEditor, "workflow");
        uiState = parseJsonEditor(uiStateEditor, "ui_state");
      } catch (err) {
        setStatus(err.message, true);
        return;
      }
      setStatus("saving...");
      const res = await fetch("/api/workflow/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ workflow, ui_state: uiState, base_revision: state.revision }),
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
    document.getElementById("diffBtn").addEventListener("click", previewDiff);
    document.getElementById("saveBtn").addEventListener("click", saveWorkflow);
    document.getElementById("rollbackBtn").addEventListener("click", rollbackWorkflow);
    loadWorkflow();
  </script>
</body>
</html>
"""
