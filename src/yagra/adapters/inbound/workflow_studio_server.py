"""Provides the local HTTP server for Workflow Studio."""

from __future__ import annotations

import json
import mimetypes
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from os import PathLike
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

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


def _load_web_asset(asset_path: str) -> tuple[bytes, str] | None:
    """Loads bundled web assets.

    Args:
        asset_path: Relative path after `/assets/`.

    Returns:
        `(body, content_type)`. Returns `None` for invalid paths or missing files.
    """
    normalized = asset_path.strip().replace("\\", "/")
    if not normalized:
        return None
    path_parts = normalized.split("/")
    if path_parts[0] != "vendor" or any(part in {"", ".", ".."} for part in path_parts):
        return None

    resource: resources.abc.Traversable = resources.files("yagra.web_assets")
    for part in path_parts:
        resource = resource.joinpath(part)
    if not resource.is_file():
        return None

    body = resource.read_bytes()
    mime_type, _ = mimetypes.guess_type(normalized)
    if mime_type is None and normalized.endswith(".mjs"):
        mime_type = "application/javascript"
    if mime_type is None:
        mime_type = "application/octet-stream"
    if mime_type.startswith("text/") or mime_type in {
        "application/javascript",
        "application/json",
        "application/xml",
        "image/svg+xml",
    }:
        return body, f"{mime_type}; charset=utf-8"
    return body, mime_type


def _resolve_workspace_root_path(
    *,
    workflow_abspath: Path | None,
    workspace_root: str | PathLike[str] | None,
) -> Path:
    """Determines the default workspace_root for Studio.

    Args:
        workflow_abspath: Absolute path to the workflow being edited.
        workspace_root: workspace_root explicitly specified from the CLI.

    Returns:
        Absolute path to the workspace_root to use.
    """
    if workspace_root is not None:
        return Path(workspace_root).expanduser().resolve()

    current_dir = Path.cwd().resolve()
    if workflow_abspath is None:
        return current_dir
    try:
        workflow_abspath.relative_to(current_dir)
    except ValueError:
        return workflow_abspath.parent
    return current_dir


def create_workflow_studio_server(
    workflow_path: str | PathLike[str] | None = None,
    bundle_root: str | PathLike[str] | None = None,
    ui_state_path: str | PathLike[str] | None = None,
    workspace_root: str | PathLike[str] | None = None,
    backup_dir: str | PathLike[str] = ".yagra/backups",
    host: str = "127.0.0.1",
    port: int = 8787,
) -> ThreadingHTTPServer:
    """Creates the Workflow Studio local server.

    Args:
        workflow_path: Path to the workflow to edit. Select/create from the UI launcher if not specified.
        bundle_root: Base directory for resolving split references.
        ui_state_path: UI sidecar path.
        workspace_root: Workspace root where workflow exploration/creation is permitted.
        backup_dir: Directory for storing backups.
        host: Bind host.
        port: Bind port.

    Returns:
        Configured `ThreadingHTTPServer`.
    """
    workflow_abspath = (
        Path(workflow_path).expanduser().resolve() if workflow_path is not None else None
    )
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
    workspace_root_path = _resolve_workspace_root_path(
        workflow_abspath=workflow_abspath,
        workspace_root=workspace_root,
    )
    bundle_root_path = Path(bundle_root).expanduser().resolve() if bundle_root is not None else None
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
    """Creates an HTTP Handler class encapsulating configuration.

    Args:
        studio: Studio inbound port implementation.

    Returns:
        Derived class of `BaseHTTPRequestHandler`.
    """
    # ── Routing table ──────────────────────────────────────────
    # GET: path → service method name (no arguments)
    _get_routes: dict[str, str] = {
        "/api/studio/target": "get_studio_target",
        "/api/studio/files": "get_studio_files",
        "/api/workflow/form": "get_form",
        "/api/workflow": "get_workflow",
    }

    # POST: path → service method name (receives body)
    _post_routes: dict[str, str] = {
        "/api/workflow/diff": "diff",
        "/api/workflow/form/preview": "form_preview",
        "/api/workflow/catalogs/preview": "catalog_preview",
        "/api/workflow/save": "save",
        "/api/workflow/rollback": "rollback",
        "/api/studio/open": "open_studio_target",
        "/api/studio/create": "create_studio_target",
        "/api/studio/file/read": "read_studio_yaml_file",
        "/api/studio/file/save": "save_studio_yaml_file",
    }

    class WorkflowStudioHandler(BaseHTTPRequestHandler):
        """Handles requests to the Workflow Studio API."""

        _studio = studio

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
            """Suppresses standard output logging."""
            _ = (format, args)

        def do_GET(self) -> None:  # noqa: N802
            """Handles GET requests."""
            path = urlparse(self.path).path
            if path == "/":
                self._write_html(_studio_html())
                return
            if path.startswith("/assets/"):
                self._handle_get_asset(path)
                return

            method_name = _get_routes.get(path)
            if method_name is not None:
                operation = getattr(self._studio, method_name)
                payload = self._execute_studio_call(operation)
                if payload is not None:
                    self._write_json(200, payload)
                return

            self._write_json(404, {"error": "not_found"})

        def do_POST(self) -> None:  # noqa: N802
            """Handles POST requests."""
            path = urlparse(self.path).path
            try:
                body = self._read_json_body()
            except ValueError as exc:
                self._write_json(400, {"error": "invalid_json", "message": str(exc)})
                return

            method_name = _post_routes.get(path)
            if method_name is not None:
                method = getattr(self._studio, method_name)
                payload = self._execute_studio_call(lambda: method(body))
                if payload is not None:
                    self._write_json(200, payload)
                return

            self._write_json(404, {"error": "not_found"})

        def _handle_get_asset(self, path: str) -> None:
            """Returns bundled static assets."""
            asset_path = unquote(path.removeprefix("/assets/"))
            loaded = _load_web_asset(asset_path)
            if loaded is None:
                self._write_json(404, {"error": "not_found"})
                return
            body, content_type = loaded
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _execute_studio_call(
            self,
            operation: Callable[[], dict[str, Any]],
        ) -> dict[str, Any] | None:
            """Executes a Studio service call and converts errors to HTTP responses."""
            try:
                return operation()
            except (
                StudioBadRequestError,
                StudioNotFoundError,
                StudioConflictError,
                StudioUnprocessableEntityError,
            ) as exc:
                status = {
                    StudioBadRequestError: 400,
                    StudioNotFoundError: 404,
                    StudioConflictError: 409,
                    StudioUnprocessableEntityError: 422,
                }[type(exc)]
                self._write_json(status, exc.to_payload())
            return None

        def _read_json_body(self) -> dict[str, Any]:
            """Reads the request body as a JSON dictionary."""
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
            """Writes a JSON response."""
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _write_html(self, html_text: str) -> None:
            """Writes an HTML response."""
            body = html_text.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return WorkflowStudioHandler


