"""Workflow Studio 用のローカル HTTP サーバーを提供する。"""

from __future__ import annotations

import json
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from os import PathLike
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from yagra.application.services import (
    StudioService,
    StudioSessionConfig,
)
from yagra.ports.inbound import (
    StudioBadRequestError,
    StudioConflictError,
    StudioNotFoundError,
    StudioPort,
    StudioUnprocessableEntityError,
)


def create_workflow_studio_server(
    workflow_path: str | PathLike[str] | None = None,
    bundle_root: str | PathLike[str] | None = None,
    ui_state_path: str | PathLike[str] | None = None,
    workspace_root: str | PathLike[str] | None = None,
    backup_dir: str | PathLike[str] = ".yagra/backups",
    host: str = "127.0.0.1",
    port: int = 8787,
) -> ThreadingHTTPServer:
    """Workflow Studio ローカルサーバーを生成する。

    Args:
        workflow_path: 編集対象 workflow パス。未指定時は UI ランチャーから選択/作成する。
        bundle_root: 分割参照解決の基準ディレクトリ。
        ui_state_path: UI サイドカーパス。
        workspace_root: workflow 探索/作成を許可するワークスペースルート。
        backup_dir: バックアップ格納ディレクトリ。
        host: バインドホスト。
        port: バインドポート。

    Returns:
        設定済み `ThreadingHTTPServer`。
    """
    workflow_abspath = (
        Path(workflow_path).expanduser().resolve() if workflow_path is not None else None
    )
    bundle_root_path = Path(bundle_root).expanduser().resolve() if bundle_root is not None else None
    ui_state_override = (
        Path(ui_state_path).expanduser().resolve() if ui_state_path is not None else None
    )
    ui_state_abspath = (
        ui_state_override
        if workflow_abspath is not None and ui_state_override is not None
        else workflow_abspath.with_suffix(".workflow-ui.json")
        if workflow_abspath is not None
        else None
    )
    workspace_root_path = (
        Path(workspace_root).expanduser().resolve()
        if workspace_root is not None
        else workflow_abspath.parent
        if workflow_abspath is not None
        else Path.cwd().resolve()
    )
    backup_dir_path = Path(backup_dir).expanduser().resolve()

    config = StudioSessionConfig(
        workflow_path=workflow_abspath,
        bundle_root=bundle_root_path,
        ui_state_path=ui_state_abspath,
        ui_state_override=ui_state_override,
        workspace_root=workspace_root_path,
        backup_dir=backup_dir_path,
    )
    studio_service = StudioService(config=config)
    handler_class = _build_handler_class(studio_service)
    return ThreadingHTTPServer((host, port), handler_class)


def _build_handler_class(
    studio: StudioPort,
) -> type[BaseHTTPRequestHandler]:
    """設定を閉じ込めた HTTP Handler クラスを生成する。

    Args:
        studio: Studio inbound port 実装。

    Returns:
        `BaseHTTPRequestHandler` 派生クラス。
    """

    class WorkflowStudioHandler(BaseHTTPRequestHandler):
        """Workflow Studio API のリクエストを処理する。"""

        _studio = studio

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
            """標準出力ログを抑制する。"""
            _ = (format, args)

        def do_GET(self) -> None:  # noqa: N802
            """GET リクエストを処理する。"""
            path = urlparse(self.path).path
            if path == "/":
                self._write_html(_studio_html())
                return
            if path == "/api/studio/target":
                self._handle_get_studio_target()
                return
            if path == "/api/studio/files":
                self._handle_get_studio_files()
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
            if path == "/api/workflow/catalogs/preview":
                self._handle_catalog_preview(body)
                return
            if path == "/api/workflow/save":
                self._handle_save(body)
                return
            if path == "/api/workflow/rollback":
                self._handle_rollback(body)
                return
            if path == "/api/studio/open":
                self._handle_open_studio_target(body)
                return
            if path == "/api/studio/create":
                self._handle_create_studio_target(body)
                return
            if path == "/api/studio/file/read":
                self._handle_read_studio_yaml_file(body)
                return
            if path == "/api/studio/file/save":
                self._handle_save_studio_yaml_file(body)
                return

            self._write_json(404, {"error": "not_found"})

        def _handle_get_studio_target(self) -> None:
            """Studio の現在ターゲット情報を返す。"""
            payload = self._execute_studio_call(self._studio.get_studio_target)
            if payload is not None:
                self._write_json(200, payload)

        def _handle_get_studio_files(self) -> None:
            """ワークスペース配下の workflow 候補一覧を返す。"""
            payload = self._execute_studio_call(self._studio.get_studio_files)
            if payload is not None:
                self._write_json(200, payload)

        def _handle_open_studio_target(self, body: dict[str, Any]) -> None:
            """既存 workflow を Studio 編集対象として開く。"""
            payload = self._execute_studio_call(lambda: self._studio.open_studio_target(body))
            if payload is not None:
                self._write_json(200, payload)

        def _handle_create_studio_target(self, body: dict[str, Any]) -> None:
            """新規 workflow を作成して Studio 編集対象として開く。"""
            payload = self._execute_studio_call(lambda: self._studio.create_studio_target(body))
            if payload is not None:
                self._write_json(200, payload)

        def _handle_read_studio_yaml_file(self, body: dict[str, Any]) -> None:
            """ワークスペース配下の YAML ファイル内容を返す。"""
            payload = self._execute_studio_call(lambda: self._studio.read_studio_yaml_file(body))
            if payload is not None:
                self._write_json(200, payload)

        def _handle_save_studio_yaml_file(self, body: dict[str, Any]) -> None:
            """ワークスペース配下の YAML ファイルを作成・更新する。"""
            payload = self._execute_studio_call(lambda: self._studio.save_studio_yaml_file(body))
            if payload is not None:
                self._write_json(200, payload)

        def _handle_get_workflow(self) -> None:
            """現在の workflow を返す。"""
            payload = self._execute_studio_call(self._studio.get_workflow)
            if payload is not None:
                self._write_json(200, payload)

        def _handle_get_form(self) -> None:
            """フォーム編集向けの workflow 表示情報を返す。"""
            payload = self._execute_studio_call(self._studio.get_form)
            if payload is not None:
                self._write_json(200, payload)

        def _handle_diff(self, body: dict[str, Any]) -> None:
            """編集案の差分を返す。"""
            payload = self._execute_studio_call(lambda: self._studio.diff(body))
            if payload is not None:
                self._write_json(200, payload)

        def _handle_form_preview(self, body: dict[str, Any]) -> None:
            """フォーム編集入力から差分プレビューを返す。"""
            payload = self._execute_studio_call(lambda: self._studio.form_preview(body))
            if payload is not None:
                self._write_json(200, payload)

        def _handle_catalog_preview(self, body: dict[str, Any]) -> None:
            """Workflow の catalog 設定プレビューを返す。"""
            payload = self._execute_studio_call(lambda: self._studio.catalog_preview(body))
            if payload is not None:
                self._write_json(200, payload)

        def _handle_save(self, body: dict[str, Any]) -> None:
            """編集案を保存する。"""
            payload = self._execute_studio_call(lambda: self._studio.save(body))
            if payload is not None:
                self._write_json(200, payload)

        def _handle_rollback(self, body: dict[str, Any]) -> None:
            """バックアップIDを指定して復元する。"""
            payload = self._execute_studio_call(lambda: self._studio.rollback(body))
            if payload is not None:
                self._write_json(200, payload)

        def _execute_studio_call(
            self,
            operation: Callable[[], dict[str, Any]],
        ) -> dict[str, Any] | None:
            """Studio サービス呼び出しを実行し、エラーを HTTP 応答へ変換する。"""
            try:
                return operation()
            except StudioBadRequestError as exc:
                self._write_json(400, exc.to_payload())
            except StudioNotFoundError as exc:
                self._write_json(404, exc.to_payload())
            except StudioConflictError as exc:
                self._write_json(409, exc.to_payload())
            except StudioUnprocessableEntityError as exc:
                self._write_json(422, exc.to_payload())
            return None

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


