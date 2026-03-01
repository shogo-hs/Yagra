"""Provides the input boundary implementation for Workflow Studio."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import Any

import yaml

from yagra.application.services.workflow_file_store import (
    WorkflowBackupNotFoundError,
    WorkflowFileStore,
)
from yagra.application.use_cases.workflow_edit_session import (
    build_workflow_diff,
    load_workflow_edit_session,
)
from yagra.application.use_cases.workflow_form_model import (
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
    validate_workflow_payload_for_ui,
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
    """Mutable session configuration for the Studio service."""

    workflow_path: Path | None
    bundle_root: Path | None
    ui_state_path: Path | None
    ui_state_override: Path | None
    workspace_root: Path
    backup_dir: Path
    lock: Lock = field(default_factory=Lock)


def _resolve_path_in_workspace(
    raw_path: str,
    workspace_root: Path,
    *,
    label: str = "path",
) -> Path:
    """Resolves a YAML path within the workspace to an absolute path.

    Args:
        raw_path: User input path string.
        workspace_root: Absolute path to the workspace root.
        label: Parameter name used in error messages.

    Returns:
        Resolved absolute path.

    Raises:
        ValueError: If the path is empty, outside workspace, or does not have a YAML extension.
    """
    text = raw_path.strip()
    if not text:
        raise ValueError(f"{label} must be a non-empty string")
    source = Path(text).expanduser()
    candidate = source.resolve() if source.is_absolute() else (workspace_root / source).resolve()
    try:
        candidate.relative_to(workspace_root)
    except ValueError as exc:
        raise ValueError(f"{label} must be inside workspace_root") from exc
    if candidate.suffix.lower() not in _WORKFLOW_EXTENSIONS:
        raise ValueError(f"{label} must end with .yaml or .yml")
    return candidate


def _resolve_ui_state_for_target(workflow_path: Path, ui_state_override: Path | None) -> Path:
    """Returns the UI sidecar path corresponding to the target workflow."""
    if ui_state_override is not None:
        return ui_state_override
    return workflow_path.with_suffix(".workflow-ui.json")


_EXCLUDED_DIRS = {"venv", "node_modules", "__pycache__", ".tox", "dist", "build"}

#: Directory names that hold only prompt/catalog YAML files, not workflow entry-points.
_PROMPT_DIRS = {"prompts", "prompt", "catalogs", "catalog"}

#: File names that are always metadata, never workflow entry-points.
_NON_WORKFLOW_FILENAMES = {"template.yaml", "template.yml"}


def _is_workflow_candidate(relative: Path) -> bool:
    """Returns True when the YAML file is likely a workflow entry-point.

    Heuristic: exclude files that live inside a dedicated prompt/catalog
    directory (e.g. ``prompts/``, ``catalog/``) and known metadata files
    (``template.yaml``).  All other ``.yaml`` / ``.yml`` files are considered
    potential workflow entry-points so that custom names like
    ``my-workflow.yaml`` are still included.

    Args:
        relative: Path relative to the workspace root.

    Returns:
        True if the file should appear in the launcher workflow picker.
    """
    if relative.name in _NON_WORKFLOW_FILENAMES:
        return False
    parts = relative.parts[:-1]
    if any(part.lower() in _PROMPT_DIRS for part in parts):
        return False
    return True


def _walk_yaml_files(
    workspace_root: Path,
) -> list[Path]:
    """Walks the workspace and yields YAML files, pruning excluded directories early.

    Uses ``os.scandir`` so that excluded directories (dot-dirs, tool dirs) are
    never descended into, avoiding expensive traversal of large subtrees like
    ``.venv/`` or ``Yagra/``.

    Args:
        workspace_root: Absolute path to the workspace root directory.

    Returns:
        List of absolute Path objects for YAML files under the workspace.
    """
    results: list[Path] = []

    def _scan(dir_path: Path, depth: int) -> None:
        if depth > 10:
            return
        try:
            entries = sorted(os.scandir(dir_path), key=lambda e: e.name)
        except OSError:
            return
        for entry in entries:
            name = entry.name
            if name.startswith("."):
                continue
            if entry.is_dir(follow_symlinks=False):
                if name in _EXCLUDED_DIRS:
                    continue
                _scan(Path(entry.path), depth + 1)
            elif entry.is_file(follow_symlinks=False):
                suffix = Path(name).suffix.lower()
                if suffix in _WORKFLOW_EXTENSIONS:
                    results.append(Path(entry.path))

    _scan(workspace_root, 0)
    return results


def _list_workflow_candidates(workspace_root: Path) -> list[str]:
    """Returns workflow entry-point candidates under the workspace.

    Excludes files inside prompt/catalog directories and known metadata files
    (e.g. ``template.yaml``) so that auxiliary YAML files are not mixed into
    the launcher list.  Also excludes dot-directories, common non-project tool
    directories, and root-level dot-files.

    Args:
        workspace_root: Absolute path to the workspace root directory.

    Returns:
        Sorted list of workspace-relative POSIX paths.
    """
    candidates: list[str] = []
    for path in _walk_yaml_files(workspace_root):
        relative = path.relative_to(workspace_root)
        if not _is_workflow_candidate(relative):
            continue
        candidates.append(relative.as_posix())
    return sorted(candidates)


def _list_yaml_files(workspace_root: Path) -> list[str]:
    """Returns all YAML file candidates under the workspace.

    Used to populate file-picker dropdowns (e.g. prompt_ref selectors) where
    any YAML file is a valid target, not only workflow entry-points.
    Excludes dot-directories, common non-project tool directories, and
    root-level dot-files.

    Args:
        workspace_root: Absolute path to the workspace root directory.

    Returns:
        Sorted list of workspace-relative POSIX paths.
    """
    candidates: list[str] = []
    for path in _walk_yaml_files(workspace_root):
        relative = path.relative_to(workspace_root)
        candidates.append(relative.as_posix())
    return sorted(candidates)


def _to_workspace_relative_path(path: Path, workspace_root: Path) -> str:
    """Converts an absolute path to a relative path based on workspace_root."""
    return path.relative_to(workspace_root).as_posix()


def _collect_yaml_key_paths(payload: Any, prefix: str = "") -> list[str]:
    """Returns a list of keys in `a.b.c` format from a YAML mapping."""
    if not isinstance(payload, dict):
        return []
    key_paths: list[str] = []
    for key, value in payload.items():
        if not isinstance(key, str) or not key:
            continue
        current = f"{prefix}.{key}" if prefix else key
        key_paths.append(current)
        key_paths.extend(_collect_yaml_key_paths(value, prefix=current))
    return key_paths


def _collect_prompt_entries(payload: Any, prefix: str = "") -> list[dict[str, str]]:
    """Extracts a list of prompt entries from a YAML mapping."""
    if not isinstance(payload, dict):
        return []
    entries: list[dict[str, str]] = []
    system = payload.get("system")
    user = payload.get("user")
    if isinstance(system, str) or isinstance(user, str):
        entries.append(
            {
                "key_path": prefix,
                "system": system if isinstance(system, str) else "",
                "user": user if isinstance(user, str) else "",
            }
        )
    for key, value in payload.items():
        if not isinstance(key, str) or not key:
            continue
        current = f"{prefix}.{key}" if prefix else key
        entries.extend(_collect_prompt_entries(value, prefix=current))
    return entries


def _build_initial_workflow_payload() -> dict[str, Any]:
    """Returns the minimal workflow payload to use when creating new workflows."""
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
    """Application service used by the Workflow Studio API."""

    def __init__(self, config: StudioSessionConfig) -> None:
        """Initializes the service.

        Args:
            config: Configuration holding the state of the Studio session.
        """
        self._config = config

    def get_studio_target(self) -> dict[str, Any]:
        """Returns the current target information for Studio."""
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
        """Returns workflow entry-points and all YAML files under the workspace.

        ``workflows`` contains only ``workflow.yaml`` / ``workflow.yml`` files
        for use in the launcher open-workflow picker.
        ``yaml_files`` contains all YAML files for use in file-picker dropdowns
        such as the prompt_ref selector.
        """
        with self._config.lock:
            workspace_root = self._config.workspace_root
            workflow_candidates = _list_workflow_candidates(workspace_root)
            yaml_files = _list_yaml_files(workspace_root)
        return {
            "workspace_root": str(workspace_root),
            "workflows": workflow_candidates,
            "yaml_files": yaml_files,
        }

    def read_studio_yaml_file(self, body: dict[str, Any]) -> dict[str, Any]:
        """Returns the YAML file contents under the workspace."""
        raw_path = body.get("path")
        if not isinstance(raw_path, str):
            raise StudioBadRequestError(error="path must be a string")

        with self._config.lock:
            workspace_root = self._config.workspace_root
            try:
                yaml_path = _resolve_path_in_workspace(
                    raw_path=raw_path,
                    workspace_root=workspace_root,
                )
            except ValueError as exc:
                raise StudioBadRequestError(
                    error="invalid_yaml_path",
                    message=str(exc),
                ) from exc

            if not yaml_path.exists() or not yaml_path.is_file():
                raise StudioNotFoundError(
                    error="yaml_file_not_found",
                    message=f"yaml file not found: {yaml_path}",
                )

            try:
                content = yaml_path.read_text(encoding="utf-8")
            except OSError as exc:
                raise StudioUnprocessableEntityError(
                    error="yaml_read_failed",
                    message=f"yaml file read failed: {yaml_path}: {exc}",
                ) from exc

        parse_error: str | None = None
        key_paths: list[str] = []
        prompt_entries: list[dict[str, str]] = []
        try:
            loaded = yaml.safe_load(content)
            if isinstance(loaded, dict):
                key_paths = sorted(set(_collect_yaml_key_paths(loaded)))
                prompt_entries = sorted(
                    _collect_prompt_entries(loaded),
                    key=lambda item: item.get("key_path", ""),
                )
            elif loaded is not None:
                parse_error = "yaml root must be a mapping to extract prompt keys"
        except yaml.YAMLError as exc:
            parse_error = str(exc)

        return {
            "path": _to_workspace_relative_path(yaml_path, workspace_root),
            "content": content,
            "key_paths": key_paths,
            "prompt_entries": prompt_entries,
            "parse_error": parse_error,
        }

    def save_studio_yaml_file(self, body: dict[str, Any]) -> dict[str, Any]:
        """Creates or updates a YAML file under the workspace."""
        raw_path = body.get("path")
        content = body.get("content")
        overwrite = body.get("overwrite", False)
        if not isinstance(raw_path, str):
            raise StudioBadRequestError(error="path must be a string")
        if not isinstance(content, str):
            raise StudioBadRequestError(error="content must be a string")
        if not isinstance(overwrite, bool):
            raise StudioBadRequestError(error="overwrite must be a boolean")

        with self._config.lock:
            workspace_root = self._config.workspace_root
            try:
                yaml_path = _resolve_path_in_workspace(
                    raw_path=raw_path,
                    workspace_root=workspace_root,
                )
            except ValueError as exc:
                raise StudioBadRequestError(
                    error="invalid_yaml_path",
                    message=str(exc),
                ) from exc

            if yaml_path.exists() and not yaml_path.is_file():
                raise StudioBadRequestError(
                    error="invalid_yaml_path",
                    message=f"path is not a file: {yaml_path}",
                )
            if yaml_path.exists() and not overwrite:
                raise StudioConflictError(
                    error="yaml_file_exists",
                    message=f"yaml file already exists: {yaml_path}",
                )

            try:
                yaml.safe_load(content)
            except yaml.YAMLError as exc:
                raise StudioBadRequestError(
                    error="invalid_yaml_content",
                    message=str(exc),
                ) from exc

            store = WorkflowFileStore(backup_root=self._config.backup_dir)
            try:
                store.write_text_atomic(path=yaml_path, text=content)
            except OSError as exc:
                raise StudioUnprocessableEntityError(
                    error="yaml_save_failed",
                    message=f"yaml file save failed: {yaml_path}: {exc}",
                ) from exc

        return {
            "path": _to_workspace_relative_path(yaml_path, workspace_root),
        }

    def open_studio_target(self, body: dict[str, Any]) -> dict[str, Any]:
        """Opens an existing workflow as a Studio editing target."""
        workflow_path_raw = body.get("workflow_path")
        if not isinstance(workflow_path_raw, str):
            raise StudioBadRequestError(error="workflow_path must be a string")

        with self._config.lock:
            try:
                workflow_path = _resolve_path_in_workspace(
                    raw_path=workflow_path_raw,
                    workspace_root=self._config.workspace_root,
                    label="workflow_path",
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
        """Creates a new workflow and opens it as a Studio editing target."""
        workflow_path_raw = body.get("workflow_path")
        overwrite = body.get("overwrite", False)
        if not isinstance(workflow_path_raw, str):
            raise StudioBadRequestError(error="workflow_path must be a string")
        if not isinstance(overwrite, bool):
            raise StudioBadRequestError(error="overwrite must be a boolean")

        with self._config.lock:
            try:
                workflow_path = _resolve_path_in_workspace(
                    raw_path=workflow_path_raw,
                    workspace_root=self._config.workspace_root,
                    label="workflow_path",
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
        """Returns the current workflow."""
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
            "validation_report": session.validation_report.to_dict(),
        }

    def get_form(self) -> dict[str, Any]:
        """Returns workflow display information for form editing."""
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

        payload = form_view.to_dict()
        payload["workflow"] = session.workflow
        payload["ui_state"] = session.ui_state
        payload["catalog_preview"] = catalog_preview.to_dict()
        payload["validation_report"] = session.validation_report.to_dict()
        return payload

    def diff(self, body: dict[str, Any]) -> dict[str, Any]:
        """Returns the diff of the editing proposal."""
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

        return diff_result.to_dict()

    def form_preview(self, body: dict[str, Any]) -> dict[str, Any]:
        """Returns a diff preview from form editing input."""
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

        response_payload = diff_result.to_dict()
        response_payload["candidate_workflow"] = candidate_workflow
        response_payload["candidate_ui_state"] = candidate_ui_state
        return response_payload

    def catalog_preview(self, body: dict[str, Any]) -> dict[str, Any]:
        """Returns a preview of the workflow's catalog configuration."""
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

        return catalog_preview.to_dict()

    def save(self, body: dict[str, Any]) -> dict[str, Any]:
        """Saves the editing proposal."""
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
                    details={"report": exc.report.to_dict()},
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

    def validate_live(self, body: dict[str, Any]) -> dict[str, Any]:
        """Validates a workflow payload without computing a diff.

        Args:
            body: Request body containing the ``workflow`` payload to validate.

        Returns:
            Dictionary with ``validation_report`` holding the structured report.
        """
        candidate_workflow = body.get("workflow")
        if not isinstance(candidate_workflow, dict):
            raise StudioBadRequestError(error="workflow must be a mapping")

        with self._config.lock:
            workflow_path, _ = self._require_active_target_paths()
            report = validate_workflow_payload_for_ui(
                payload=candidate_workflow,
                workflow_path=workflow_path,
                bundle_root=self._config.bundle_root,
            )

        return {"validation_report": report.to_dict()}

    def rollback(self, body: dict[str, Any]) -> dict[str, Any]:
        """Restores using the specified backup ID."""
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
        """Returns the currently selected workflow/ui_state paths. Returns `None` if not selected."""
        workflow_path = self._config.workflow_path
        ui_state_path = self._config.ui_state_path
        if workflow_path is None or ui_state_path is None:
            return None
        return workflow_path, ui_state_path

    def _require_active_target_paths(self) -> tuple[Path, Path]:
        """Requires and retrieves the currently selected target. Raises an error if not selected."""
        target_paths = self._active_target_paths()
        if target_paths is not None:
            return target_paths
        raise StudioConflictError(
            error="studio_target_required",
            message="workflow target is not selected",
        )