def _studio_html() -> str:
    """Returns the form editing UI HTML for Workflow Studio."""
    return """<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Yagra Workflow Studio</title>
  <link
    rel="stylesheet"
    href="/assets/vendor/vue-flow/core/1.48.2/style.css"
  />
  <link
    rel="stylesheet"
    href="/assets/vendor/vue-flow/core/1.48.2/theme-default.css"
  />
  <link
    rel="stylesheet"
    href="/assets/vendor/vue-flow/minimap/1.5.4/style.css"
  />
  <link
    rel="stylesheet"
    href="/assets/vendor/vue-flow/controls/1.1.3/style.css"
  />
  <style>
    :root {
      /* ===== Color system ===== */
      /* Background / panel */
      --bg: #f3f7fb;
      --panel: #ffffff;
      --line: #d5deea;

      /* Text */
      --text: #1d2735;
      --text-secondary: #5d6d84;
      --muted: #5d6d84; /* kept for compatibility */

      /* Primary (blue) */
      --primary: #0a6fd8;
      --primary-hover: #0858b0;
      --primary-active: #064488;
      --accent: #0a6fd8; /* kept for compatibility */

      /* Semantic colors */
      --success: #2e7d32;
      --success-bg: #e8f5e9;
      --warning: #f57c00;
      --warning-bg: #fff3e0;
      --danger: #c62828;
      --danger-bg: #ffebee;
      --info: #1976d2;
      --info-bg: #e3f2fd;
      --ok: #2e7d32; /* kept for compatibility */
      --warn: #e65100;

      /* For diff display */
      --diff-add: #e6ffed;
      --diff-add-text: #1b5e20;
      --diff-del: #ffeef0;
      --diff-del-text: #b71c1c;
      --diff-meta: #f0f4ff;
      --diff-meta-text: #1565c0;

      /* For toast notifications */
      --toast-success: #2e7d32;
      --toast-error: #c62828;

      /* For subsections */
      --subsection-bg: #f8fafd;
      --subsection-border: #e4ecf5;

      /* For save button */
      --save-bg: #d32f2f;
      --save-border: #b71c1c;

      /* ===== Spacing scale ===== */
      --spacing-xs: 4px;
      --spacing-sm: 8px;
      --spacing-md: 12px;
      --spacing-lg: 16px;
      --spacing-xl: 24px;
      --spacing-2xl: 32px;

      /* ===== Typography scale ===== */
      --font-size-xs: 11px;
      --font-size-sm: 12px;
      --font-size-base: 14px;
      --font-size-md: 16px;
      --font-size-lg: 18px;
      --font-size-xl: 24px;
      --font-size-2xl: 30px;

      --line-height-tight: 1.35;
      --line-height-base: 1.45;
      --line-height-relaxed: 1.6;

      --font-weight-normal: 400;
      --font-weight-medium: 500;
      --font-weight-bold: 700;
      --font-weight-extrabold: 800;

      /* ===== Miscellaneous ===== */
      --border-radius-sm: 8px;
      --border-radius-md: 10px;
      --border-radius-lg: 12px;
      --border-radius-xl: 14px;
      --border-radius-pill: 999px;

      --shadow-sm: 0 1px 3px rgba(35, 70, 120, 0.1);
      --shadow-md: 0 2px 7px rgba(35, 70, 120, 0.14);
      --shadow-lg: 0 4px 11px rgba(10, 111, 216, 0.24);

      --transition-fast: 120ms ease;
      --transition-base: 200ms ease;
    }
    * {
      box-sizing: border-box;
    }
    body {
      margin: 0;
      font-family: "Noto Sans JP", "Hiragino Kaku Gothic ProN", sans-serif;
      background: var(--bg);
      color: var(--text);
      font-size: var(--font-size-base);
      line-height: var(--line-height-base);
    }
    .page {
      max-width: 1640px;
      margin: 0 auto;
      padding: var(--spacing-lg);
      display: grid;
      gap: var(--spacing-md);
    }
    .header {
      background: linear-gradient(145deg, #ffffff 10%, #eaf3ff 100%);
      border: 1px solid var(--line);
      border-radius: var(--border-radius-xl);
      padding: var(--spacing-lg);
    }
    h1 {
      margin: 0 0 var(--spacing-sm);
      font-size: clamp(var(--font-size-xl), 3vw, var(--font-size-2xl));
      font-weight: var(--font-weight-bold);
      line-height: var(--line-height-tight);
    }
    h2 {
      margin: 0;
      font-size: var(--font-size-lg);
      font-weight: var(--font-weight-medium);
      line-height: var(--line-height-tight);
    }
    .muted {
      color: var(--text-secondary);
      font-size: var(--font-size-sm);
      line-height: var(--line-height-base);
    }
    .toolbar {
      margin-top: var(--spacing-md);
      display: flex;
      flex-wrap: wrap;
      gap: var(--spacing-sm);
      align-items: center;
    }
    .meta-line {
      margin-top: var(--spacing-sm);
      display: flex;
      flex-wrap: wrap;
      gap: var(--spacing-md);
      align-items: center;
    }
    button {
      border: 1px solid var(--primary-active);
      background: var(--primary);
      color: #fff;
      border-radius: var(--border-radius-md);
      padding: var(--spacing-sm) var(--spacing-md);
      font-size: var(--font-size-base);
      font-weight: var(--font-weight-bold);
      cursor: pointer;
      transition: all var(--transition-fast);
      line-height: var(--line-height-tight);
    }
    button:hover {
      background: var(--primary-hover);
      box-shadow: var(--shadow-sm);
    }
    button:active {
      background: var(--primary-active);
      transform: translateY(1px);
    }
    button:focus-visible {
      outline: 2px solid var(--primary);
      outline-offset: 2px;
    }
    button:disabled {
      opacity: 0.55;
      cursor: not-allowed;
    }
    button.secondary {
      background: var(--panel);
      color: var(--primary);
      border-color: var(--line);
    }
    button.secondary:hover {
      background: var(--bg);
    }
    button.secondary:active {
      background: var(--line);
    }
    button.save-btn {
      background: var(--save-bg);
      border-color: var(--save-border);
      color: #fff;
    }
    .btn-group {
      display: flex;
      gap: 6px;
      align-items: center;
    }
    .btn-group + .btn-group {
      margin-left: 4px;
      padding-left: 10px;
      border-left: 1px solid var(--line);
    }
    input[type="text"], select, textarea {
      border: 1px solid var(--line);
      border-radius: var(--border-radius-md);
      padding: var(--spacing-sm) var(--spacing-md);
      width: 100%;
      font-size: var(--font-size-base);
      background: var(--panel);
      color: var(--text);
      font-family: inherit;
      line-height: var(--line-height-base);
      transition: all var(--transition-fast);
    }
    input[type="text"]:hover, select:hover, textarea:hover {
      border-color: var(--primary);
    }
    input[type="text"]:focus, select:focus, textarea:focus {
      outline: none;
      border-color: var(--primary);
      box-shadow: 0 0 0 3px rgba(10, 111, 216, 0.1);
    }
    input[type="text"]:disabled, select:disabled, textarea:disabled {
      opacity: 0.6;
      cursor: not-allowed;
      background: var(--bg);
    }
    textarea {
      min-height: 94px;
      line-height: var(--line-height-relaxed);
      resize: vertical;
    }
    .main {
      display: grid;
      grid-template-columns: 1fr 380px;
      gap: var(--spacing-md);
      align-items: start;
    }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: var(--border-radius-lg);
      padding: var(--spacing-md);
    }
    .canvas-panel {
      min-height: 700px;
      display: grid;
      gap: var(--spacing-md);
    }
    .flow-shell {
      border: 1px solid var(--line);
      border-radius: var(--border-radius-md);
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
      gap: var(--spacing-xs);
    }
    .side-panel {
      display: grid;
      gap: var(--spacing-md);
      position: sticky;
      top: var(--spacing-md);
      max-height: calc(100vh - var(--spacing-2xl));
      overflow: auto;
    }
    .side-section {
      display: grid;
      gap: var(--spacing-sm);
      border: 1px solid var(--line);
      border-radius: var(--border-radius-md);
      padding: var(--spacing-md);
      background: #fbfdff;
    }
    .field {
      display: grid;
      gap: var(--spacing-xs);
    }
    .field label {
      color: var(--text-secondary);
      font-size: var(--font-size-sm);
      font-weight: var(--font-weight-bold);
      line-height: var(--line-height-tight);
    }
    .inline-row {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: var(--spacing-sm);
    }
    .check-list {
      display: grid;
      gap: var(--spacing-xs);
      max-height: 150px;
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: var(--border-radius-sm);
      padding: var(--spacing-sm);
      background: var(--panel);
    }
    .check-item {
      display: flex;
      align-items: center;
      gap: var(--spacing-sm);
      font-size: var(--font-size-sm);
      color: var(--text);
      line-height: var(--line-height-base);
    }
    .hint {
      font-size: var(--font-size-sm);
      color: var(--text-secondary);
      line-height: var(--line-height-base);
    }
    .mono {
      font-family: "Menlo", "Monaco", "Consolas", monospace;
      font-size: var(--font-size-sm);
      line-height: var(--line-height-relaxed);
      color: var(--text);
      word-break: break-all;
    }
    .lower {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: var(--spacing-md);
    }
    pre {
      width: 100%;
      min-height: 170px;
      border: 1px solid var(--line);
      border-radius: var(--border-radius-md);
      padding: var(--spacing-md);
      font-size: var(--font-size-sm);
      line-height: var(--line-height-base);
      background: var(--panel);
      overflow: auto;
      white-space: pre-wrap;
      margin: var(--spacing-sm) 0 0;
    }
    .danger {
      color: var(--danger);
      font-weight: 700;
    }
    .ok {
      color: var(--ok);
      font-weight: 700;
    }
    .toast-container {
      position: fixed;
      top: 14px;
      right: 14px;
      z-index: 9999;
      display: flex;
      flex-direction: column;
      gap: 8px;
      pointer-events: none;
    }
    .toast-item {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 10px 16px;
      border-radius: 10px;
      font-size: 13px;
      font-weight: 600;
      color: #fff;
      background: var(--toast-success);
      box-shadow: 0 4px 14px rgba(0,0,0,0.18);
      pointer-events: auto;
      animation: toastIn 220ms ease;
      max-width: 480px;
      word-break: break-word;
    }
    .toast-item.is-error {
      background: var(--toast-error);
    }
    .toast-item.is-fading {
      opacity: 0;
      transition: opacity 350ms ease;
    }
    @keyframes toastIn {
      from { opacity: 0; transform: translateX(20px); }
      to { opacity: 1; transform: translateX(0); }
    }
    .validation-list {
      display: grid;
      gap: 6px;
      margin: 8px 0 0;
    }
    .validation-pass {
      display: flex;
      align-items: center;
      gap: 6px;
      padding: 8px 12px;
      border-radius: 8px;
      background: #e8f5e9;
      color: var(--ok);
      font-size: 13px;
      font-weight: 700;
    }
    .validation-issue {
      display: flex;
      gap: 8px;
      align-items: flex-start;
      padding: 8px 10px;
      border-radius: 8px;
      background: var(--diff-del);
      font-size: 12px;
      line-height: 1.45;
    }
    .issue-badge {
      display: inline-flex;
      align-items: center;
      padding: 2px 7px;
      border-radius: 4px;
      background: var(--danger);
      color: #fff;
      font-size: 10px;
      font-weight: 800;
      letter-spacing: 0.03em;
      white-space: nowrap;
      flex-shrink: 0;
    }
    .issue-msg {
      color: var(--text);
    }
    .issue-location {
      font-family: "Menlo", "Monaco", "Consolas", monospace;
      font-size: 11px;
      color: var(--muted);
    }
    .diff-display {
      width: 100%;
      min-height: 170px;
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 10px;
      font-family: "Menlo", "Monaco", "Consolas", monospace;
      font-size: 12px;
      line-height: 1.55;
      background: #fff;
      overflow: auto;
      margin: 8px 0 0;
    }
    .diff-line-add {
      background: var(--diff-add);
      color: var(--diff-add-text);
      display: block;
      padding: 0 4px;
      border-radius: 2px;
    }
    .diff-line-del {
      background: var(--diff-del);
      color: var(--diff-del-text);
      display: block;
      padding: 0 4px;
      border-radius: 2px;
    }
    .diff-line-meta {
      background: var(--diff-meta);
      color: var(--diff-meta-text);
      display: block;
      padding: 0 4px;
      border-radius: 2px;
      font-weight: 700;
    }
    .diff-line-ctx {
      display: block;
      padding: 0 4px;
      color: var(--muted);
    }
    .subsection-label {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 11px;
      font-weight: 800;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.06em;
      padding: 6px 0 2px;
      border-top: 1px solid var(--subsection-border);
      margin-top: 4px;
    }
    .subsection-label:first-child {
      border-top: none;
      margin-top: 0;
      padding-top: 0;
    }
    .workflow-node {
      position: relative;
      min-width: 180px;
      max-width: 440px;
      padding: var(--spacing-sm) var(--spacing-md);
      border: 1px solid #8ea8cc;
      border-radius: var(--border-radius-md);
      background: var(--panel);
      box-shadow: var(--shadow-md);
      white-space: normal;
      overflow-wrap: anywhere;
      word-break: break-word;
      transition: all var(--transition-fast);
    }
    .workflow-node:hover {
      box-shadow: var(--shadow-lg);
    }
    .workflow-node.is-start {
      border-color: #5d94d6;
    }
    .workflow-node.is-end {
      border-color: #d89f6f;
    }
    .workflow-node.selected {
      border-color: var(--primary-active);
      box-shadow: var(--shadow-lg);
      border-width: 2px;
    }
    .workflow-node-role {
      display: flex;
      gap: var(--spacing-xs);
      margin-bottom: var(--spacing-xs);
    }
    .role-pill {
      display: inline-flex;
      align-items: center;
      border-radius: var(--border-radius-pill);
      font-size: var(--font-size-xs);
      font-weight: var(--font-weight-extrabold);
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
      font-size: var(--font-size-sm);
      font-weight: var(--font-weight-extrabold);
      margin-bottom: 3px;
      line-height: var(--line-height-tight);
      overflow-wrap: anywhere;
      color: var(--text);
    }
    .workflow-node-handler {
      font-size: var(--font-size-sm);
      color: var(--text-secondary);
      line-height: var(--line-height-base);
      overflow-wrap: anywhere;
    }
    /* Data flow variable badges */
    .node-vars-section {
      display: flex;
      align-items: flex-start;
      flex-wrap: wrap;
      gap: 3px;
      margin-top: 5px;
    }
    .node-vars-label {
      font-size: 9px;
      font-weight: var(--font-weight-extrabold);
      letter-spacing: 0.06em;
      color: var(--muted);
      min-width: 20px;
      flex-shrink: 0;
      padding-top: 3px;
    }
    .var-pill {
      display: inline-flex;
      align-items: center;
      border-radius: var(--border-radius-pill);
      font-size: 10px;
      font-weight: var(--font-weight-bold);
      line-height: 1;
      padding: 2px 6px;
      border: 1px solid transparent;
      max-width: 120px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .var-pill-in {
      background: #e8f1ff;
      color: #0a4a92;
      border-color: #afc9ec;
    }
    .var-pill-out {
      background: #e8f5ee;
      color: #0a6e3a;
      border-color: #8fcdb0;
    }
    .var-pill-more {
      font-size: 10px;
      color: var(--muted);
      cursor: default;
      padding: 2px 4px;
    }
    /* Toolbar toggle label */
    .var-toggle-label {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      font-size: var(--font-size-sm);
      color: var(--text-secondary);
      cursor: pointer;
      user-select: none;
    }
    .var-toggle-label input[type="checkbox"] {
      cursor: pointer;
      width: 14px;
      height: 14px;
      accent-color: var(--primary-active);
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
      gap: var(--spacing-md);
    }
    .launcher-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: var(--spacing-md);
    }
    .launcher-box {
      display: grid;
      gap: var(--spacing-sm);
      border: 1px solid var(--line);
      border-radius: var(--border-radius-md);
      padding: var(--spacing-md);
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
    <div class="toast-container">
      <div
        v-for="toast in toasts"
        :key="toast.id"
        class="toast-item"
        :class="{ 'is-error': toast.isError, 'is-fading': toast.fading }"
      >{{ toast.message }}</div>
    </div>
    <section class="header">
      <h1>Yagra Workflow Studio</h1>
      <div class="toolbar">
        <template v-if="hasTarget">
          <div class="btn-group">
            <button type="button" :disabled="isBusy" @click="loadWorkflow">Load</button>
            <button type="button" class="secondary" :disabled="isBusy" @click="previewDiff">Preview Diff</button>
          </div>
          <div class="btn-group">
            <button type="button" class="save-btn" :disabled="isBusy" @click="saveWorkflow">{{ isBusy ? 'Saving...' : 'Save' }}</button>
          </div>
          <div class="btn-group">
            <input
              v-model.trim="backupId"
              type="text"
              placeholder="backup_id"
              style="max-width: 280px;"
            />
            <button type="button" class="secondary" :disabled="isBusy" @click="rollbackWorkflow">Rollback</button>
          </div>
          <div class="btn-group">
            <button type="button" class="secondary" :disabled="isBusy" @click="openLauncher">Change Target</button>
          </div>
          <div class="btn-group">
            <label class="var-toggle-label">
              <input type="checkbox" v-model="showInputVars" />
              <span>IN</span>
            </label>
            <label class="var-toggle-label">
              <input type="checkbox" v-model="showOutputVars" />
              <span>OUT</span>
            </label>
          </div>
        </template>
        <template v-else>
          <button type="button" @click="refreshStudioFiles">Refresh Files</button>
        </template>
      </div>
      <div class="meta-line">
        <span class="muted">target: {{ studioTargetPath || "-" }}</span>
        <span class="muted">revision: {{ revision || "-" }}</span>
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
            <span>Overwrite existing workflow</span>
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
              Click a node to edit properties in the sidebar. Connect nodes via right/left handles; loop edges use bottom/top handles.
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
                <workflow-node
                  v-bind="nodeProps"
                  :show-input-vars="showInputVars"
                  :show-output-vars="showOutputVars"
                ></workflow-node>
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
                Add nodes first.
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
            <div class="field">
              <label>interrupt_before</label>
              <div v-if="nodeIdOptions.length === 0" class="hint">
                Add nodes first.
              </div>
              <div v-else class="check-list">
                <label v-for="nodeId in nodeIdOptions" :key="'ib-' + nodeId" class="check-item">
                  <input
                    type="checkbox"
                    :value="nodeId"
                    v-model="workflowMeta.interruptBefore"
                    @change="onWorkflowMetaChange"
                  />
                  <span>{{ nodeId }}</span>
                </label>
              </div>
            </div>
            <div class="field">
              <label>interrupt_after</label>
              <div v-if="nodeIdOptions.length === 0" class="hint">
                Add nodes first.
              </div>
              <div v-else class="check-list">
                <label v-for="nodeId in nodeIdOptions" :key="'ia-' + nodeId" class="check-item">
                  <input
                    type="checkbox"
                    :value="nodeId"
                    v-model="workflowMeta.interruptAfter"
                    @change="onWorkflowMetaChange"
                  />
                  <span>{{ nodeId }}</span>
                </label>
              </div>
            </div>
            <div class="field">
              <label>state_schema</label>
              <div class="hint">Define typed state fields. <code>type</code>: str / int / float / bool / list / dict / messages. <code>reducer</code>: add (optional, for list fan-in).</div>
              <table class="state-schema-table" style="width:100%; border-collapse:collapse; font-size:0.85em; margin-top:4px;">
                <thead>
                  <tr>
                    <th style="text-align:left; padding:2px 4px;">field name</th>
                    <th style="text-align:left; padding:2px 4px;">type</th>
                    <th style="text-align:left; padding:2px 4px;">reducer</th>
                    <th style="padding:2px 4px;"></th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(row, idx) in workflowMeta.stateSchema" :key="'ss-' + idx">
                    <td style="padding:2px 4px;">
                      <input
                        v-model.trim="row.name"
                        type="text"
                        placeholder="field_name"
                        style="width:100%; box-sizing:border-box;"
                        @input="onWorkflowMetaChange"
                      />
                    </td>
                    <td style="padding:2px 4px;">
                      <select v-model="row.type" style="width:100%;" @change="onWorkflowMetaChange">
                        <option value="str">str</option>
                        <option value="int">int</option>
                        <option value="float">float</option>
                        <option value="bool">bool</option>
                        <option value="list">list</option>
                        <option value="dict">dict</option>
                        <option value="messages">messages</option>
                      </select>
                    </td>
                    <td style="padding:2px 4px;">
                      <select v-model="row.reducer" style="width:100%;" @change="onWorkflowMetaChange">
                        <option value="">(none)</option>
                        <option value="add">add</option>
                      </select>
                    </td>
                    <td style="padding:2px 4px;">
                      <button
                        type="button"
                        class="btn-small"
                        @click="workflowMeta.stateSchema.splice(idx, 1); onWorkflowMetaChange();"
                        title="Remove"
                      >✕</button>
                    </td>
                  </tr>
                </tbody>
              </table>
              <button
                type="button"
                class="btn-secondary"
                style="margin-top:6px; width:100%;"
                @click="workflowMeta.stateSchema.push({ name: '', type: 'str', reducer: '' }); onWorkflowMetaChange();"
              >+ Add Field</button>
            </div>
            <div class="hint"><code>start_at</code>, <code>end_at</code>, and <code>state_schema</code> are applied to the workflow on save.</div>
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
            <div class="hint">Nodes are auto-positioned. Drag on canvas to reposition.</div>
          </section>

          <section class="side-section">
            <h2>Node Properties</h2>
            <div v-if="!selectedNode" class="hint">
              Select a node to edit its properties.
            </div>
            <template v-else>
              <div class="mono">selected: {{ selectedNode.id }}</div>

              <div class="subsection-label">Basic Info</div>
              <div class="field">
                <label for="nodeIdInput">node id</label>
                <input id="nodeIdInput" v-model.trim="nodeEditor.id" type="text" />
              </div>
              <div class="field">
                <label for="nodeHandlerTypeSelect">handler type</label>
                <select id="nodeHandlerTypeSelect" v-model="nodeEditor.handlerType">
                  <option value="llm">llm</option>
                  <option value="structured_llm">structured_llm</option>
                  <option value="streaming_llm">streaming_llm</option>
                  <option value="custom">custom</option>
                </select>
              </div>
              <div v-if="nodeEditor.handlerType === 'custom'" class="field">
                <label for="nodeHandlerInput">handler name</label>
                <input id="nodeHandlerInput" v-model="nodeEditor.handler" type="text"
                  placeholder="my_custom_handler" />
              </div>

              <div v-if="showPromptFields" class="subsection-label">Prompt Settings</div>
              <div v-if="showPromptFields" class="field">
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
              <div v-if="showPromptFields" class="field">
                <label for="nodePromptKeyInput">prompt key (optional)</label>
                <input
                  id="nodePromptKeyInput"
                  v-model.trim="nodeEditor.promptKey"
                  type="text"
                  list="nodePromptKeyOptions"
                  placeholder="default"
                  @change="onNodePromptKeyChange"
                />
              </div>
              <div v-if="showPromptFields" class="field">
                <label>prompt reference</label>
                <div class="mono hint" style="padding: 4px 0; min-height: 1.4em; word-break: break-all;">
                  {{ nodeEditor.promptRef || "(auto create on Apply)" }}
                </div>
              </div>
              <div v-if="showPromptFields && nodeEditor.promptFileParseError" class="hint danger">
                {{ nodeEditor.promptFileParseError }}
              </div>
              <div v-if="showPromptFields" class="field">
                <label for="nodePromptSystemInput">system prompt</label>
                <textarea
                  id="nodePromptSystemInput"
                  v-model="nodeEditor.promptSystem"
                  placeholder="You are a helpful assistant..."
                ></textarea>
              </div>
              <div v-if="showPromptFields" class="field">
                <label for="nodePromptUserInput">user prompt</label>
                <textarea
                  id="nodePromptUserInput"
                  v-model="nodeEditor.promptUser"
                  placeholder="{input}"
                ></textarea>
              </div>

              <div v-if="isLlmHandler" class="subsection-label">Model Settings</div>
              <div v-if="isLlmHandler" class="inline-row">
                <div class="field">
                  <label for="nodeModelProviderInput">provider</label>
                  <input
                    id="nodeModelProviderInput"
                    v-model.trim="nodeEditor.modelProvider"
                    type="text"
                    placeholder="e.g. openai"
                  />
                </div>
                <div class="field">
                  <label for="nodeModelNameInput">model name</label>
                  <input
                    id="nodeModelNameInput"
                    v-model.trim="nodeEditor.modelName"
                    type="text"
                    placeholder="e.g. gpt-4.1-mini"
                  />
                </div>
              </div>
              <div v-if="isLlmHandler" class="inline-row">
                <div class="field">
                  <label for="nodeModelTemperatureInput">temperature</label>
                  <input
                    id="nodeModelTemperatureInput"
                    v-model.trim="nodeEditor.temperature"
                    type="text"
                    placeholder="e.g. 0.2"
                  />
                </div>
                <div class="field">
                  <label for="nodeModelTopPInput">top_p</label>
                  <input
                    id="nodeModelTopPInput"
                    v-model.trim="nodeEditor.topP"
                    type="text"
                    placeholder="e.g. 0.9"
                  />
                </div>
              </div>
              <div v-if="isLlmHandler" class="field">
                <label for="nodeModelMaxTokensInput">max_tokens</label>
                <input
                  id="nodeModelMaxTokensInput"
                  v-model.trim="nodeEditor.maxTokens"
                  type="text"
                  placeholder="e.g. 512"
                />
              </div>

              <template v-if="isStructuredLlm">
                <div class="subsection-label">Schema Settings</div>
                <div class="field">
                  <label for="nodeSchemaYamlInput">schema yaml</label>
                  <textarea
                    id="nodeSchemaYamlInput"
                    v-model="nodeEditor.schemaYaml"
                    placeholder="name: str&#10;age: int&#10;score: float"
                    style="font-family: monospace; min-height: 6em;"
                  ></textarea>
                </div>
                <div class="hint">Define schema fields as 'field_name: type' (e.g. name: str, age: int). Saved as params.schema_yaml on Apply.</div>
              </template>

              <template v-if="isStreamingLlm">
                <div class="subsection-label">Streaming Settings</div>
                <div class="field" style="flex-direction: row; align-items: center; gap: 8px;">
                  <input
                    id="nodeStreamDisabledInput"
                    v-model="nodeEditor.streamDisabled"
                    type="checkbox"
                    style="width: auto; margin: 0;"
                  />
                  <label for="nodeStreamDisabledInput" style="margin: 0;">Disable stream (explicit false)</label>
                </div>
                <div class="hint">Leave unchecked (default) to enable streaming. Check to explicitly set model.kwargs.stream: false in YAML.</div>
              </template>

              <div v-if="isLlmHandler" class="subsection-label">Output Settings</div>
              <div v-if="isLlmHandler" class="field">
                <label for="nodeOutputKeyInput">output_key</label>
                <input
                  id="nodeOutputKeyInput"
                  v-model.trim="nodeEditor.outputKey"
                  type="text"
                  placeholder="output (default)"
                />
              </div>
              <div v-if="isLlmHandler" class="hint">If left blank, the result is stored under the "output" key.</div>

              <button type="button" class="secondary" :disabled="isBusy" @click="applyNodeEdit">Apply Node Edit</button>
              <div class="hint">Node id must be unique and non-empty. If no prompt yaml is selected, a file is auto-created under prompts/ on Apply. Use prompt key for path#key references.</div>
            </template>
          </section>

          <section class="side-section">
            <h2>Edge Properties</h2>
            <div v-if="!selectedEdge" class="hint">
              Select an edge to edit its condition. Drag edge endpoints to rewire connections.
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
              <button type="button" class="secondary" :disabled="isBusy" @click="applyEdgeEdit">Apply Edge Edit</button>
            </template>
          </section>

        </aside>
      </section>

      <section class="lower">
        <article class="panel">
          <h2>Validation</h2>
          <div v-if="validationData.isValid" class="validation-list">
            <div class="validation-pass">Validation passed</div>
          </div>
          <div v-else-if="validationData.issues.length > 0" class="validation-list">
            <div v-for="(issue, idx) in validationData.issues" :key="'vi-' + idx" class="validation-issue">
              <span class="issue-badge">{{ issue.code }}</span>
              <span class="issue-msg">{{ issue.message }}</span>
              <span v-if="issue.location" class="issue-location">@ {{ issue.location }}</span>
            </div>
          </div>
          <div v-else class="validation-list">
            <div class="hint">No validation data yet. Load or preview to validate.</div>
          </div>
        </article>
        <article class="panel">
          <h2>Diff</h2>
          <div v-if="diffLines.length > 0" class="diff-display">
            <span
              v-for="(line, idx) in diffLines"
              :key="'dl-' + idx"
              :class="line.cls"
            >{{ line.text }}</span>
          </div>
          <div v-else class="diff-display" style="color: var(--muted);">
            Click "Preview Diff" to see changes.
          </div>
        </article>
      </section>
    </template>
    <datalist id="nodePromptKeyOptions">
      <option v-for="keyPath in nodeEditor.promptKeyOptions" :key="'prompt-key-' + keyPath" :value="keyPath"></option>
    </datalist>
  </div>

  <script type="importmap">
    {
      "imports": {
        "vue": "/assets/vendor/vue/3.5.28/vue.esm-browser.prod.js",
        "@vue-flow/core": "/assets/vendor/vue-flow/core/1.48.2/vue-flow-core.mjs",
        "@vue-flow/minimap": "/assets/vendor/vue-flow/minimap/1.5.4/vue-flow-minimap.mjs",
        "@vue-flow/controls": "/assets/vendor/vue-flow/controls/1.1.3/vue-flow-controls.mjs",
        "@vue-flow/background": "/assets/vendor/vue-flow/background/1.3.2/vue-flow-background.mjs"
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
        showInputVars: { type: Boolean, default: true },
        showOutputVars: { type: Boolean, default: true },
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
          <div
            v-if="showInputVars && data.inputVars && data.inputVars.length > 0"
            class="node-vars-section node-vars-in"
          >
            <span class="node-vars-label">IN</span>
            <span v-for="v in data.inputVars" :key="v" class="var-pill var-pill-in" :title="v">{{ v }}</span>
          </div>
          <div
            v-if="showOutputVars && data.outputVars && data.outputVars.length > 0"
            class="node-vars-section node-vars-out"
          >
            <span class="node-vars-label">OUT</span>
            <span v-for="v in data.outputVars" :key="v" class="var-pill var-pill-out" :title="v">{{ v }}</span>
          </div>
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

    function parseValidationReport(report) {
      if (!report) {
        return { isValid: false, issues: [], empty: true };
      }
      if (report.is_valid) {
        return { isValid: true, issues: [], empty: false };
      }
      const issues = (report.issues || []).map(issue => ({
        code: issue.code || "UNKNOWN",
        message: issue.message || "",
        location: issue.location ? JSON.stringify(issue.location) : "",
      }));
      return { isValid: false, issues, empty: false };
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

    function parseDiffLines(data) {
      const summary = isRecord(data.summary) ? data.summary : {};
      const headerLine = `summary: total=${summary.total || 0}, nodes=${summary.nodes || 0}, edges=${summary.edges || 0}, params=${summary.params || 0}`;
      const rawDiff = data.yaml_unified_diff || "";
      const lines = [
        { text: headerLine + "\\n", cls: "diff-line-meta" },
        { text: "\\n", cls: "diff-line-ctx" },
      ];
      if (!rawDiff) {
        lines.push({ text: "(no yaml changes)\\n", cls: "diff-line-ctx" });
        return lines;
      }
      for (const line of rawDiff.split("\\n")) {
        let cls = "diff-line-ctx";
        if (line.startsWith("+")) cls = "diff-line-add";
        else if (line.startsWith("-")) cls = "diff-line-del";
        else if (line.startsWith("@@")) cls = "diff-line-meta";
        lines.push({ text: line + "\\n", cls });
      }
      return lines;
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
        const isBusy = ref(false);
        const toasts = ref([]);
        let toastCounter = 0;
        const validationData = reactive({ isValid: false, issues: [], empty: true });
        const diffLines = ref([]);
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
        const studioFilesRequestSeq = ref(0);
        const nodes = ref([]);
        const edges = ref([]);
        const originalWorkflow = ref({});
        const baseUiState = ref({});
        const workflowMeta = reactive({
          version: "1.0",
          startAt: "",
          endAt: [],
          interruptBefore: [],
          interruptAfter: [],
          stateSchema: [],
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
          handlerType: "llm",
          handler: "",

          promptFilePath: "",
          promptFileParseError: "",
          promptKey: "default",
          promptKeyOptions: [],
          promptRef: "",
          promptSystem: "",
          promptUser: "",
          modelProvider: "",
          modelName: "",
          temperature: "",
          topP: "",
          maxTokens: "",
          schemaYaml: "",
          streamDisabled: false,
          outputKey: "",
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
        const LLM_HANDLERS = ["llm", "structured_llm", "streaming_llm"];
        const isLlmHandler = computed(() => LLM_HANDLERS.includes(nodeEditor.handlerType));
        const isStructuredLlm = computed(() => nodeEditor.handlerType === "structured_llm");
        const isStreamingLlm = computed(() => nodeEditor.handlerType === "streaming_llm");
        const showPromptFields = computed(() => isLlmHandler.value || nodeEditor.handlerType === "custom");

        // Toggle display of data flow variable badges
        const showInputVars = ref(true);
        const showOutputVars = ref(true);

        watch(
          selectedNode,
          node => {
            if (!node) {
              nodeEditor.id = "";
              nodeEditor.handlerType = "llm";
              nodeEditor.handler = "";
              nodeEditor.promptFilePath = "";
              nodeEditor.promptFileParseError = "";
              nodeEditor.promptKey = "default";
              nodeEditor.promptKeyOptions = [];
              nodeEditor.promptRef = "";
              nodeEditor.promptSystem = "";
              nodeEditor.promptUser = "";
              nodeEditor.modelProvider = "";
              nodeEditor.modelName = "";
              nodeEditor.temperature = "";
              nodeEditor.topP = "";
              nodeEditor.maxTokens = "";
              nodeEditor.schemaYaml = "";
              nodeEditor.streamDisabled = false;
              nodeEditor.outputKey = "";
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
            const handlerVal = normalizeText(data.handler);
            nodeEditor.handler = handlerVal;
            nodeEditor.handlerType = LLM_HANDLERS.includes(handlerVal) ? handlerVal : "custom";
            nodeEditor.promptRef = normalizeText(data.promptRef);
            nodeEditor.promptKeyOptions = [];
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
            const params = isRecord(data.params) ? data.params : {};
            nodeEditor.schemaYaml = typeof params.schema_yaml === "string" ? params.schema_yaml : "";
            nodeEditor.outputKey = typeof params.output_key === "string" ? params.output_key : "";
            const streamKwargs = isRecord(model?.kwargs) ? model.kwargs : {};
            nodeEditor.streamDisabled = streamKwargs.stream === false;
            const refParts = splitPromptReference(nodeEditor.promptRef);
            const workspacePromptPath = promptRefPathToWorkspacePath(refParts.path);
            nodeEditor.promptFilePath = workspacePromptPath;
            nodeEditor.promptKey = refParts.keyPath || "default";
            nodeEditor.promptFileParseError = "";
            if (workspacePromptPath) {
              void loadPromptFromYaml(workspacePromptPath, {
                preferredKeyPath: refParts.keyPath,
                updatePromptRef: false,
                quiet: true,
              });
            }
          },
          { immediate: true },
        );

        watch(
          () => nodeEditor.handlerType,
          type => {
            if (type !== "custom") {
              nodeEditor.handler = type;
            }
          },
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
          if (message && message !== "idle") {
            showToast(message, isError);
          }
        }

        function showToast(message, isError = false) {
          toastCounter += 1;
          const id = toastCounter;
          const toast = reactive({ id, message, isError, fading: false });
          toasts.value = [...toasts.value, toast];
          setTimeout(() => {
            toast.fading = true;
            setTimeout(() => {
              toasts.value = toasts.value.filter(t => t.id !== id);
            }, 400);
          }, 3000);
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

        function normalizePosixPath(rawPath) {
          const text = normalizeText(rawPath);
          if (!text) {
            return "";
          }
          const isAbsolute = text.startsWith("/");
          const normalized = text.replace(/\\\\/g, "/");
          const segments = normalized.split("/");
          const stack = [];
          for (const segment of segments) {
            if (!segment || segment === ".") {
              continue;
            }
            if (segment === "..") {
              if (stack.length > 0 && stack[stack.length - 1] !== "..") {
                stack.pop();
              } else if (!isAbsolute) {
                stack.push("..");
              }
              continue;
            }
            stack.push(segment);
          }
          const joined = stack.join("/");
          if (isAbsolute) {
            return joined ? `/${joined}` : "/";
          }
          return joined;
        }

        function joinPosixPath(basePath, childPath) {
          const base = normalizePosixPath(basePath);
          const child = normalizePosixPath(childPath);
          if (!base) {
            return child;
          }
          if (!child) {
            return base;
          }
          if (child.startsWith("/")) {
            return child;
          }
          return normalizePosixPath(`${base}/${child}`);
        }

        function relativePosixPath(fromDir, toPath) {
          const from = normalizePosixPath(fromDir);
          const to = normalizePosixPath(toPath);
          if (!to) {
            return "";
          }
          if (to.startsWith("/")) {
            return to;
          }
          const fromSegments = from ? from.split("/") : [];
          const toSegments = to.split("/");
          let index = 0;
          while (
            index < fromSegments.length
            && index < toSegments.length
            && fromSegments[index] === toSegments[index]
          ) {
            index += 1;
          }
          const upSegments = Array(fromSegments.length - index).fill("..");
          const tailSegments = toSegments.slice(index);
          const relSegments = [...upSegments, ...tailSegments];
          if (relSegments.length === 0) {
            return ".";
          }
          return relSegments.join("/");
        }

        function getWorkflowDirectoryRelative() {
          const workflowPath = normalizePosixPath(studioTargetPath.value);
          const workspaceRoot = normalizePosixPath(studioWorkspaceRoot.value);
          if (!workflowPath || !workspaceRoot || !workflowPath.startsWith("/")) {
            return "";
          }
          const workspacePrefix = workspaceRoot.endsWith("/") ? workspaceRoot : `${workspaceRoot}/`;
          if (!workflowPath.startsWith(workspacePrefix)) {
            return "";
          }
          const workflowRelativePath = workflowPath.slice(workspacePrefix.length);
          const slashIndex = workflowRelativePath.lastIndexOf("/");
          if (slashIndex < 0) {
            return "";
          }
          return workflowRelativePath.slice(0, slashIndex);
        }

        function promptRefPathToWorkspacePath(rawPath) {
          const normalizedPath = normalizePosixPath(rawPath);
          if (!normalizedPath) {
            return "";
          }
          if (normalizedPath.startsWith("/")) {
            const workspaceRoot = normalizePosixPath(studioWorkspaceRoot.value);
            if (!workspaceRoot) {
              return normalizedPath;
            }
            const workspacePrefix = workspaceRoot.endsWith("/") ? workspaceRoot : `${workspaceRoot}/`;
            if (!normalizedPath.startsWith(workspacePrefix)) {
              return normalizedPath;
            }
            return normalizePosixPath(normalizedPath.slice(workspacePrefix.length));
          }
          if (normalizedPath.startsWith("../") || normalizedPath.startsWith("./")) {
            const workflowDir = getWorkflowDirectoryRelative();
            return joinPosixPath(workflowDir, normalizedPath);
          }
          return normalizedPath;
        }

        function workspacePathToPromptRefPath(rawPath) {
          const normalizedPath = normalizePosixPath(rawPath);
          if (!normalizedPath) {
            return "";
          }
          if (normalizedPath.startsWith("/")) {
            const workspaceRoot = normalizePosixPath(studioWorkspaceRoot.value);
            if (!workspaceRoot) {
              return normalizedPath;
            }
            const workspacePrefix = workspaceRoot.endsWith("/") ? workspaceRoot : `${workspaceRoot}/`;
            if (!normalizedPath.startsWith(workspacePrefix)) {
              return normalizedPath;
            }
            return workspacePathToPromptRefPath(normalizedPath.slice(workspacePrefix.length));
          }
          return normalizedPath;
        }

        function normalizePromptKeyPath(rawKeyPath) {
          const text = normalizeText(rawKeyPath);
          if (!text) {
            return "";
          }
          const segments = text.split(".").map(segment => segment.trim());
          if (segments.some(segment => !segment)) {
            throw new Error("prompt key must not contain empty segments");
          }
          return segments.join(".");
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

        function collectPromptKeyOptions(entries) {
          if (!Array.isArray(entries)) {
            return [];
          }
          const keys = new Set();
          for (const entry of entries) {
            const keyPath = normalizeText(entry?.key_path);
            if (!keyPath) {
              continue;
            }
            keys.add(keyPath);
          }
          return Array.from(keys).sort();
        }

        function sanitizePromptFileStem(rawNodeId) {
          const text = normalizeText(rawNodeId).toLowerCase();
          const stem = text
            .replace(/[^a-z0-9_-]+/g, "-")
            .replace(/^-+/g, "")
            .replace(/-+$/g, "");
          return stem || "node-prompt";
        }

        function resolveDefaultPromptDirectory() {
          return "prompts";
        }

        function buildPromptYamlContent(systemPrompt, userPrompt, keyPath = "") {
          const system = typeof systemPrompt === "string" ? systemPrompt : "";
          const user = typeof userPrompt === "string" ? userPrompt : "";
          const normalizedKeyPath = normalizeText(keyPath);
          if (!normalizedKeyPath) {
            return [
              `system: ${JSON.stringify(system)}`,
              `user: ${JSON.stringify(user)}`,
              "",
            ].join("\\n");
          }
          const keySegments = normalizedKeyPath
            .split(".")
            .map(segment => segment.trim())
            .filter(Boolean);
          if (keySegments.length === 0) {
            return [
              `system: ${JSON.stringify(system)}`,
              `user: ${JSON.stringify(user)}`,
              "",
            ].join("\\n");
          }
          const lines = [];
          for (let index = 0; index < keySegments.length; index += 1) {
            const indent = "  ".repeat(index);
            lines.push(`${indent}${JSON.stringify(keySegments[index])}:`);
          }
          const promptIndent = "  ".repeat(keySegments.length);
          return [
            ...lines,
            `${promptIndent}system: ${JSON.stringify(system)}`,
            `${promptIndent}user: ${JSON.stringify(user)}`,
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
          workflowMeta.interruptBefore = [];
          workflowMeta.interruptAfter = [];
          nodeEditor.id = "";
          nodeEditor.handler = "";
          nodeEditor.promptFilePath = "";
          nodeEditor.promptFileParseError = "";
          nodeEditor.promptKey = "default";
          nodeEditor.promptKeyOptions = [];
          nodeEditor.promptRef = "";
          nodeEditor.promptSystem = "";
          nodeEditor.promptUser = "";
          nodeEditor.modelProvider = "";
          nodeEditor.modelName = "";
          nodeEditor.temperature = "";
          nodeEditor.topP = "";
          nodeEditor.maxTokens = "";
          nodeEditor.outputKey = "";
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

          const interruptBefore = [];
          const ibSeen = new Set();
          for (const rawNodeId of normalizeNodeIdList(metaLike?.interruptBefore)) {
            if (!nodeIdSet.has(rawNodeId) || ibSeen.has(rawNodeId)) {
              continue;
            }
            ibSeen.add(rawNodeId);
            interruptBefore.push(rawNodeId);
          }

          const interruptAfter = [];
          const iaSeen = new Set();
          for (const rawNodeId of normalizeNodeIdList(metaLike?.interruptAfter)) {
            if (!nodeIdSet.has(rawNodeId) || iaSeen.has(rawNodeId)) {
              continue;
            }
            iaSeen.add(rawNodeId);
            interruptAfter.push(rawNodeId);
          }

          return { version, startAt, endAt, interruptBefore, interruptAfter };
        }

        function normalizeStateSchema(value) {
          if (!Array.isArray(value)) return [];
          const rows = [];
          for (const item of value) {
            if (!isRecord(item)) continue;
            const name = normalizeText(item.name);
            const type = normalizeText(item.type);
            const reducer = normalizeText(item.reducer);
            if (!name || !type) continue;
            rows.push({ name, type, reducer });
          }
          return rows;
        }

        function stateSchemaToPayload(rows) {
          const schema = {};
          for (const row of rows) {
            const name = normalizeText(row.name);
            const type = normalizeText(row.type);
            const reducer = normalizeText(row.reducer);
            if (!name || !type) continue;
            const entry = { type };
            if (reducer) entry.reducer = reducer;
            schema[name] = entry;
          }
          return schema;
        }

        function stateSchemaFromPayload(payload) {
          if (!isRecord(payload)) return [];
          const rows = [];
          for (const [name, value] of Object.entries(payload)) {
            if (!isRecord(value)) continue;
            const type = normalizeText(value.type);
            const reducer = normalizeText(value.reducer);
            if (!type) continue;
            rows.push({ name, type, reducer: reducer || "" });
          }
          return rows;
        }

        function syncWorkflowMetaWithNodes(nodeItems = nodes.value) {
          const normalized = normalizeWorkflowMeta(workflowMeta, nodeItems);
          workflowMeta.version = normalized.version;
          workflowMeta.startAt = normalized.startAt;
          workflowMeta.endAt = normalized.endAt;
          workflowMeta.interruptBefore = normalized.interruptBefore;
          workflowMeta.interruptAfter = normalized.interruptAfter;
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
          // Recalculate outputVars for nodes following conditional edge changes
          refreshNodeOutputVars();
        }

        /** Recalculates the conditional source set and updates outputVars for each node */
        function refreshNodeOutputVars() {
          const condSources = new Set(
            edges.value
              .filter(e => isRecord(e.data) && normalizeText(e.data.condition))
              .map(e => e.source),
          );
          nodes.value = nodes.value.map(node => {
            const data = isRecord(node.data) ? node.data : {};
            const rawParams = isRecord(data.rawNode?.params) ? data.rawNode.params : {};
            const editedParams = isRecord(data.params) ? data.params : {};
            const mergedParams = { ...rawParams, ...editedParams };
            const outs = [];
            if (hasExplicitOutputKey(mergedParams)) outs.push(extractOutputVar(mergedParams));
            if (condSources.has(node.id)) outs.push("__next__");
            return {
              ...node,
              data: {
                ...data,
                outputVars: outs.length > 0 ? outs : null,
              },
            };
          });
        }

        /** Returns whether params contains a prompt (dict) or prompt_ref (str) */
        function hasPrompt(params) {
          if (!params || typeof params !== "object") return false;
          const p = params.prompt;
          if (p && typeof p === "object") return true;
          if (typeof params.prompt_ref === "string") return true;
          return false;
        }

        /** Returns whether output_key is explicitly specified in params */
        function hasExplicitOutputKey(params) {
          return params && typeof params === "object" && "output_key" in params;
        }

        /** Returns the list of input variable names from rawNode.params (mirrors prompt_variable_validator logic) */
        function extractInputVars(params, promptUserFallback) {
          if (!params || typeof params !== "object") return [];
          const explicitKeys = params.input_keys;
          if (explicitKeys !== undefined && explicitKeys !== null) {
            return Array.isArray(explicitKeys) ? explicitKeys.map(String) : [];
          }
          // Extract {variable} patterns from both system and user prompts (mirrors backend logic)
          const prompt = params.prompt;
          const systemTemplate = (prompt && typeof prompt === "object" && typeof prompt.system === "string")
            ? prompt.system : "";
          // Prefer inline prompt.user; fall back to formItem.prompt_user (resolved prompt_ref text) if absent
          const userTemplate = (prompt && typeof prompt === "object" && typeof prompt.user === "string")
            ? prompt.user
            : (typeof promptUserFallback === "string" ? promptUserFallback : "");
          const seen = new Set();
          const matches = [];
          const re = /\{(\w+)\}/g;
          let m;
          for (const tmpl of [systemTemplate, userTemplate]) {
            re.lastIndex = 0;
            while ((m = re.exec(tmpl)) !== null) {
              if (!seen.has(m[1])) { seen.add(m[1]); matches.push(m[1]); }
            }
          }
          return matches;
        }

        /** Returns the output variable name from rawNode.params (defaults to "output") */
        function extractOutputVar(params) {
          if (!params || typeof params !== "object") return "output";
          const key = params.output_key;
          return (key && typeof key === "string") ? key : "output";
        }

        function buildNodesFromPayload(workflow, uiState, formNodes) {
          const workflowNodes = Array.isArray(workflow?.nodes) ? workflow.nodes : [];
          const workflowEdges = Array.isArray(workflow?.edges) ? workflow.edges : [];
          const conditionalSources = new Set(
            workflowEdges
              .filter(e => isRecord(e) && typeof e.condition === "string")
              .map(e => e.source),
          );
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
              const modelObj = isRecord(formItem?.model)
                ? deepClone(formItem.model)
                : isRecord(params.model)
                  ? deepClone(params.model)
                  : null;
              const loadedParams = {};
              if (typeof params.output_key === "string" && params.output_key) {
                loadedParams.output_key = params.output_key;
              }
              if (typeof params.schema_yaml === "string" && params.schema_yaml) {
                loadedParams.schema_yaml = params.schema_yaml;
              }
              const handler = typeof node.handler === "string" ? node.handler : "";
              const nodeHasPrompt = hasPrompt(params) || (formItem && typeof formItem.prompt_user === "string" && formItem.prompt_user);
              const outs = [];
              if (hasExplicitOutputKey(params)) outs.push(extractOutputVar(params));
              if (conditionalSources.has(node.id)) outs.push("__next__");
              return {
                id: node.id,
                type: "workflow",
                position,
                data: {
                  id: node.id,
                  handler,
                  promptRef: typeof formItem?.prompt_ref === "string"
                    ? formItem.prompt_ref
                    : typeof params.prompt_ref === "string"
                      ? params.prompt_ref
                      : "",
                  prompt: (typeof formItem?.prompt_user === "string" && formItem.prompt_user)
                    ? {
                        system: typeof formItem.prompt_system === "string" ? formItem.prompt_system : "",
                        user: formItem.prompt_user,
                      }
                    : null,
                  model: modelObj,
                  params: Object.keys(loadedParams).length > 0 ? loadedParams : null,
                  isStart: startIds.has(node.id),
                  isEnd: endIds.has(node.id),
                  inputVars: nodeHasPrompt ? extractInputVars(params, formItem?.prompt_user) : null,
                  outputVars: outs.length > 0 ? outs : null,
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
            const rawParams = isRecord(rawNode.params) ? deepClone(rawNode.params) : {};
            const dataParams = isRecord(data.params) ? deepClone(data.params) : {};
            const params = { ...rawParams, ...dataParams };
            delete params.prompt_ref;
            delete params.prompt;
            delete params.model;
            const promptRef = normalizeText(data.promptRef);
            if (promptRef) {
              params.prompt_ref = promptRef;
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
          const interruptBefore = normalizeNodeIdList(workflowMeta.interruptBefore);
          if (interruptBefore.length > 0) {
            payload.interrupt_before = interruptBefore;
          } else {
            delete payload.interrupt_before;
          }
          const interruptAfter = normalizeNodeIdList(workflowMeta.interruptAfter);
          if (interruptAfter.length > 0) {
            payload.interrupt_after = interruptAfter;
          } else {
            delete payload.interrupt_after;
          }
          const stateSchemaPayload = stateSchemaToPayload(normalizeStateSchema(workflowMeta.stateSchema));
          if (Object.keys(stateSchemaPayload).length > 0) {
            payload.state_schema = stateSchemaPayload;
          } else {
            delete payload.state_schema;
          }
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
            const promptSystem = normalizeText(nodeEditor.promptSystem);
            const promptUser = normalizeText(nodeEditor.promptUser);
            const promptKey = normalizePromptKeyPath(nodeEditor.promptKey);
            nodeEditor.promptKey = promptKey;
            let promptFilePath = normalizePosixPath(nodeEditor.promptFilePath);
            let promptRef = normalizeText(nodeEditor.promptRef);
            if (showPromptFields.value) {
              if (!promptFilePath) {
                const createdPath = await createPromptFileForNode(
                  nextNodeId,
                  promptSystem,
                  promptUser,
                  promptKey,
                );
                promptFilePath = normalizePosixPath(createdPath);
                nodeEditor.promptFilePath = createdPath;
                nodeEditor.promptFileParseError = "";
                const promptRefPath = workspacePathToPromptRefPath(promptFilePath) || promptFilePath;
                promptRef = buildPromptReference(promptRefPath, promptKey);
                nodeEditor.promptRef = promptRef;
              } else {
                await savePromptToExistingFile(
                  promptFilePath,
                  promptSystem,
                  promptUser,
                  promptKey,
                );
                const promptRefPath = workspacePathToPromptRefPath(promptFilePath) || promptFilePath;
                promptRef = buildPromptReference(promptRefPath, promptKey);
                nodeEditor.promptRef = promptRef;
              }
            } else {
              // prompt disabled: clear prompt_ref
              promptRef = "";
              nodeEditor.promptRef = "";
              nodeEditor.promptFilePath = "";
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
              delete modelObj.kwargs.stream;
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
            if (isStreamingLlm.value && nodeEditor.streamDisabled) {
              modelObj.kwargs = { ...(isRecord(modelObj.kwargs) ? modelObj.kwargs : {}), stream: false };
            }
            const finalModel = Object.keys(modelObj).length > 0 ? modelObj : null;
            const selectedParams = isRecord(selectedData.params) ? deepClone(selectedData.params) : {};
            if (isStructuredLlm.value && nodeEditor.schemaYaml.trim()) {
              selectedParams.schema_yaml = nodeEditor.schemaYaml.trim();
            } else {
              delete selectedParams.schema_yaml;
            }
            const outputKey = normalizeText(nodeEditor.outputKey);
            if (outputKey) {
              selectedParams.output_key = outputKey;
            } else {
              delete selectedParams.output_key;
            }
            const finalParams = Object.keys(selectedParams).length > 0 ? selectedParams : null;
            const renamed = currentNodeId !== nextNodeId;
            nodes.value = nodes.value.map(node => {
              if (node.id !== currentNodeId) {
                return node;
              }
              const current = isRecord(node.data) ? node.data : {};
              const nextHandler = normalizeText(nodeEditor.handler);
              // Badge recalculation: output_key from finalParams, input variables from promptUser
              const nextRawParams = {
                ...(isRecord(isRecord(node.data) ? node.data.rawNode?.params : {}) ? node.data.rawNode.params : {}),
                ...(finalParams || {}),
                prompt: { system: normalizeText(nodeEditor.promptSystem), user: normalizeText(nodeEditor.promptUser) },
              };
              // Include prompt_ref in params when present
              if (promptRef) {
                nextRawParams.prompt_ref = promptRef;
              }
              const nodeHasPrompt = showPromptFields.value && (hasPrompt(nextRawParams) || !!(normalizeText(nodeEditor.promptSystem) || normalizeText(nodeEditor.promptUser)));
              // Determine conditional edge sources
              const condSources = new Set(
                edges.value
                  .filter(e => isRecord(e.data) && typeof e.data?.rawEdge?.condition === "string")
                  .map(e => e.source),
              );
              const nextOuts = [];
              if (hasExplicitOutputKey(nextRawParams)) nextOuts.push(extractOutputVar(nextRawParams));
              if (condSources.has(nextNodeId)) nextOuts.push("__next__");
              return {
                ...node,
                id: nextNodeId,
                data: {
                  ...current,
                  id: nextNodeId,
                  handler: nextHandler,
                  promptRef,
                  prompt: null,
                  model: finalModel,
                  params: finalParams,
                  inputVars: nodeHasPrompt ? extractInputVars(nextRawParams) : null,
                  outputVars: nextOuts.length > 0 ? nextOuts : null,
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
              workflowMeta.interruptBefore = normalizeNodeIdList(workflowMeta.interruptBefore).map(nodeId =>
                nodeId === currentNodeId ? nextNodeId : nodeId,
              );
              workflowMeta.interruptAfter = normalizeNodeIdList(workflowMeta.interruptAfter).map(nodeId =>
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
          const requestSeq = studioFilesRequestSeq.value + 1;
          studioFilesRequestSeq.value = requestSeq;
          const { response, data } = await requestJson("/api/studio/files");
          if (requestSeq !== studioFilesRequestSeq.value) {
            return null;
          }
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
          const resolvedPromptRefPath = workspacePathToPromptRefPath(resolvedPath) || resolvedPath;
          const promptEntries = Array.isArray(data.prompt_entries)
            ? data.prompt_entries
              .filter(item => isRecord(item))
              .map(item => ({
                key_path: normalizeText(item.key_path),
                system: typeof item.system === "string" ? item.system : "",
                user: typeof item.user === "string" ? item.user : "",
              }))
            : [];
          nodeEditor.promptKeyOptions = collectPromptKeyOptions(promptEntries);
          const selectedEntry = selectPromptEntry(promptEntries, preferredKeyPath);
          if (!selectedEntry) {
            const fallbackKey = normalizeText(preferredKeyPath);
            nodeEditor.promptKey = fallbackKey;
            if (updatePromptRef) {
              nodeEditor.promptRef = buildPromptReference(resolvedPromptRefPath, fallbackKey);
            }
            if (!quiet) {
              if (nodeEditor.promptFileParseError) {
                setStatus(`yaml loaded with parse warning: ${resolvedPath}`, true);
              } else {
                setStatus(`yaml loaded: ${resolvedPath}`);
              }
            }
            return { path: resolvedPath, keyPath: fallbackKey, system: "", user: "" };
          }
          nodeEditor.promptKey = selectedEntry.key_path;
          nodeEditor.promptSystem = selectedEntry.system;
          nodeEditor.promptUser = selectedEntry.user;
          if (updatePromptRef) {
            nodeEditor.promptRef = buildPromptReference(
              resolvedPromptRefPath,
              selectedEntry.key_path,
            );
          }
          if (!quiet) {
            const resolvedRef = buildPromptReference(
              resolvedPromptRefPath,
              selectedEntry.key_path,
            );
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
            nodeEditor.promptKeyOptions = [];
            nodeEditor.promptRef = "";
            setStatus("prompt yaml is not selected (auto create on Apply)");
            return;
          }
          const currentRef = splitPromptReference(nodeEditor.promptRef);
          const currentRefWorkspacePath = promptRefPathToWorkspacePath(currentRef.path);
          const preferredKeyPath = currentRefWorkspacePath === path
            ? currentRef.keyPath
            : normalizeText(nodeEditor.promptKey);
          try {
            const normalizedPreferredKey = normalizePromptKeyPath(preferredKeyPath);
            nodeEditor.promptKey = normalizedPreferredKey;
            await loadPromptFromYaml(path, {
              preferredKeyPath: normalizedPreferredKey,
              updatePromptRef: true,
              quiet: false,
            });
          } catch (error) {
            const message = error instanceof Error ? error.message : String(error);
            setStatus(message, true);
          }
        }

        async function onNodePromptKeyChange() {
          if (!selectedNode.value) {
            setStatus("node is not selected", true);
            return;
          }
          try {
            const keyPath = normalizePromptKeyPath(nodeEditor.promptKey);
            nodeEditor.promptKey = keyPath;
            const path = normalizeText(nodeEditor.promptFilePath);
            if (!path) {
              const refPath = normalizeText(nodeEditor.promptRef);
              if (!refPath) {
                setStatus("prompt key will be used when prompt yaml is auto-created");
                return;
              }
              const refParts = splitPromptReference(refPath);
              if (!refParts.path) {
                setStatus("prompt key will be used when prompt yaml is auto-created");
                return;
              }
              nodeEditor.promptRef = buildPromptReference(refParts.path, keyPath);
              setStatus(`prompt_ref updated: ${nodeEditor.promptRef}`);
              return;
            }
            await loadPromptFromYaml(path, {
              preferredKeyPath: keyPath,
              updatePromptRef: true,
              quiet: false,
            });
          } catch (error) {
            const message = error instanceof Error ? error.message : String(error);
            setStatus(message, true);
          }
        }

        async function onPromptRefChange() {
          if (!selectedNode.value) {
            setStatus("node is not selected", true);
            return;
          }
          const parsed = splitPromptReference(nodeEditor.promptRef);
          const workspacePath = promptRefPathToWorkspacePath(parsed.path);
          nodeEditor.promptFilePath = workspacePath;
          nodeEditor.promptKey = parsed.keyPath;
          if (!workspacePath) {
            nodeEditor.promptFileParseError = "";
            nodeEditor.promptKeyOptions = [];
            setStatus("prompt_ref cleared");
            return;
          }
          const loaded = await loadPromptFromYaml(workspacePath, {
            preferredKeyPath: parsed.keyPath,
            updatePromptRef: false,
            quiet: false,
          });
          if (!loaded) {
            return;
          }
          setStatus(`prompt_ref set: ${buildPromptReference(parsed.path, parsed.keyPath)}`);
        }

        async function createPromptFileForNode(nodeId, systemPrompt, userPrompt, promptKeyPath = "") {
          const stem = sanitizePromptFileStem(nodeId);
          const content = buildPromptYamlContent(systemPrompt, userPrompt, promptKeyPath);
          const promptDirectory = resolveDefaultPromptDirectory();
          let attempt = 0;
          while (attempt < 200) {
            const suffix = attempt === 0 ? "" : `-${attempt + 1}`;
            const path = `${promptDirectory}/${stem}${suffix}.yaml`;
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
          throw new Error(`failed to allocate prompt yaml path under ${promptDirectory}/`);
        }

        async function savePromptToExistingFile(filePath, systemPrompt, userPrompt, promptKeyPath) {
          const content = buildPromptYamlContent(systemPrompt, userPrompt, promptKeyPath);
          const { response, data } = await requestJson("/api/studio/file/save", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              path: filePath,
              content,
              overwrite: true,
            }),
          });
          if (!response.ok) {
            throw new Error(data.message || data.error || `prompt file save failed: ${filePath}`);
          }
          return normalizeText(data.path) || filePath;
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
          isBusy.value = true;
          setStatus(`opening: ${workflowPath} ...`);
          try {
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
            await loadStudioFiles();
            showLauncher.value = false;
            await loadWorkflow();
            setStatus(`opened: ${workflowPath}`);
          } finally {
            isBusy.value = false;
          }
        }

        async function createStudioTarget() {
          const workflowPath = normalizeText(launcher.createWorkflowPath);
          if (!workflowPath) {
            setStatus("create target path is required", true);
            return;
          }
          isBusy.value = true;
          setStatus(`creating: ${workflowPath} ...`);
          try {
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
            await loadStudioTarget();
            await loadStudioFiles();
            showLauncher.value = false;
            await loadWorkflow();
            setStatus(`created: ${workflowPath}`);
          } finally {
            isBusy.value = false;
          }
        }

        async function loadWorkflow() {
          isBusy.value = true;
          setStatus("loading...");
          try {
            const { response, data } = await requestJson("/api/workflow/form");
            if (response.status === 409 && data.error === "studio_target_required") {
              resetEditorState();
              hasTarget.value = false;
              showLauncher.value = true;
              await loadStudioTarget();
              await loadStudioFiles();
              setStatus("Select a workflow target");
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
            workflowMeta.interruptBefore = normalizeNodeIdList(data.workflow?.interrupt_before);
            workflowMeta.interruptAfter = normalizeNodeIdList(data.workflow?.interrupt_after);
            workflowMeta.stateSchema = stateSchemaFromPayload(data.workflow?.state_schema);
            onWorkflowMetaChange();
            edges.value = buildEdgesFromPayload(data.workflow, data.ui_state, data.edges, nodes.value);
            refreshEdgeMetadata();
            selectedNodeId.value = null;
            selectedEdgeId.value = null;
            validationText.value = buildValidationText(data.validation_report);
            const vd = parseValidationReport(data.validation_report);
            validationData.isValid = vd.isValid;
            validationData.issues = vd.issues;
            validationData.empty = vd.empty;
            diffText.value = "";
            diffLines.value = [];
            setStatus("loaded");
          } finally {
            isBusy.value = false;
          }
        }

        async function previewDiff() {
          if (!revision.value) {
            setStatus("load first", true);
            return;
          }
          isBusy.value = true;
          setStatus("previewing...");
          try {
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
                setStatus("Select a workflow target");
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
            const vd = parseValidationReport(data.validation_report);
            validationData.isValid = vd.isValid;
            validationData.issues = vd.issues;
            validationData.empty = vd.empty;
            diffText.value = buildDiffText(data);
            diffLines.value = parseDiffLines(data);
            setStatus("diff ready");
          } finally {
            isBusy.value = false;
          }
        }

        async function saveWorkflow() {
          if (!revision.value) {
            setStatus("load first", true);
            return;
          }
          isBusy.value = true;
          setStatus("saving...");
          try {
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
                setStatus("Select a workflow target");
                return;
              }
              setStatus("revision conflict. reload required", true);
              return;
            }
            if (response.status === 422) {
              validationText.value = buildValidationText(data.report);
              const vd = parseValidationReport(data.report);
              validationData.isValid = vd.isValid;
              validationData.issues = vd.issues;
              validationData.empty = vd.empty;
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
          } finally {
            isBusy.value = false;
          }
        }

        async function rollbackWorkflow() {
          const targetBackupId = normalizeText(backupId.value);
          if (!targetBackupId) {
            setStatus("backup_id is required", true);
            return;
          }
          const shouldProceed = window.confirm(
            "Rollback will replace the current state with the backup. Continue?",
          );
          if (!shouldProceed) {
            setStatus("rollback cancelled");
            return;
          }
          isBusy.value = true;
          setStatus("rolling back...");
          try {
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
              setStatus("Select a workflow target");
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
          } finally {
            isBusy.value = false;
          }
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
          setStatus("Select a workflow target");
        });

        return {
          revision,
          backupId,
          status,
          statusClass,
          validationText,
          diffText,
          isBusy,
          toasts,
          validationData,
          diffLines,
          hasTarget,
          showLauncher,
          studioTargetPath,
          studioWorkspaceRoot,
          workflowCandidates,
          launcher,
          yamlFiles,
          workflowMeta,
          nodeIdOptions,
          isLlmHandler,
          isStructuredLlm,
          isStreamingLlm,
          showPromptFields,
          showInputVars,
          showOutputVars,
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
          onNodePromptKeyChange,
          onPromptRefChange,
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