def _studio_html() -> str:
    """Workflow Studio のフォーム編集 UI HTML を返す。"""
    return """<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Yagra Workflow Studio</title>
  <link
    rel="stylesheet"
    href="https://cdn.jsdelivr.net/npm/@vue-flow/core@1.48.2/dist/style.css"
  />
  <link
    rel="stylesheet"
    href="https://cdn.jsdelivr.net/npm/@vue-flow/core@1.48.2/dist/theme-default.css"
  />
  <link
    rel="stylesheet"
    href="https://cdn.jsdelivr.net/npm/@vue-flow/minimap@1.5.4/dist/style.css"
  />
  <link
    rel="stylesheet"
    href="https://cdn.jsdelivr.net/npm/@vue-flow/controls@1.1.3/dist/style.css"
  />
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
    * {
      box-sizing: border-box;
    }
    body {
      margin: 0;
      font-family: "Noto Sans JP", "Hiragino Kaku Gothic ProN", sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.45;
    }
    .page {
      max-width: 1640px;
      margin: 0 auto;
      padding: 18px;
      display: grid;
      gap: 14px;
    }
    .header {
      background: linear-gradient(145deg, #ffffff 10%, #eaf3ff 100%);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 16px;
    }
    h1 {
      margin: 0 0 8px;
      font-size: clamp(21px, 3vw, 30px);
    }
    h2 {
      margin: 0;
      font-size: 17px;
    }
    .muted {
      color: var(--muted);
      font-size: 13px;
    }
    .toolbar {
      margin-top: 12px;
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
    }
    .meta-line {
      margin-top: 8px;
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      align-items: center;
    }
    button {
      border: 1px solid #0b63be;
      background: var(--accent);
      color: #fff;
      border-radius: 9px;
      padding: 8px 12px;
      font-weight: 700;
      cursor: pointer;
    }
    button.secondary {
      background: #fff;
      color: var(--accent);
    }
    input[type="text"], select, textarea {
      border: 1px solid var(--line);
      border-radius: 9px;
      padding: 8px 10px;
      width: 100%;
      font-size: 13px;
      background: #fff;
      color: var(--text);
      font-family: inherit;
    }
    textarea {
      min-height: 94px;
      line-height: 1.42;
      resize: vertical;
    }
    .main {
      display: grid;
      grid-template-columns: 1fr 380px;
      gap: 14px;
      align-items: start;
    }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 12px;
    }
    .canvas-panel {
      min-height: 700px;
      display: grid;
      gap: 10px;
    }
    .flow-shell {
      border: 1px solid var(--line);
      border-radius: 10px;
      overflow: hidden;
      min-height: 620px;
      background: linear-gradient(180deg, #fcfeff 0%, #f2f8ff 100%);
    }
    .workflow-flow {
      width: 100%;
      height: 620px;
    }
    .section-head {
      display: grid;
      gap: 4px;
    }
    .side-panel {
      display: grid;
      gap: 12px;
      position: sticky;
      top: 10px;
      max-height: calc(100vh - 32px);
      overflow: auto;
    }
    .side-section {
      display: grid;
      gap: 8px;
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 10px;
      background: #fbfdff;
    }
    .field {
      display: grid;
      gap: 4px;
    }
    .field label {
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
    }
    .inline-row {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
    }
    .check-list {
      display: grid;
      gap: 6px;
      max-height: 150px;
      overflow: auto;
      border: 1px solid #e0e8f4;
      border-radius: 8px;
      padding: 8px;
      background: #fff;
    }
    .check-item {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 12px;
      color: #2f4769;
    }
    .hint {
      font-size: 12px;
      color: var(--muted);
    }
    .mono {
      font-family: "Menlo", "Monaco", "Consolas", monospace;
      font-size: 12px;
      line-height: 1.5;
      color: #2f4769;
      word-break: break-all;
    }
    .lower {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 14px;
    }
    pre {
      width: 100%;
      min-height: 170px;
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 10px;
      font-size: 12px;
      line-height: 1.45;
      background: #fff;
      overflow: auto;
      white-space: pre-wrap;
      margin: 8px 0 0;
    }
    .danger {
      color: var(--danger);
      font-weight: 700;
    }
    .ok {
      color: var(--ok);
      font-weight: 700;
    }
    .workflow-node {
      position: relative;
      min-width: 180px;
      max-width: 440px;
      padding: 8px 14px;
      border: 1px solid #8ea8cc;
      border-radius: 10px;
      background: #fff;
      box-shadow: 0 2px 7px rgba(35, 70, 120, 0.14);
      white-space: normal;
      overflow-wrap: anywhere;
      word-break: break-word;
    }
    .workflow-node.is-start {
      border-color: #5d94d6;
    }
    .workflow-node.is-end {
      border-color: #d89f6f;
    }
    .workflow-node.selected {
      border-color: #0b63be;
      box-shadow: 0 4px 11px rgba(10, 111, 216, 0.24);
    }
    .workflow-node-role {
      display: flex;
      gap: 4px;
      margin-bottom: 4px;
    }
    .role-pill {
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      font-size: 10px;
      font-weight: 800;
      letter-spacing: 0.04em;
      line-height: 1;
      padding: 3px 7px;
      border: 1px solid transparent;
    }
    .role-pill.start {
      background: #e8f1ff;
      color: #0a4a92;
      border-color: #afc9ec;
    }
    .role-pill.end {
      background: #ffeede;
      color: #8f3f04;
      border-color: #ecbb96;
    }
    .workflow-node-id {
      font-size: 12px;
      font-weight: 800;
      margin-bottom: 3px;
      line-height: 1.35;
      overflow-wrap: anywhere;
    }
    .workflow-node-handler {
      font-size: 12px;
      color: #2f4769;
      line-height: 1.4;
      overflow-wrap: anywhere;
    }
    .node-handle {
      width: 9px;
      height: 9px;
      border: 1px solid #0b63be;
      background: #ffffff;
      opacity: 0;
      transition: opacity 120ms ease;
    }
    .node-handle-top,
    .node-handle-bottom {
      border-color: #c2793b;
      background: #fff7f0;
    }
    .workflow-node:hover .node-handle,
    .workflow-node.selected .node-handle,
    .page.is-connecting .node-handle {
      opacity: 1;
    }
    .launcher-panel {
      display: grid;
      gap: 12px;
    }
    .launcher-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
    }
    .launcher-box {
      display: grid;
      gap: 8px;
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 12px;
      background: #fbfdff;
    }
    @media (max-width: 1320px) {
      .main {
        grid-template-columns: 1fr;
      }
      .side-panel {
        position: static;
        max-height: none;
      }
      .lower {
        grid-template-columns: 1fr;
      }
      .launcher-grid {
        grid-template-columns: 1fr;
      }
    }
  </style>
</head>
<body>
  <div id="app" class="page" :class="{ 'is-connecting': isConnecting }">
    <section class="header">
      <h1>Yagra Workflow Studio</h1>
      <div class="muted">Vue 3 + Vue Flow (CDN / ES Modules / no-build)</div>
      <div class="toolbar">
        <template v-if="hasTarget">
          <button type="button" @click="loadWorkflow">Load</button>
          <button type="button" class="secondary" @click="previewDiff">Preview Diff</button>
          <button type="button" @click="saveWorkflow">Save</button>
          <input
            v-model.trim="backupId"
            type="text"
            placeholder="rollback backup_id"
            style="max-width: 360px;"
          />
          <button type="button" class="secondary" @click="rollbackWorkflow">Rollback</button>
          <button type="button" class="secondary" @click="openLauncher">Change Target</button>
        </template>
        <template v-else>
          <button type="button" @click="refreshStudioFiles">Refresh Files</button>
        </template>
      </div>
      <div class="meta-line">
        <span class="muted">target: {{ studioTargetPath || "-" }}</span>
        <span class="muted">revision: {{ revision || "-" }}</span>
        <span :class="statusClass">status: {{ status.message }}</span>
      </div>
    </section>

    <section v-if="showLauncher || !hasTarget" class="panel launcher-panel">
      <div class="launcher-grid">
        <article class="launcher-box">
          <h2>Open Existing Workflow</h2>
          <div class="hint">workspace_root: <span class="mono">{{ studioWorkspaceRoot || "-" }}</span></div>
          <div class="field">
            <label for="openWorkflowSelect">workflow</label>
            <select id="openWorkflowSelect" v-model="launcher.openWorkflowPath">
              <option value="">(select workflow)</option>
              <option v-for="path in workflowCandidates" :key="'wf-' + path" :value="path">
                {{ path }}
              </option>
            </select>
          </div>
          <div class="toolbar">
            <button type="button" @click="openStudioTarget">Open</button>
            <button type="button" class="secondary" @click="refreshStudioFiles">Refresh List</button>
          </div>
        </article>

        <article class="launcher-box">
          <h2>Create Workflow</h2>
          <div class="field">
            <label for="createWorkflowPathInput">workflow path (workspace relative)</label>
            <input
              id="createWorkflowPathInput"
              v-model.trim="launcher.createWorkflowPath"
              type="text"
              placeholder="workflows/new-workflow.yaml"
            />
          </div>
          <label class="check-item">
            <input v-model="launcher.overwrite" type="checkbox" />
            <span>既存 workflow を上書きする（overwrite）</span>
          </label>
          <div class="toolbar">
            <button type="button" @click="createStudioTarget">Create And Open</button>
          </div>
        </article>
      </div>
      <div v-if="hasTarget && showLauncher" class="toolbar">
        <button type="button" class="secondary" @click="closeLauncher">Cancel</button>
      </div>
    </section>

    <template v-if="hasTarget && !showLauncher">
      <section class="main">
        <article class="panel canvas-panel">
          <div class="section-head">
            <h2>Graph Canvas</h2>
            <div class="hint">
              ノードをクリックすると右サイドバーに編集フォームが表示されます。通常は右→左、戻りループは下→上ハンドルで接続できます。
            </div>
          </div>
          <div class="flow-shell">
            <vue-flow
              v-model:nodes="nodes"
              v-model:edges="edges"
              class="workflow-flow"
              :node-types="nodeTypes"
              :default-edge-options="defaultEdgeOptions"
              :nodes-draggable="true"
              :nodes-connectable="true"
              :elements-selectable="true"
              :pan-on-drag="true"
              :pan-on-scroll="true"
              :zoom-on-scroll="true"
              :fit-view-on-init="true"
              :min-zoom="0.2"
              :max-zoom="2.2"
              :edges-updatable="true"
              :apply-default="false"
              @nodes-change="onNodesChange"
              @edges-change="onEdgesChange"
              @connect="onConnect"
              @connect-start="onConnectStart"
              @connect-end="onConnectEnd"
              @node-click="onNodeClick"
              @edge-click="onEdgeClick"
              @edge-update="onEdgeUpdate"
              @pane-click="onPaneClick"
            >
              <template #node-workflow="nodeProps">
                <workflow-node v-bind="nodeProps"></workflow-node>
              </template>
              <mini-map></mini-map>
              <flow-controls></flow-controls>
              <flow-background pattern-color="#d5e1f0" :gap="18" :size="1"></flow-background>
            </vue-flow>
          </div>
        </article>

        <aside class="panel side-panel">
          <section class="side-section">
            <h2>Workflow Settings</h2>
            <div class="field">
              <label for="workflowVersionInput">version</label>
              <input id="workflowVersionInput" v-model="workflowMeta.version" type="text" placeholder="1.0" />
            </div>
            <div class="field">
              <label for="workflowStartAtInput">start_at</label>
              <select id="workflowStartAtInput" v-model="workflowMeta.startAt" @change="onWorkflowMetaChange">
                <option value="">(select node)</option>
                <option v-for="nodeId in nodeIdOptions" :key="'start-' + nodeId" :value="nodeId">
                  {{ nodeId }}
                </option>
              </select>
            </div>
            <div class="field">
              <label>end_at</label>
              <div v-if="nodeIdOptions.length === 0" class="hint">
                先にノードを追加してください。
              </div>
              <div v-else class="check-list">
                <label v-for="nodeId in nodeIdOptions" :key="'end-' + nodeId" class="check-item">
                  <input
                    type="checkbox"
                    :value="nodeId"
                    v-model="workflowMeta.endAt"
                    @change="onWorkflowMetaChange"
                  />
                  <span>{{ nodeId }}</span>
                </label>
              </div>
            </div>
            <div class="hint">`start_at` と `end_at` は保存時に workflow へ反映されます。</div>
          </section>

          <section class="side-section">
            <h2>Add Node</h2>
            <div class="inline-row">
              <div class="field">
                <label for="newNodeId">node id</label>
                <input id="newNodeId" v-model.trim="newNode.id" type="text" placeholder="review" />
              </div>
              <div class="field">
                <label for="newNodeHandler">handler</label>
                <input id="newNodeHandler" v-model.trim="newNode.handler" type="text" placeholder="review_handler" />
              </div>
            </div>
            <button type="button" class="secondary" @click="addNode">Add Node</button>
            <div class="hint">追加後の位置は自動配置されます。必要に応じてキャンバス上でドラッグしてください。</div>
          </section>

          <section class="side-section">
            <h2>Node Properties</h2>
            <div v-if="!selectedNode" class="hint">
              ノードを選択してください。
            </div>
            <template v-else>
              <div class="mono">selected: {{ selectedNode.id }}</div>
              <div class="field">
                <label for="nodeIdInput">node id</label>
                <input id="nodeIdInput" v-model.trim="nodeEditor.id" type="text" />
              </div>
              <div class="field">
                <label for="nodeHandlerInput">handler</label>
                <input id="nodeHandlerInput" v-model="nodeEditor.handler" type="text" />
              </div>
              <div class="field">
                <label for="nodePromptFileSelect">prompt yaml</label>
                <select
                  id="nodePromptFileSelect"
                  v-model="nodeEditor.promptFilePath"
                  @change="onNodePromptFileChange"
                >
                  <option value="">(auto create on Apply)</option>
                  <option v-for="path in yamlFiles" :key="'node-yaml-' + path" :value="path">
                    {{ path }}
                  </option>
                </select>
              </div>
              <div class="inline-row">
                <div class="field">
                  <label for="nodePromptRefInput">prompt_ref</label>
                  <input
                    id="nodePromptRefInput"
                    v-model="nodeEditor.promptRef"
                    type="text"
                    placeholder="prompts/review.yaml#intent"
                  />
                </div>
              </div>
              <div v-if="nodeEditor.promptFileParseError" class="hint danger">
                {{ nodeEditor.promptFileParseError }}
              </div>
              <div class="field">
                <label for="nodePromptSystemInput">system prompt</label>
                <textarea
                  id="nodePromptSystemInput"
                  v-model="nodeEditor.promptSystem"
                  placeholder="You are a helpful assistant..."
                ></textarea>
              </div>
              <div class="field">
                <label for="nodePromptUserInput">user prompt</label>
                <textarea
                  id="nodePromptUserInput"
                  v-model="nodeEditor.promptUser"
                  placeholder="{{input}}"
                ></textarea>
              </div>
              <div class="field">
                <label>Model Settings</label>
                <div class="inline-row">
                  <input
                    id="nodeModelProviderInput"
                    v-model.trim="nodeEditor.modelProvider"
                    type="text"
                    placeholder="provider (e.g. openai)"
                  />
                  <input
                    id="nodeModelNameInput"
                    v-model.trim="nodeEditor.modelName"
                    type="text"
                    placeholder="name (e.g. gpt-4.1-mini)"
                  />
                </div>
              </div>
              <div class="field">
                <label>Model Runtime Params</label>
                <div class="inline-row">
                  <input
                    id="nodeModelTemperatureInput"
                    v-model.trim="nodeEditor.temperature"
                    type="text"
                    placeholder="temperature (e.g. 0.2)"
                  />
                  <input
                    id="nodeModelTopPInput"
                    v-model.trim="nodeEditor.topP"
                    type="text"
                    placeholder="top_p (e.g. 0.9)"
                  />
                </div>
                <div class="field">
                  <input
                    id="nodeModelMaxTokensInput"
                    v-model.trim="nodeEditor.maxTokens"
                    type="text"
                    placeholder="max_tokens (e.g. 512)"
                  />
                </div>
              </div>
              <button type="button" class="secondary" @click="applyNodeEdit">Apply Node Edit</button>
              <div class="hint">node id は空文字/重複不可です。prompt yaml 未選択で Apply すると `prompts/` 配下へ自動作成されます。</div>
            </template>
          </section>

          <section class="side-section">
            <h2>Edge Properties</h2>
            <div v-if="!selectedEdge" class="hint">
              エッジを選択すると condition を編集できます。エッジ端点をドラッグすると再接続できます。
            </div>
            <template v-else>
              <div class="mono">
                edge[{{ selectedEdge.data.index }}] {{ selectedEdge.source }} -> {{ selectedEdge.target }}
                <span v-if="selectedEdge.data.isLoopEdge"> (loop)</span>
              </div>
              <div class="field">
                <label for="edgeConditionInput">condition</label>
                <input id="edgeConditionInput" v-model="edgeEditor.condition" type="text" placeholder="retry / done" />
              </div>
              <button type="button" class="secondary" @click="applyEdgeEdit">Apply Edge Edit</button>
            </template>
          </section>

        </aside>
      </section>

      <section class="lower">
        <article class="panel">
          <h2>Validation</h2>
          <pre>{{ validationText }}</pre>
        </article>
        <article class="panel">
          <h2>Diff</h2>
          <pre>{{ diffText }}</pre>
        </article>
      </section>
    </template>
  </div>

  <script type="importmap">
    {
      "imports": {
        "vue": "https://cdn.jsdelivr.net/npm/vue@3.5.28/dist/vue.esm-browser.prod.js",
        "@vue-flow/core": "https://cdn.jsdelivr.net/npm/@vue-flow/core@1.48.2/dist/vue-flow-core.mjs",
        "@vue-flow/minimap": "https://cdn.jsdelivr.net/npm/@vue-flow/minimap@1.5.4/dist/vue-flow-minimap.mjs",
        "@vue-flow/controls": "https://cdn.jsdelivr.net/npm/@vue-flow/controls@1.1.3/dist/vue-flow-controls.mjs",
        "@vue-flow/background": "https://cdn.jsdelivr.net/npm/@vue-flow/background@1.3.2/dist/vue-flow-background.mjs"
      }
    }
  </script>
  <script>
    window.process = window.process || { env: { NODE_ENV: "production" } };
  </script>
  <script type="module">
    import { createApp, computed, onMounted, reactive, ref, watch } from "vue";
    import {
      VueFlow,
      Handle,
      Position,
      applyEdgeChanges,
      applyNodeChanges,
    } from "@vue-flow/core";
    import { MiniMap } from "@vue-flow/minimap";
    import { Controls as FlowControls } from "@vue-flow/controls";
    import { Background as FlowBackground } from "@vue-flow/background";

    const WorkflowNode = {
      name: "WorkflowNode",
      components: { Handle },
      props: {
        data: { type: Object, required: true },
        selected: { type: Boolean, default: false },
      },
      setup() {
        return { Position };
      },
      template: `
        <div class="workflow-node" :class="{ selected, 'is-start': data.isStart, 'is-end': data.isEnd }">
          <Handle id="left-in" type="target" :position="Position.Left" class="node-handle" />
          <Handle id="top-in" type="target" :position="Position.Top" class="node-handle node-handle-top" />
          <div v-if="data.isStart || data.isEnd" class="workflow-node-role">
            <span v-if="data.isStart" class="role-pill start">START</span>
            <span v-if="data.isEnd" class="role-pill end">END</span>
          </div>
          <div class="workflow-node-id">{{ data.id }}</div>
          <div class="workflow-node-handler">{{ data.handler || "(no handler)" }}</div>
          <Handle id="right-out" type="source" :position="Position.Right" class="node-handle" />
          <Handle id="bottom-out" type="source" :position="Position.Bottom" class="node-handle node-handle-bottom" />
        </div>
      `,
    };

    function isRecord(value) {
      return typeof value === "object" && value !== null && !Array.isArray(value);
    }

    function deepClone(value) {
      return JSON.parse(JSON.stringify(value));
    }

    function normalizeText(value) {
      if (value === null || value === undefined) return "";
      return String(value).trim();
    }

    function normalizeNodeIdList(value) {
      if (typeof value === "string") {
        const text = normalizeText(value);
        return text ? [text] : [];
      }
      if (!Array.isArray(value)) return [];
      const ids = [];
      for (const item of value) {
        if (typeof item !== "string") continue;
        const text = normalizeText(item);
        if (text) {
          ids.push(text);
        }
      }
      return ids;
    }

    function defaultNodePosition(index) {
      const columns = 4;
      const col = index % columns;
      const row = Math.floor(index / columns);
      return {
        x: 70 + col * 270,
        y: 70 + row * 170,
      };
    }

    function edgeLabel(index, condition) {
      void index;
      const text = normalizeText(condition);
      return text || "";
    }

    function edgeDirectionKey(source, target) {
      return `${source}=>${target}`;
    }

    function edgePairKey(source, target) {
      return source <= target ? `${source}<=>${target}` : `${target}<=>${source}`;
    }

    function isRetryLikeCondition(condition) {
      const text = normalizeText(condition).toLowerCase();
      if (!text) {
        return false;
      }
      const keywords = [
        "retry",
        "re-try",
        "re_try",
        "loop",
        "again",
        "redo",
        "replan",
        "back",
        "リトライ",
        "再試行",
        "やり直し",
      ];
      return keywords.some(keyword => text.includes(keyword));
    }

    function compareLoopPriority(left, right) {
      if (left.retryLike !== right.retryLike) {
        return left.retryLike ? 1 : -1;
      }
      if (left.hasCondition !== right.hasCondition) {
        return left.hasCondition ? 1 : -1;
      }
      if (left.index !== right.index) {
        return left.index > right.index ? 1 : -1;
      }
      return 0;
    }

    function buildLoopEdgeKeySet(edgeItems) {
      const normalizedItems = edgeItems
        .map((item, fallbackIndex) => {
          if (
            !item
            || typeof item.key !== "string"
            || typeof item.source !== "string"
            || typeof item.target !== "string"
          ) {
            return null;
          }
          const condition = normalizeText(item.condition);
          const index = Number.isInteger(item.index) ? item.index : fallbackIndex;
          return {
            key: item.key,
            source: item.source,
            target: item.target,
            index,
            condition,
            hasCondition: Boolean(condition),
            retryLike: isRetryLikeCondition(condition),
          };
        })
        .filter(Boolean);

      const loopKeys = new Set();
      const pairGroups = new Map();

      for (const item of normalizedItems) {
        if (item.source === item.target) {
          loopKeys.add(item.key);
          continue;
        }
        const pairKey = edgePairKey(item.source, item.target);
        if (!pairGroups.has(pairKey)) {
          pairGroups.set(pairKey, []);
        }
        pairGroups.get(pairKey).push(item);
      }

      for (const groupItems of pairGroups.values()) {
        const directionMap = new Map();
        for (const item of groupItems) {
          const directionKey = edgeDirectionKey(item.source, item.target);
          if (!directionMap.has(directionKey)) {
            directionMap.set(directionKey, []);
          }
          directionMap.get(directionKey).push(item);
        }
        if (directionMap.size < 2) {
          continue;
        }

        const directionLeaders = [];
        for (const directionItems of directionMap.values()) {
          let leader = directionItems[0];
          for (const candidate of directionItems.slice(1)) {
            if (compareLoopPriority(candidate, leader) > 0) {
              leader = candidate;
            }
          }
          directionLeaders.push(leader);
        }
        if (directionLeaders.length < 2) {
          continue;
        }

        let pairWinner = directionLeaders[0];
        for (const candidate of directionLeaders.slice(1)) {
          if (compareLoopPriority(candidate, pairWinner) > 0) {
            pairWinner = candidate;
          }
        }
        loopKeys.add(pairWinner.key);
      }

      return loopKeys;
    }

    const SOURCE_HANDLE_OPTIONS = ["right-out", "bottom-out"];
    const TARGET_HANDLE_OPTIONS = ["left-in", "top-in"];
    const NODE_WIDTH_ESTIMATE = 220;
    const NODE_HEIGHT_ESTIMATE = 88;
    const EDGE_DETOUR_OFFSET = 48;

    function toFiniteNumber(value, fallback = 0) {
      const num = Number(value);
      return Number.isFinite(num) ? num : fallback;
    }

    function buildNodeMap(nodeItems) {
      const map = new Map();
      for (const node of Array.isArray(nodeItems) ? nodeItems : []) {
        if (!node || typeof node.id !== "string") {
          continue;
        }
        map.set(node.id, node);
      }
      return map;
    }

    function sourceVectorForHandle(handleId) {
      if (handleId === "bottom-out") {
        return { x: 0, y: 1 };
      }
      return { x: 1, y: 0 };
    }

    function targetVectorForHandle(handleId) {
      if (handleId === "top-in") {
        return { x: 0, y: 1 };
      }
      return { x: 1, y: 0 };
    }

    function estimateHandlePoint(nodeLike, handleId) {
      const position = isRecord(nodeLike?.position) ? nodeLike.position : {};
      const baseX = toFiniteNumber(position.x, 0);
      const baseY = toFiniteNumber(position.y, 0);
      const halfW = NODE_WIDTH_ESTIMATE / 2;
      const halfH = NODE_HEIGHT_ESTIMATE / 2;
      if (handleId === "right-out") {
        return { x: baseX + NODE_WIDTH_ESTIMATE, y: baseY + halfH };
      }
      if (handleId === "bottom-out") {
        return { x: baseX + halfW, y: baseY + NODE_HEIGHT_ESTIMATE };
      }
      if (handleId === "top-in") {
        return { x: baseX + halfW, y: baseY };
      }
      return { x: baseX, y: baseY + halfH };
    }

    function estimateNodeRect(nodeLike, margin = 8) {
      const position = isRecord(nodeLike?.position) ? nodeLike.position : {};
      const baseX = toFiniteNumber(position.x, 0);
      const baseY = toFiniteNumber(position.y, 0);
      return {
        left: baseX - margin,
        right: baseX + NODE_WIDTH_ESTIMATE + margin,
        top: baseY - margin,
        bottom: baseY + NODE_HEIGHT_ESTIMATE + margin,
      };
    }

    function segmentIntersectsRect(start, end, rect) {
      const sx = toFiniteNumber(start?.x, 0);
      const sy = toFiniteNumber(start?.y, 0);
      const ex = toFiniteNumber(end?.x, 0);
      const ey = toFiniteNumber(end?.y, 0);
      const epsilon = 1e-6;

      if (Math.abs(sy - ey) <= epsilon) {
        if (sy < rect.top || sy > rect.bottom) {
          return false;
        }
        const minX = Math.min(sx, ex);
        const maxX = Math.max(sx, ex);
        return maxX >= rect.left && minX <= rect.right;
      }

      if (Math.abs(sx - ex) <= epsilon) {
        if (sx < rect.left || sx > rect.right) {
          return false;
        }
        const minY = Math.min(sy, ey);
        const maxY = Math.max(sy, ey);
        return maxY >= rect.top && minY <= rect.bottom;
      }

      const minX = Math.min(sx, ex);
      const maxX = Math.max(sx, ex);
      const minY = Math.min(sy, ey);
      const maxY = Math.max(sy, ey);
      return maxX >= rect.left && minX <= rect.right && maxY >= rect.top && minY <= rect.bottom;
    }

    function countPathOverlappedNodes(pathPoints, nodeMap, sourceId, targetId) {
      let overlaps = 0;
      for (const [nodeId, node] of nodeMap.entries()) {
        if (nodeId === sourceId || nodeId === targetId) {
          continue;
        }
        const rect = estimateNodeRect(node);
        let hit = false;
        for (let index = 0; index < pathPoints.length - 1; index += 1) {
          if (segmentIntersectsRect(pathPoints[index], pathPoints[index + 1], rect)) {
            hit = true;
            break;
          }
        }
        if (hit) {
          overlaps += 1;
        }
      }
      return overlaps;
    }

    function translatePoint(point, vector, distance) {
      return {
        x: toFiniteNumber(point?.x, 0) + toFiniteNumber(vector?.x, 0) * distance,
        y: toFiniteNumber(point?.y, 0) + toFiniteNumber(vector?.y, 0) * distance,
      };
    }

    function buildOrthogonalPathVariants(sourcePoint, targetPoint, sourceHandle, targetHandle) {
      const sourceVector = sourceVectorForHandle(sourceHandle);
      const targetVector = targetVectorForHandle(targetHandle);
      const sourceDetourPoint = translatePoint(sourcePoint, sourceVector, EDGE_DETOUR_OFFSET);
      const targetDetourPoint = translatePoint(targetPoint, targetVector, -EDGE_DETOUR_OFFSET);
      return [
        [
          sourcePoint,
          { x: targetPoint.x, y: sourcePoint.y },
          targetPoint,
        ],
        [
          sourcePoint,
          { x: sourcePoint.x, y: targetPoint.y },
          targetPoint,
        ],
        [
          sourcePoint,
          sourceDetourPoint,
          { x: targetDetourPoint.x, y: sourceDetourPoint.y },
          targetDetourPoint,
          targetPoint,
        ],
        [
          sourcePoint,
          sourceDetourPoint,
          { x: sourceDetourPoint.x, y: targetDetourPoint.y },
          targetDetourPoint,
          targetPoint,
        ],
      ];
    }

    function compareRoutingScore(left, right) {
      if (left.overlaps !== right.overlaps) {
        return left.overlaps - right.overlaps;
      }
      if (left.bends !== right.bends) {
        return left.bends - right.bends;
      }
      if (left.distance !== right.distance) {
        return left.distance - right.distance;
      }
      return 0;
    }

    function evaluateHandlePair(sourceNode, targetNode, sourceHandle, targetHandle, nodeMap, sourceId, targetId) {
      const sourcePoint = estimateHandlePoint(sourceNode, sourceHandle);
      const targetPoint = estimateHandlePoint(targetNode, targetHandle);
      const dx = targetPoint.x - sourcePoint.x;
      const dy = targetPoint.y - sourcePoint.y;

      const sourceVector = sourceVectorForHandle(sourceHandle);
      const targetVector = targetVectorForHandle(targetHandle);

      let bends = 0;
      if (sourceVector.x !== targetVector.x || sourceVector.y !== targetVector.y) {
        bends += 1;
      }
      if (dx * sourceVector.x + dy * sourceVector.y <= 0) {
        bends += 1;
      }
      if (dx * targetVector.x + dy * targetVector.y <= 0) {
        bends += 1;
      }

      const pathVariants = buildOrthogonalPathVariants(sourcePoint, targetPoint, sourceHandle, targetHandle);
      let overlaps = Number.POSITIVE_INFINITY;
      for (const variant of pathVariants) {
        const overlappedNodes = countPathOverlappedNodes(variant, nodeMap, sourceId, targetId);
        if (overlappedNodes < overlaps) {
          overlaps = overlappedNodes;
        }
      }
      if (!Number.isFinite(overlaps)) {
        overlaps = 0;
      }

      return {
        overlaps,
        bends,
        distance: Math.abs(dx) + Math.abs(dy),
      };
    }

    function chooseBestTargetHandle(edge, sourceNode, targetNode, sourceHandle, nodeMap) {
      let bestHandle = TARGET_HANDLE_OPTIONS[0];
      let bestScore = evaluateHandlePair(
        sourceNode,
        targetNode,
        sourceHandle,
        bestHandle,
        nodeMap,
        edge.source,
        edge.target,
      );
      for (const candidate of TARGET_HANDLE_OPTIONS.slice(1)) {
        const score = evaluateHandlePair(
          sourceNode,
          targetNode,
          sourceHandle,
          candidate,
          nodeMap,
          edge.source,
          edge.target,
        );
        if (compareRoutingScore(score, bestScore) < 0) {
          bestHandle = candidate;
          bestScore = score;
        }
      }
      return { targetHandle: bestHandle, score: bestScore };
    }

    function chooseBestRoutingForEdge(edge, nodeMap) {
      const sourceNode = nodeMap.get(edge.source);
      const targetNode = nodeMap.get(edge.target);

      let bestSourceHandle = SOURCE_HANDLE_OPTIONS[0];
      let bestTarget = chooseBestTargetHandle(edge, sourceNode, targetNode, bestSourceHandle, nodeMap);

      for (const sourceHandle of SOURCE_HANDLE_OPTIONS.slice(1)) {
        const targetResult = chooseBestTargetHandle(edge, sourceNode, targetNode, sourceHandle, nodeMap);
        if (compareRoutingScore(targetResult.score, bestTarget.score) < 0) {
          bestSourceHandle = sourceHandle;
          bestTarget = targetResult;
        }
      }

      return {
        sourceHandle: bestSourceHandle,
        targetHandle: bestTarget.targetHandle,
        score: bestTarget.score,
      };
    }

    function chooseBranchSourceHandle(edgeGroup, nodeMap) {
      let bestSourceHandle = SOURCE_HANDLE_OPTIONS[0];
      let bestTotalScore = null;
      let bestTargetByEdge = new Map();

      for (const sourceHandle of SOURCE_HANDLE_OPTIONS) {
        const targetByEdge = new Map();
        let totalOverlaps = 0;
        let totalBends = 0;
        let totalDistance = 0;

        for (const edge of edgeGroup) {
          const sourceNode = nodeMap.get(edge.source);
          const targetNode = nodeMap.get(edge.target);
          const targetResult = chooseBestTargetHandle(edge, sourceNode, targetNode, sourceHandle, nodeMap);
          targetByEdge.set(edge.id, targetResult.targetHandle);
          totalOverlaps += targetResult.score.overlaps;
          totalBends += targetResult.score.bends;
          totalDistance += targetResult.score.distance;
        }

        const totalScore = { overlaps: totalOverlaps, bends: totalBends, distance: totalDistance };
        if (bestTotalScore === null || compareRoutingScore(totalScore, bestTotalScore) < 0) {
          bestSourceHandle = sourceHandle;
          bestTotalScore = totalScore;
          bestTargetByEdge = targetByEdge;
        }
      }

      return {
        sourceHandle: bestSourceHandle,
        score: bestTotalScore || { overlaps: 0, bends: 0, distance: 0 },
        targetByEdge: bestTargetByEdge,
      };
    }

    function computeEdgeGroupScore(routesByEdgeId) {
      let overlaps = 0;
      let bends = 0;
      let distance = 0;
      for (const route of routesByEdgeId.values()) {
        const score = route?.score;
        if (!score) {
          continue;
        }
        overlaps += toFiniteNumber(score.overlaps, 0);
        bends += toFiniteNumber(score.bends, 0);
        distance += toFiniteNumber(score.distance, 0);
      }
      return { overlaps, bends, distance };
    }

    function buildEdgeHandlePlan(edgeItems, nodeMap) {
      const sourceGroups = new Map();
      for (const edge of edgeItems) {
        if (!edge || typeof edge.id !== "string") {
          continue;
        }
        if (!sourceGroups.has(edge.source)) {
          sourceGroups.set(edge.source, []);
        }
        sourceGroups.get(edge.source).push(edge);
      }

      const plan = new Map();
      for (const edgeGroup of sourceGroups.values()) {
        if (edgeGroup.length >= 2) {
          const branchPlan = chooseBranchSourceHandle(edgeGroup, nodeMap);
          const splitRoutes = new Map();
          for (const edge of edgeGroup) {
            splitRoutes.set(edge.id, chooseBestRoutingForEdge(edge, nodeMap));
          }
          const splitScore = computeEdgeGroupScore(splitRoutes);
          const shouldUseSplit =
            branchPlan.score.overlaps > 0
            && compareRoutingScore(splitScore, branchPlan.score) < 0;

          if (shouldUseSplit) {
            for (const edge of edgeGroup) {
              const splitRoute = splitRoutes.get(edge.id);
              if (!splitRoute) {
                continue;
              }
              plan.set(edge.id, {
                sourceHandle: splitRoute.sourceHandle,
                targetHandle: splitRoute.targetHandle,
              });
            }
            continue;
          }

          for (const edge of edgeGroup) {
            plan.set(edge.id, {
              sourceHandle: branchPlan.sourceHandle,
              targetHandle: branchPlan.targetByEdge.get(edge.id) || "left-in",
            });
          }
          continue;
        }

        const edge = edgeGroup[0];
        const route = chooseBestRoutingForEdge(edge, nodeMap);
        plan.set(edge.id, {
          sourceHandle: route.sourceHandle,
          targetHandle: route.targetHandle,
        });
      }

      return plan;
    }

    function normalizeHandleId(value) {
      if (typeof value !== "string") return "";
      return value.trim();
    }

    function resolveEdgeHandles(edgeLike) {
      const defaultSource = "right-out";
      const defaultTarget = "left-in";
      const sourceCandidate = normalizeHandleId(edgeLike?.sourceHandle);
      const targetCandidate = normalizeHandleId(edgeLike?.targetHandle);
      const sourceHandle = SOURCE_HANDLE_OPTIONS.includes(sourceCandidate)
        ? sourceCandidate
        : defaultSource;
      const targetHandle = TARGET_HANDLE_OPTIONS.includes(targetCandidate)
        ? targetCandidate
        : defaultTarget;
      return { sourceHandle, targetHandle };
    }

    function buildPersistedEdgeHandleMap(uiState) {
      const persisted = isRecord(uiState?.edge_handles) ? uiState.edge_handles : {};
      const map = new Map();
      for (const [rawIndex, rawHandles] of Object.entries(persisted)) {
        const index = Number(rawIndex);
        if (!Number.isInteger(index) || index < 0 || !isRecord(rawHandles)) {
          continue;
        }
        const handles = resolveEdgeHandles({
          sourceHandle: rawHandles.source_handle,
          targetHandle: rawHandles.target_handle,
        });
        map.set(index, handles);
      }
      return map;
    }

    function buildEdgeAppearance(index, condition, loopEdge) {
      const label = edgeLabel(index, condition);
      const stroke = loopEdge ? "#c2793b" : "#6f89ac";
      return {
        type: "smoothstep",
        label,
        labelShowBg: Boolean(label),
        labelBgPadding: [6, 2],
        labelBgBorderRadius: 4,
        labelBgStyle: { fill: "#ffffff", fillOpacity: 0.95 },
        markerEnd: {
          type: "arrowclosed",
          color: stroke,
          width: 18,
          height: 18,
        },
        style: loopEdge
          ? { stroke, strokeWidth: 2.2, strokeDasharray: "7 5" }
          : { stroke, strokeWidth: 1.6 },
        animated: loopEdge,
        pathOptions: loopEdge
          ? { offset: 36, borderRadius: 16 }
          : { offset: 24, borderRadius: 12 },
      };
    }

    function buildValidationText(report) {
      if (!report) return "-";
      if (report.is_valid) return "workflow validation passed";
      const lines = ["workflow validation failed:"];
      for (const issue of report.issues || []) {
        lines.push(`- [${issue.code}] ${issue.message} @ ${JSON.stringify(issue.location || [])}`);
      }
      return lines.join("\\n");
    }

    function buildDiffText(data) {
      const summary = isRecord(data.summary) ? data.summary : {};
      return [
        `summary: total=${summary.total || 0}, nodes=${summary.nodes || 0}, edges=${summary.edges || 0}, params=${summary.params || 0}, ui_state=${summary.ui_state || 0}, other=${summary.other || 0}`,
        "",
        "yaml diff:",
        data.yaml_unified_diff || "(no yaml changes)",
      ].join("\\n");
    }

    createApp({
      components: {
        "vue-flow": VueFlow,
        "mini-map": MiniMap,
        "flow-controls": FlowControls,
        "flow-background": FlowBackground,
        "workflow-node": WorkflowNode,
      },
      setup() {
        const revision = ref(null);
        const backupId = ref("");
        const status = reactive({ message: "idle", isError: false });
        const validationText = ref("-");
        const diffText = ref("");
        const hasTarget = ref(false);
        const showLauncher = ref(false);
        const studioTargetPath = ref("");
        const studioWorkspaceRoot = ref("");
        const workflowCandidates = ref([]);
        const launcher = reactive({
          openWorkflowPath: "",
          createWorkflowPath: "",
          overwrite: false,
        });

        const yamlFiles = ref([]);
        const nodes = ref([]);
        const edges = ref([]);
        const originalWorkflow = ref({});
        const baseUiState = ref({});
        const workflowMeta = reactive({
          version: "1.0",
          startAt: "",
          endAt: [],
        });

        const selectedNodeId = ref(null);
        const selectedEdgeId = ref(null);
        const isConnecting = ref(false);

        const newNode = reactive({
          id: "",
          handler: "",
        });
        const nodeEditor = reactive({
          id: "",
          handler: "",
          promptFilePath: "",
          promptFileParseError: "",
          promptRef: "",
          promptSystem: "",
          promptUser: "",
          modelProvider: "",
          modelName: "",
          temperature: "",
          topP: "",
          maxTokens: "",
        });
        const edgeEditor = reactive({
          condition: "",
        });

        const defaultEdgeOptions = {
          type: "smoothstep",
          markerEnd: {
            type: "arrowclosed",
            color: "#6f89ac",
            width: 18,
            height: 18,
          },
          labelShowBg: true,
          labelBgPadding: [6, 2],
          labelBgBorderRadius: 4,
          labelBgStyle: { fill: "#ffffff", fillOpacity: 0.95 },
          style: { stroke: "#6f89ac", strokeWidth: 1.6 },
          pathOptions: { offset: 24, borderRadius: 12 },
        };

        const nodeTypes = { workflow: WorkflowNode };

        const statusClass = computed(() => (status.isError ? "danger" : "ok"));
        const selectedNode = computed(() =>
          nodes.value.find(node => node.id === selectedNodeId.value) || null,
        );
        const selectedEdge = computed(() =>
          edges.value.find(edge => edge.id === selectedEdgeId.value) || null,
        );
        const nodeIdOptions = computed(() => {
          const ids = [];
          const seen = new Set();
          for (const node of nodes.value) {
            const nodeId = normalizeText(node?.id);
            if (!nodeId || seen.has(nodeId)) {
              continue;
            }
            seen.add(nodeId);
            ids.push(nodeId);
          }
          return ids;
        });

        watch(
          selectedNode,
          node => {
            if (!node) {
              nodeEditor.id = "";
              nodeEditor.handler = "";
              nodeEditor.promptFilePath = "";
              nodeEditor.promptFileParseError = "";
              nodeEditor.promptRef = "";
              nodeEditor.promptSystem = "";
              nodeEditor.promptUser = "";
              nodeEditor.modelProvider = "";
              nodeEditor.modelName = "";
              nodeEditor.temperature = "";
              nodeEditor.topP = "";
              nodeEditor.maxTokens = "";
              return;
            }
            const data = isRecord(node.data) ? node.data : {};
            const prompt = isRecord(data.prompt) ? data.prompt : null;
            const model = isRecord(data.model) ? data.model : null;
            const modelKwargs = isRecord(model?.kwargs) ? model.kwargs : null;
            const modelNameRaw = typeof model?.name === "string"
              ? model.name
              : typeof model?.model === "string"
                ? model.model
                : typeof model?.model_name === "string"
                  ? model.model_name
                  : "";
            const temperatureRaw = model?.temperature ?? modelKwargs?.temperature;
            const topPRaw = model?.top_p ?? modelKwargs?.top_p;
            const maxTokensRaw = model?.max_tokens ?? modelKwargs?.max_tokens;
            nodeEditor.id = normalizeText(node.id);
            nodeEditor.handler = normalizeText(data.handler);
            nodeEditor.promptRef = normalizeText(data.promptRef);
            nodeEditor.promptSystem = typeof prompt?.system === "string"
              ? prompt.system
              : "";
            nodeEditor.promptUser = typeof prompt?.user === "string"
              ? prompt.user
              : "";
            nodeEditor.modelProvider = typeof model?.provider === "string"
              ? model.provider
              : "";
            nodeEditor.modelName = normalizeText(modelNameRaw);
            nodeEditor.temperature = Number.isFinite(Number(temperatureRaw))
              ? String(Number(temperatureRaw))
              : "";
            nodeEditor.topP = Number.isFinite(Number(topPRaw))
              ? String(Number(topPRaw))
              : "";
            nodeEditor.maxTokens = Number.isInteger(Number(maxTokensRaw))
              ? String(Number(maxTokensRaw))
              : "";
            const refParts = splitPromptReference(nodeEditor.promptRef);
            nodeEditor.promptFilePath = refParts.path;
            nodeEditor.promptFileParseError = "";
            if (refParts.path) {
              void loadPromptFromYaml(refParts.path, {
                preferredKeyPath: refParts.keyPath,
                updatePromptRef: false,
                quiet: true,
              });
            }
          },
          { immediate: true },
        );

        watch(
          selectedEdge,
          edge => {
            if (!edge) {
              edgeEditor.condition = "";
              return;
            }
            edgeEditor.condition = normalizeText(edge.data?.condition);
          },
          { immediate: true },
        );

        function setStatus(message, isError = false) {
          status.message = message;
          status.isError = isError;
        }

        function parseOptionalNumber(raw, label) {
          const text = normalizeText(raw);
          if (!text) {
            return null;
          }
          const value = Number(text);
          if (!Number.isFinite(value)) {
            throw new Error(`${label} must be a number`);
          }
          return value;
        }

        function parseOptionalInteger(raw, label) {
          const value = parseOptionalNumber(raw, label);
          if (value === null) {
            return null;
          }
          if (!Number.isInteger(value)) {
            throw new Error(`${label} must be an integer`);
          }
          return value;
        }

        function splitPromptReference(rawReference) {
          const text = normalizeText(rawReference);
          if (!text) {
            return { path: "", keyPath: "" };
          }
          const hashIndex = text.indexOf("#");
          if (hashIndex < 0) {
            return { path: text, keyPath: "" };
          }
          return {
            path: text.slice(0, hashIndex).trim(),
            keyPath: text.slice(hashIndex + 1).trim(),
          };
        }

        function buildPromptReference(path, keyPath = "") {
          const normalizedPath = normalizeText(path);
          const normalizedKeyPath = normalizeText(keyPath);
          if (!normalizedPath) {
            return "";
          }
          return normalizedKeyPath ? `${normalizedPath}#${normalizedKeyPath}` : normalizedPath;
        }

        function selectPromptEntry(entries, preferredKeyPath = "") {
          if (!Array.isArray(entries) || entries.length === 0) {
            return null;
          }
          const preferred = normalizeText(preferredKeyPath);
          if (preferred) {
            const exact = entries.find(entry => normalizeText(entry?.key_path) === preferred);
            if (exact) {
              return exact;
            }
          }
          const root = entries.find(entry => normalizeText(entry?.key_path) === "");
          if (root) {
            return root;
          }
          return entries[0];
        }

        function sanitizePromptFileStem(rawNodeId) {
          const text = normalizeText(rawNodeId).toLowerCase();
          const stem = text
            .replace(/[^a-z0-9_-]+/g, "-")
            .replace(/^-+/g, "")
            .replace(/-+$/g, "");
          return stem || "node-prompt";
        }

        function buildPromptYamlContent(systemPrompt, userPrompt) {
          const system = typeof systemPrompt === "string" ? systemPrompt : "";
          const user = typeof userPrompt === "string" ? userPrompt : "";
          return [
            `system: ${JSON.stringify(system)}`,
            `user: ${JSON.stringify(user)}`,
            "",
          ].join("\\n");
        }

        function resetEditorState() {
          revision.value = null;
          backupId.value = "";
          yamlFiles.value = [];
          nodes.value = [];
          edges.value = [];
          originalWorkflow.value = {};
          baseUiState.value = {};
          workflowMeta.version = "1.0";
          workflowMeta.startAt = "";
          workflowMeta.endAt = [];
          nodeEditor.id = "";
          nodeEditor.handler = "";
          nodeEditor.promptFilePath = "";
          nodeEditor.promptFileParseError = "";
          nodeEditor.promptRef = "";
          nodeEditor.promptSystem = "";
          nodeEditor.promptUser = "";
          nodeEditor.modelProvider = "";
          nodeEditor.modelName = "";
          nodeEditor.temperature = "";
          nodeEditor.topP = "";
          nodeEditor.maxTokens = "";
          selectedNodeId.value = null;
          selectedEdgeId.value = null;
          validationText.value = "-";
          diffText.value = "";
        }

        function resolveWorkflowStartAt(value) {
          const ids = normalizeNodeIdList(value);
          return ids.length > 0 ? ids[0] : "";
        }

        function normalizeWorkflowMeta(metaLike, nodeItems) {
          const nodeIds = [];
          const seen = new Set();
          for (const node of Array.isArray(nodeItems) ? nodeItems : []) {
            const nodeId = normalizeText(node?.id);
            if (!nodeId || seen.has(nodeId)) {
              continue;
            }
            seen.add(nodeId);
            nodeIds.push(nodeId);
          }
          const nodeIdSet = new Set(nodeIds);
          const version = normalizeText(metaLike?.version) || "1.0";

          let startAt = normalizeText(metaLike?.startAt);
          if (!nodeIdSet.has(startAt)) {
            startAt = nodeIds[0] || "";
          }

          const endAt = [];
          const endSeen = new Set();
          for (const rawNodeId of normalizeNodeIdList(metaLike?.endAt)) {
            if (!nodeIdSet.has(rawNodeId) || endSeen.has(rawNodeId)) {
              continue;
            }
            endSeen.add(rawNodeId);
            endAt.push(rawNodeId);
          }
          if (startAt && endAt.length === 0) {
            endAt.push(startAt);
          }

          return { version, startAt, endAt };
        }

        function syncWorkflowMetaWithNodes(nodeItems = nodes.value) {
          const normalized = normalizeWorkflowMeta(workflowMeta, nodeItems);
          workflowMeta.version = normalized.version;
          workflowMeta.startAt = normalized.startAt;
          workflowMeta.endAt = normalized.endAt;
        }

        function syncNodeRoleFlags() {
          const startNodeId = normalizeText(workflowMeta.startAt);
          const endNodeIdSet = new Set(normalizeNodeIdList(workflowMeta.endAt));
          nodes.value = nodes.value.map(node => {
            const current = isRecord(node.data) ? node.data : {};
            return {
              ...node,
              data: {
                ...current,
                isStart: node.id === startNodeId,
                isEnd: endNodeIdSet.has(node.id),
              },
            };
          });
        }

        function onWorkflowMetaChange() {
          syncWorkflowMetaWithNodes(nodes.value);
          syncNodeRoleFlags();
        }

        function refreshEdgeMetadata() {
          const edgeInputs = edges.value.map((edge, index) => {
            const current = isRecord(edge.data) ? edge.data : {};
            return {
              key: edge.id,
              source: edge.source,
              target: edge.target,
              condition: normalizeText(current.condition),
              index,
            };
          });
          const loopEdgeKeySet = buildLoopEdgeKeySet(edgeInputs);
          edges.value = edges.value.map((edge, index) => {
            const current = isRecord(edge.data) ? edge.data : {};
            const condition = normalizeText(current.condition);
            const loopEdge = loopEdgeKeySet.has(edge.id);
            const manualHandle = Boolean(current.manualHandle);
            const handles = resolveEdgeHandles({
              sourceHandle: normalizeHandleId(edge.sourceHandle) || normalizeHandleId(current.sourceHandle),
              targetHandle: normalizeHandleId(edge.targetHandle) || normalizeHandleId(current.targetHandle),
            });
            return {
              ...edge,
              ...handles,
              ...buildEdgeAppearance(index, condition, loopEdge),
              data: {
                ...current,
                index,
                condition,
                isLoopEdge: loopEdge,
                manualHandle,
                sourceHandle: handles.sourceHandle,
                targetHandle: handles.targetHandle,
              },
            };
          });
          if (selectedEdgeId.value && !edges.value.some(edge => edge.id === selectedEdgeId.value)) {
            selectedEdgeId.value = null;
          }
        }

        function buildNodesFromPayload(workflow, uiState, formNodes) {
          const workflowNodes = Array.isArray(workflow?.nodes) ? workflow.nodes : [];
          const startIds = new Set(normalizeNodeIdList(workflow?.start_at));
          const endIds = new Set(normalizeNodeIdList(workflow?.end_at));
          const nodeFormById = new Map(
            (Array.isArray(formNodes) ? formNodes : [])
              .filter(item => isRecord(item) && typeof item.id === "string")
              .map(item => [item.id, item]),
          );
          const positions = isRecord(uiState?.positions) ? uiState.positions : {};

          return workflowNodes
            .filter(node => isRecord(node) && typeof node.id === "string")
            .map((node, index) => {
              const formItem = nodeFormById.get(node.id);
              const params = isRecord(node.params) ? node.params : {};
              const rawPos = positions[node.id];
              const fallbackPos = defaultNodePosition(index);
              const x = Number(rawPos?.x);
              const y = Number(rawPos?.y);
              const position = {
                x: Number.isFinite(x) ? x : fallbackPos.x,
                y: Number.isFinite(y) ? y : fallbackPos.y,
              };
              const promptObj = isRecord(formItem?.prompt)
                ? deepClone(formItem.prompt)
                : isRecord(params.prompt)
                  ? deepClone(params.prompt)
                  : null;
              const modelObj = isRecord(formItem?.model)
                ? deepClone(formItem.model)
                : isRecord(params.model)
                  ? deepClone(params.model)
                  : null;
              return {
                id: node.id,
                type: "workflow",
                position,
                data: {
                  id: node.id,
                  handler: typeof node.handler === "string" ? node.handler : "",
                  promptRef: typeof formItem?.prompt_ref === "string"
                    ? formItem.prompt_ref
                    : typeof params.prompt_ref === "string"
                      ? params.prompt_ref
                      : "",
                  prompt: promptObj,
                  model: modelObj,
                  isStart: startIds.has(node.id),
                  isEnd: endIds.has(node.id),
                  rawNode: deepClone(node),
                },
              };
            });
        }

        function buildEdgesFromPayload(workflow, uiState, formEdges, nodeItems) {
          const workflowEdges = Array.isArray(workflow?.edges) ? workflow.edges : [];
          const persistedHandleMap = buildPersistedEdgeHandleMap(uiState);
          const edgeFormByIndex = new Map(
            (Array.isArray(formEdges) ? formEdges : [])
              .filter(item => isRecord(item) && Number.isInteger(item.index))
              .map(item => [item.index, item]),
          );
          const validEdges = workflowEdges
            .map((edge, index) => {
              if (!isRecord(edge) || typeof edge.source !== "string" || typeof edge.target !== "string") {
                return null;
              }
              const formItem = edgeFormByIndex.get(index);
              const condition = typeof formItem?.condition === "string"
                  ? formItem.condition
                  : typeof edge.condition === "string"
                    ? edge.condition
                    : "";
              return { edge, index, condition };
            })
            .filter(Boolean);
          const edgeInputs = validEdges.map(item => ({
            key: `edge-${item.index}-${item.edge.source}-${item.edge.target}`,
            source: item.edge.source,
            target: item.edge.target,
            condition: item.condition,
            index: item.index,
          }));
          const loopEdgeKeySet = buildLoopEdgeKeySet(edgeInputs);
          const nodeMap = buildNodeMap(nodeItems);
          const handlePlan = buildEdgeHandlePlan(
            edgeInputs.map(item => ({ id: item.key, source: item.source, target: item.target })),
            nodeMap,
          );
          return validEdges.map(item => {
            const edgeId = `edge-${item.index}-${item.edge.source}-${item.edge.target}`;
            const loopEdge = loopEdgeKeySet.has(edgeId);
            const handles = persistedHandleMap.get(item.index)
              || handlePlan.get(edgeId)
              || resolveEdgeHandles(item.edge);
            return {
              id: edgeId,
              source: item.edge.source,
              target: item.edge.target,
              ...handles,
              ...buildEdgeAppearance(item.index, item.condition, loopEdge),
              data: {
                index: item.index,
                condition: item.condition,
                isLoopEdge: loopEdge,
                manualHandle: false,
                sourceHandle: handles.sourceHandle,
                targetHandle: handles.targetHandle,
                rawEdge: deepClone(item.edge),
              },
            };
          });
        }

        function buildWorkflowPayload() {
          const workflowNodes = nodes.value.map(node => {
            const data = isRecord(node.data) ? node.data : {};
            const rawNode = isRecord(data.rawNode) ? deepClone(data.rawNode) : {};
            rawNode.id = node.id;
            rawNode.handler = normalizeText(data.handler);
            const params = isRecord(rawNode.params) ? deepClone(rawNode.params) : {};
            delete params.prompt_ref;
            delete params.prompt;
            delete params.model;
            const promptRef = normalizeText(data.promptRef);
            if (promptRef) {
              params.prompt_ref = promptRef;
            }
            if (isRecord(data.prompt)) {
              params.prompt = deepClone(data.prompt);
            }
            if (isRecord(data.model)) {
              params.model = deepClone(data.model);
            }
            if (Object.keys(params).length > 0) {
              rawNode.params = params;
            } else {
              delete rawNode.params;
            }
            return rawNode;
          });

          const workflowEdges = edges.value.map(edge => {
            const currentData = isRecord(edge.data) ? edge.data : {};
            const rawEdge = isRecord(currentData.rawEdge) ? deepClone(currentData.rawEdge) : {};
            rawEdge.source = edge.source;
            rawEdge.target = edge.target;
            const condition = normalizeText(currentData.condition);
            if (condition) {
              rawEdge.condition = condition;
            } else {
              delete rawEdge.condition;
            }
            return rawEdge;
          });

          const normalizedMeta = normalizeWorkflowMeta(workflowMeta, workflowNodes);
          const payload = isRecord(originalWorkflow.value)
            ? deepClone(originalWorkflow.value)
            : {};
          const rootParams = isRecord(payload.params) ? deepClone(payload.params) : {};
          delete rootParams.prompt_catalog;
          delete rootParams.model_catalog;
          payload.version = normalizedMeta.version;
          payload.start_at = normalizedMeta.startAt;
          payload.end_at = normalizedMeta.endAt;
          payload.nodes = workflowNodes;
          payload.edges = workflowEdges;
          if (Object.keys(rootParams).length > 0) {
            payload.params = rootParams;
          } else {
            payload.params = {};
          }
          return payload;
        }

        function buildUiStatePayload() {
          const payload = isRecord(baseUiState.value) ? deepClone(baseUiState.value) : {};
          const positions = {};
          for (const node of nodes.value) {
            positions[node.id] = {
              x: Number.isFinite(Number(node.position?.x)) ? Number(node.position.x) : 0,
              y: Number.isFinite(Number(node.position?.y)) ? Number(node.position.y) : 0,
            };
          }
          payload.positions = positions;

          const edgeHandles = {};
          for (const edge of edges.value) {
            const currentData = isRecord(edge.data) ? edge.data : {};
            const rawIndex = Number(currentData.index);
            if (!Number.isInteger(rawIndex) || rawIndex < 0) {
              continue;
            }
            const handles = resolveEdgeHandles({
              sourceHandle: normalizeHandleId(edge.sourceHandle) || normalizeHandleId(currentData.sourceHandle),
              targetHandle: normalizeHandleId(edge.targetHandle) || normalizeHandleId(currentData.targetHandle),
            });
            edgeHandles[String(rawIndex)] = {
              source_handle: handles.sourceHandle,
              target_handle: handles.targetHandle,
            };
          }
          payload.edge_handles = edgeHandles;
          return payload;
        }

        async function applyNodeEdit() {
          if (!selectedNode.value) {
            setStatus("node is not selected", true);
            return;
          }
          try {
            const currentNodeId = selectedNode.value.id;
            const nextNodeId = normalizeText(nodeEditor.id);
            if (!nextNodeId) {
              setStatus("node id is required", true);
              return;
            }
            if (
              nextNodeId !== currentNodeId
              && nodes.value.some(node => node.id === nextNodeId)
            ) {
              setStatus(`node already exists: ${nextNodeId}`, true);
              return;
            }
            const selectedData = isRecord(selectedNode.value.data) ? selectedNode.value.data : {};
            const promptObj = isRecord(selectedData.prompt)
              ? deepClone(selectedData.prompt)
              : {};
            const promptSystem = normalizeText(nodeEditor.promptSystem);
            const promptUser = normalizeText(nodeEditor.promptUser);
            if (promptSystem) {
              promptObj.system = promptSystem;
            } else {
              delete promptObj.system;
            }
            if (promptUser) {
              promptObj.user = promptUser;
            } else {
              delete promptObj.user;
            }
            const finalPrompt = Object.keys(promptObj).length > 0 ? promptObj : null;
            let promptFilePath = normalizeText(nodeEditor.promptFilePath);
            let promptRef = normalizeText(nodeEditor.promptRef);
            if (!promptFilePath) {
              const createdPath = await createPromptFileForNode(nextNodeId, promptSystem, promptUser);
              promptFilePath = createdPath;
              nodeEditor.promptFilePath = createdPath;
              nodeEditor.promptFileParseError = "";
              promptRef = createdPath;
              nodeEditor.promptRef = createdPath;
            } else {
              const refParts = splitPromptReference(promptRef);
              if (!promptRef || refParts.path !== promptFilePath) {
                promptRef = promptFilePath;
                nodeEditor.promptRef = promptRef;
              }
            }

            const modelObj = isRecord(selectedData.model)
              ? deepClone(selectedData.model)
              : {};
            const modelProvider = normalizeText(nodeEditor.modelProvider);
            const modelName = normalizeText(nodeEditor.modelName);
            if (modelProvider) {
              modelObj.provider = modelProvider;
            } else {
              delete modelObj.provider;
            }
            if (modelName) {
              modelObj.name = modelName;
            } else {
              delete modelObj.name;
              delete modelObj.model;
              delete modelObj.model_name;
            }
            const temperature = parseOptionalNumber(nodeEditor.temperature, "temperature");
            const topP = parseOptionalNumber(nodeEditor.topP, "top_p");
            const maxTokens = parseOptionalInteger(nodeEditor.maxTokens, "max_tokens");
            if (isRecord(modelObj.kwargs)) {
              delete modelObj.kwargs.temperature;
              delete modelObj.kwargs.top_p;
              delete modelObj.kwargs.max_tokens;
              if (Object.keys(modelObj.kwargs).length === 0) {
                delete modelObj.kwargs;
              }
            }
            if (temperature !== null) {
              modelObj.temperature = temperature;
            } else {
              delete modelObj.temperature;
            }
            if (topP !== null) {
              modelObj.top_p = topP;
            } else {
              delete modelObj.top_p;
            }
            if (maxTokens !== null) {
              modelObj.max_tokens = maxTokens;
            } else {
              delete modelObj.max_tokens;
            }
            const finalModel = Object.keys(modelObj).length > 0 ? modelObj : null;
            const renamed = currentNodeId !== nextNodeId;
            nodes.value = nodes.value.map(node => {
              if (node.id !== currentNodeId) {
                return node;
              }
              const current = isRecord(node.data) ? node.data : {};
              return {
                ...node,
                id: nextNodeId,
                data: {
                  ...current,
                  id: nextNodeId,
                  handler: normalizeText(nodeEditor.handler),
                  promptRef,
                  prompt: finalPrompt,
                  model: finalModel,
                },
              };
            });
            if (renamed) {
              edges.value = edges.value.map(edge => {
                const source =
                  edge.source === currentNodeId ? nextNodeId : edge.source;
                const target =
                  edge.target === currentNodeId ? nextNodeId : edge.target;
                const currentData = isRecord(edge.data) ? edge.data : {};
                const rawEdge = isRecord(currentData.rawEdge)
                  ? deepClone(currentData.rawEdge)
                  : {};
                rawEdge.source = source;
                rawEdge.target = target;
                return {
                  ...edge,
                  source,
                  target,
                  data: {
                    ...currentData,
                    rawEdge,
                  },
                };
              });
              if (normalizeText(workflowMeta.startAt) === currentNodeId) {
                workflowMeta.startAt = nextNodeId;
              }
              workflowMeta.endAt = normalizeNodeIdList(workflowMeta.endAt).map(nodeId =>
                nodeId === currentNodeId ? nextNodeId : nodeId,
              );
              selectedNodeId.value = nextNodeId;
            }
            onWorkflowMetaChange();
            refreshEdgeMetadata();
            if (renamed) {
              setStatus(`node renamed: ${currentNodeId} -> ${nextNodeId} (prompt: ${promptRef})`);
              return;
            }
            setStatus(`node edit applied: ${nextNodeId} (prompt: ${promptRef})`);
          } catch (error) {
            const message = error instanceof Error ? error.message : String(error);
            setStatus(message, true);
          }
        }

        function applyEdgeEdit() {
          if (!selectedEdge.value) {
            setStatus("edge is not selected", true);
            return;
          }
          const targetId = selectedEdge.value.id;
          const condition = normalizeText(edgeEditor.condition);
          edges.value = edges.value.map(edge => {
            if (edge.id !== targetId) {
              return edge;
            }
            const current = isRecord(edge.data) ? edge.data : {};
            return {
              ...edge,
              data: {
                ...current,
                condition,
              },
            };
          });
          refreshEdgeMetadata();
          setStatus(`edge edit applied: ${targetId}`);
        }

        function addNode() {
          const nodeId = normalizeText(newNode.id);
          const handler = normalizeText(newNode.handler);
          if (!nodeId) {
            setStatus("node id is required", true);
            return;
          }
          if (!handler) {
            setStatus("handler is required", true);
            return;
          }
          if (nodes.value.some(node => node.id === nodeId)) {
            setStatus(`node already exists: ${nodeId}`, true);
            return;
          }

          const position = defaultNodePosition(nodes.value.length);
          nodes.value = [
            ...nodes.value,
            {
              id: nodeId,
              type: "workflow",
              position,
              data: {
                id: nodeId,
                handler,
                promptRef: "",
                prompt: null,
                model: null,
                isStart: false,
                isEnd: false,
                rawNode: { id: nodeId, handler },
              },
            },
          ];
          if (!normalizeText(workflowMeta.startAt)) {
            workflowMeta.startAt = nodeId;
          }
          if (normalizeNodeIdList(workflowMeta.endAt).length === 0) {
            workflowMeta.endAt = [nodeId];
          }
          onWorkflowMetaChange();
          selectedNodeId.value = nodeId;
          selectedEdgeId.value = null;
          newNode.id = "";
          newNode.handler = "";
          setStatus(`node created: ${nodeId}`);
        }

        function onNodesChange(changes) {
          nodes.value = applyNodeChanges(changes, nodes.value);
          onWorkflowMetaChange();
        }

        function onEdgesChange(changes) {
          edges.value = applyEdgeChanges(changes, edges.value);
          refreshEdgeMetadata();
        }

        function onConnect(connection) {
          if (!connection?.source || !connection?.target) {
            setStatus("invalid edge connection", true);
            return;
          }
          if (connection.source === connection.target) {
            setStatus("source and target must be different", true);
            return;
          }
          const edgeId = `edge-${Date.now()}-${Math.floor(Math.random() * 100000)}`;
          const handles = resolveEdgeHandles(connection);
          const nextEdge = {
            id: edgeId,
            source: connection.source,
            target: connection.target,
            sourceHandle: handles.sourceHandle,
            targetHandle: handles.targetHandle,
            data: {
              condition: "",
              isLoopEdge: false,
              manualHandle: true,
              sourceHandle: handles.sourceHandle,
              targetHandle: handles.targetHandle,
              rawEdge: { source: connection.source, target: connection.target },
            },
          };
          edges.value = [...edges.value, nextEdge];
          refreshEdgeMetadata();
          selectedNodeId.value = null;
          selectedEdgeId.value = edgeId;
          isConnecting.value = false;
          setStatus(`edge created: ${connection.source} -> ${connection.target}`);
        }

        function onConnectStart() {
          isConnecting.value = true;
        }

        function onConnectEnd() {
          isConnecting.value = false;
        }

        function onNodeClick(event) {
          selectedNodeId.value = event.node.id;
          selectedEdgeId.value = null;
        }

        function onEdgeClick(event) {
          selectedEdgeId.value = event.edge.id;
          selectedNodeId.value = null;
        }

        function onEdgeUpdate(event) {
          if (!event?.edge?.id || !event?.connection?.source || !event?.connection?.target) {
            setStatus("edge rewire failed: invalid payload", true);
            return;
          }
          edges.value = edges.value.map(edge => {
            if (edge.id !== event.edge.id) {
              return edge;
            }
            const currentData = isRecord(edge.data) ? edge.data : {};
            const handles = resolveEdgeHandles({
              sourceHandle:
                event.connection.sourceHandle
                || edge.sourceHandle
                || currentData.sourceHandle,
              targetHandle:
                event.connection.targetHandle
                || edge.targetHandle
                || currentData.targetHandle,
            });
            return {
              ...edge,
              source: event.connection.source,
              target: event.connection.target,
              sourceHandle: handles.sourceHandle,
              targetHandle: handles.targetHandle,
              data: {
                ...currentData,
                manualHandle: true,
                sourceHandle: handles.sourceHandle,
                targetHandle: handles.targetHandle,
              },
            };
          });
          refreshEdgeMetadata();
          selectedEdgeId.value = event.edge.id;
          setStatus(`edge rewired: ${event.connection.source} -> ${event.connection.target}`);
        }

        function onPaneClick() {
          selectedNodeId.value = null;
          selectedEdgeId.value = null;
        }

        async function requestJson(url, options = {}) {
          const response = await fetch(url, options);
          let data = {};
          try {
            data = await response.json();
          } catch (_error) {
            data = {};
          }
          return { response, data };
        }

        async function loadStudioTarget() {
          const { response, data } = await requestJson("/api/studio/target");
          if (!response.ok) {
            setStatus(data.message || data.error || "failed to load studio target", true);
            return false;
          }
          hasTarget.value = Boolean(data.has_target);
          studioTargetPath.value = normalizeText(data.workflow_path);
          studioWorkspaceRoot.value = normalizeText(data.workspace_root);
          return true;
        }

        async function loadStudioFiles() {
          const { response, data } = await requestJson("/api/studio/files");
          if (!response.ok) {
            setStatus(data.message || data.error || "failed to load studio files", true);
            return false;
          }
          workflowCandidates.value = Array.isArray(data.workflows)
            ? data.workflows.filter(item => typeof item === "string")
            : [];
          yamlFiles.value = Array.isArray(data.yaml_files)
            ? data.yaml_files.filter(item => typeof item === "string")
            : [];
          const selected = normalizeText(launcher.openWorkflowPath);
          if (!selected || !workflowCandidates.value.includes(selected)) {
            launcher.openWorkflowPath = workflowCandidates.value[0] || "";
          }
          const currentYamlPath = normalizeText(nodeEditor.promptFilePath);
          if (currentYamlPath && !yamlFiles.value.includes(currentYamlPath)) {
            nodeEditor.promptFilePath = "";
            nodeEditor.promptFileParseError = "";
          }
          const workspaceRoot = normalizeText(data.workspace_root);
          if (workspaceRoot) {
            studioWorkspaceRoot.value = workspaceRoot;
          }
          return true;
        }

        async function loadPromptFromYaml(path, options = {}) {
          const normalizedPath = normalizeText(path);
          const optionMapping = isRecord(options) ? options : {};
          const preferredKeyPath = normalizeText(optionMapping.preferredKeyPath);
          const updatePromptRef = optionMapping.updatePromptRef !== false;
          const quiet = optionMapping.quiet === true;

          const activeNode = selectedNode.value;
          const activeNodeId = normalizeText(activeNode?.id);
          const currentNodeId = normalizeText(nodeEditor.id);
          if (!activeNodeId || activeNodeId !== currentNodeId) {
            return null;
          }

          const targetPath = normalizedPath;
          if (!targetPath) {
            nodeEditor.promptFileParseError = "";
            return null;
          }
          if (!quiet) {
            setStatus(`loading yaml: ${targetPath} ...`);
          }
          const { response, data } = await requestJson("/api/studio/file/read", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ path: targetPath }),
          });
          if (!response.ok) {
            if (!quiet) {
              setStatus(data.message || data.error || "yaml load failed", true);
            }
            return null;
          }

          if (normalizeText(selectedNode.value?.id) !== activeNodeId) {
            return null;
          }

          const resolvedPath = normalizeText(data.path) || targetPath;
          nodeEditor.promptFilePath = resolvedPath;
          nodeEditor.promptFileParseError = normalizeText(data.parse_error);
          const promptEntries = Array.isArray(data.prompt_entries)
            ? data.prompt_entries
              .filter(item => isRecord(item))
              .map(item => ({
                key_path: normalizeText(item.key_path),
                system: typeof item.system === "string" ? item.system : "",
                user: typeof item.user === "string" ? item.user : "",
              }))
            : [];
          const selectedEntry = selectPromptEntry(promptEntries, preferredKeyPath);
          if (!selectedEntry) {
            if (updatePromptRef) {
              nodeEditor.promptRef = resolvedPath;
            }
            if (!quiet) {
              if (nodeEditor.promptFileParseError) {
                setStatus(`yaml loaded with parse warning: ${resolvedPath}`, true);
              } else {
                setStatus(`yaml loaded: ${resolvedPath}`);
              }
            }
            return { path: resolvedPath, keyPath: "", system: "", user: "" };
          }
          nodeEditor.promptSystem = selectedEntry.system;
          nodeEditor.promptUser = selectedEntry.user;
          if (updatePromptRef) {
            nodeEditor.promptRef = buildPromptReference(resolvedPath, selectedEntry.key_path);
          }
          if (!quiet) {
            const resolvedRef = buildPromptReference(resolvedPath, selectedEntry.key_path);
            setStatus(`prompt loaded: ${resolvedRef}`);
          }
          return {
            path: resolvedPath,
            keyPath: selectedEntry.key_path,
            system: selectedEntry.system,
            user: selectedEntry.user,
          };
        }

        async function onNodePromptFileChange() {
          if (!selectedNode.value) {
            setStatus("node is not selected", true);
            return;
          }
          const path = normalizeText(nodeEditor.promptFilePath);
          if (!path) {
            nodeEditor.promptFileParseError = "";
            nodeEditor.promptRef = "";
            setStatus("prompt yaml is not selected (auto create on Apply)");
            return;
          }
          const currentRef = splitPromptReference(nodeEditor.promptRef);
          const preferredKeyPath = currentRef.path === path ? currentRef.keyPath : "";
          await loadPromptFromYaml(path, {
            preferredKeyPath,
            updatePromptRef: true,
            quiet: false,
          });
        }

        async function createPromptFileForNode(nodeId, systemPrompt, userPrompt) {
          const stem = sanitizePromptFileStem(nodeId);
          const content = buildPromptYamlContent(systemPrompt, userPrompt);
          let attempt = 0;
          while (attempt < 200) {
            const suffix = attempt === 0 ? "" : `-${attempt + 1}`;
            const path = `prompts/${stem}${suffix}.yaml`;
            const { response, data } = await requestJson("/api/studio/file/save", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                path,
                content,
                overwrite: false,
              }),
            });
            if (response.ok) {
              const savedPath = normalizeText(data.path) || path;
              await loadStudioFiles();
              return savedPath;
            }
            if (response.status === 409 && normalizeText(data.error) === "yaml_file_exists") {
              attempt += 1;
              continue;
            }
            throw new Error(data.message || data.error || `yaml save failed: ${path}`);
          }
          throw new Error("failed to allocate prompt yaml path under prompts/");
        }

        async function refreshStudioFiles() {
          setStatus("loading workflow list...");
          const loaded = await loadStudioFiles();
          if (!loaded) {
            return;
          }
          setStatus("workflow list updated");
        }

        function openLauncher() {
          showLauncher.value = true;
          void loadStudioFiles();
        }

        function closeLauncher() {
          if (!hasTarget.value) {
            return;
          }
          showLauncher.value = false;
        }

        async function openStudioTarget() {
          const workflowPath = normalizeText(launcher.openWorkflowPath);
          if (!workflowPath) {
            setStatus("open target is required", true);
            return;
          }
          setStatus(`opening: ${workflowPath} ...`);
          const { response, data } = await requestJson("/api/studio/open", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ workflow_path: workflowPath }),
          });
          if (!response.ok) {
            setStatus(data.message || data.error || "open failed", true);
            return;
          }
          await loadStudioTarget();
          showLauncher.value = false;
          await loadWorkflow();
          setStatus(`opened: ${workflowPath}`);
        }

        async function createStudioTarget() {
          const workflowPath = normalizeText(launcher.createWorkflowPath);
          if (!workflowPath) {
            setStatus("create target path is required", true);
            return;
          }
          setStatus(`creating: ${workflowPath} ...`);
          const { response, data } = await requestJson("/api/studio/create", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              workflow_path: workflowPath,
              overwrite: Boolean(launcher.overwrite),
            }),
          });
          if (!response.ok) {
            setStatus(data.message || data.error || "create failed", true);
            return;
          }
          launcher.openWorkflowPath = workflowPath;
          await loadStudioFiles();
          await loadStudioTarget();
          showLauncher.value = false;
          await loadWorkflow();
          setStatus(`created: ${workflowPath}`);
        }

        async function loadWorkflow() {
          setStatus("loading...");
          const { response, data } = await requestJson("/api/workflow/form");
          if (response.status === 409 && data.error === "studio_target_required") {
            resetEditorState();
            hasTarget.value = false;
            showLauncher.value = true;
            await loadStudioTarget();
            await loadStudioFiles();
            setStatus("workflow target を選択してください");
            return;
          }
          if (!response.ok) {
            setStatus(data.message || data.error || "load failed", true);
            return;
          }
          hasTarget.value = true;
          showLauncher.value = false;

          revision.value = typeof data.revision === "string" ? data.revision : null;
          originalWorkflow.value = isRecord(data.workflow) ? deepClone(data.workflow) : {};
          baseUiState.value = isRecord(data.ui_state) ? deepClone(data.ui_state) : {};

          nodes.value = buildNodesFromPayload(data.workflow, data.ui_state, data.nodes);
          workflowMeta.version = normalizeText(data.workflow?.version) || "1.0";
          workflowMeta.startAt = resolveWorkflowStartAt(data.workflow?.start_at);
          workflowMeta.endAt = normalizeNodeIdList(data.workflow?.end_at);
          onWorkflowMetaChange();
          edges.value = buildEdgesFromPayload(data.workflow, data.ui_state, data.edges, nodes.value);
          refreshEdgeMetadata();
          selectedNodeId.value = null;
          selectedEdgeId.value = null;
          validationText.value = buildValidationText(data.validation_report);
          diffText.value = "";
          setStatus("loaded");
        }

        async function previewDiff() {
          if (!revision.value) {
            setStatus("load first", true);
            return;
          }
          setStatus("previewing...");
          const response = await fetch("/api/workflow/diff", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              workflow: buildWorkflowPayload(),
              ui_state: buildUiStatePayload(),
              base_revision: revision.value,
            }),
          });
          const data = await response.json();
          if (response.status === 409) {
            if (data.error === "studio_target_required") {
              resetEditorState();
              hasTarget.value = false;
              showLauncher.value = true;
              await loadStudioTarget();
              await loadStudioFiles();
              setStatus("workflow target を選択してください");
              return;
            }
            setStatus("revision conflict. reload required", true);
            return;
          }
          if (!response.ok) {
            setStatus(data.message || data.error || "diff failed", true);
            return;
          }
          validationText.value = buildValidationText(data.validation_report);
          diffText.value = buildDiffText(data);
          setStatus("diff ready");
        }

        async function saveWorkflow() {
          if (!revision.value) {
            setStatus("load first", true);
            return;
          }
          setStatus("saving...");
          const response = await fetch("/api/workflow/save", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              workflow: buildWorkflowPayload(),
              ui_state: buildUiStatePayload(),
              base_revision: revision.value,
            }),
          });
          const data = await response.json();
          if (response.status === 409) {
            if (data.error === "studio_target_required") {
              resetEditorState();
              hasTarget.value = false;
              showLauncher.value = true;
              await loadStudioTarget();
              await loadStudioFiles();
              setStatus("workflow target を選択してください");
              return;
            }
            setStatus("revision conflict. reload required", true);
            return;
          }
          if (response.status === 422) {
            validationText.value = buildValidationText(data.report);
            setStatus("validation failed", true);
            return;
          }
          if (!response.ok) {
            setStatus(data.message || data.error || "save failed", true);
            return;
          }
          revision.value = data.saved_revision;
          backupId.value = data.backup_id || "";
          await loadWorkflow();
          setStatus(`saved (backup: ${data.backup_id})`);
        }

        async function rollbackWorkflow() {
          const targetBackupId = normalizeText(backupId.value);
          if (!targetBackupId) {
            setStatus("backup_id is required", true);
            return;
          }
          const shouldProceed = window.confirm(
            "rollback を実行すると現在状態が復元先へ置き換わります。続行しますか？",
          );
          if (!shouldProceed) {
            setStatus("rollback cancelled");
            return;
          }
          setStatus("rolling back...");
          const response = await fetch("/api/workflow/rollback", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ backup_id: targetBackupId }),
          });
          const data = await response.json();
          if (response.status === 409 && data.error === "studio_target_required") {
            resetEditorState();
            hasTarget.value = false;
            showLauncher.value = true;
            await loadStudioTarget();
            await loadStudioFiles();
            setStatus("workflow target を選択してください");
            return;
          }
          if (!response.ok) {
            setStatus(data.message || data.error || "rollback failed", true);
            return;
          }
          revision.value = data.restored_revision;
          const safetyBackupId = normalizeText(data.safety_backup_id);
          if (safetyBackupId) {
            backupId.value = safetyBackupId;
          }
          await loadWorkflow();
          if (safetyBackupId) {
            setStatus(`rolled back (${targetBackupId}), safety backup: ${safetyBackupId}`);
            return;
          }
          setStatus(`rolled back (${targetBackupId})`);
        }

        onMounted(async () => {
          setStatus("initializing...");
          const targetLoaded = await loadStudioTarget();
          if (!targetLoaded) {
            return;
          }
          await loadStudioFiles();
          if (hasTarget.value) {
            await loadWorkflow();
            return;
          }
          resetEditorState();
          showLauncher.value = true;
          setStatus("workflow target を選択してください");
        });

        return {
          revision,
          backupId,
          status,
          statusClass,
          validationText,
          diffText,
          hasTarget,
          showLauncher,
          studioTargetPath,
          studioWorkspaceRoot,
          workflowCandidates,
          launcher,
          yamlFiles,
          workflowMeta,
          nodeIdOptions,
          nodes,
          edges,
          selectedNode,
          selectedEdge,
          newNode,
          nodeEditor,
          edgeEditor,
          isConnecting,
          nodeTypes,
          defaultEdgeOptions,
          loadWorkflow,
          refreshStudioFiles,
          openLauncher,
          closeLauncher,
          openStudioTarget,
          createStudioTarget,
          onNodePromptFileChange,
          previewDiff,
          saveWorkflow,
          rollbackWorkflow,
          onWorkflowMetaChange,
          addNode,
          applyNodeEdit,
          applyEdgeEdit,
          onNodesChange,
          onEdgesChange,
          onConnect,
          onConnectStart,
          onConnectEnd,
          onNodeClick,
          onEdgeClick,
          onEdgeUpdate,
          onPaneClick,
        };
      },
    }).mount("#app");
  </script>
</body>
</html>
"""
