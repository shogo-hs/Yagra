"""Generates display models for workflow form editing."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from typing import Any

import yaml

from yagra.application.services.reference_resolver import resolve_workflow_references
from yagra.application.use_cases.workflow_edit_session import compute_workflow_revision

_logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class WorkflowNodeFormItem:
    """Holds node display information for form editing."""

    id: str
    handler: str
    prompt_ref: str | None
    prompt_system: str | None
    prompt_user: str | None
    model: dict[str, Any] | None

    def to_dict(self) -> dict[str, Any]:
        """Converts to a dict in API response format.

        Returns:
            Dictionary containing id, handler, prompt_ref, prompt_system, prompt_user, and model.
        """
        return {
            "id": self.id,
            "handler": self.handler,
            "prompt_ref": self.prompt_ref,
            "prompt_system": self.prompt_system,
            "prompt_user": self.prompt_user,
            "model": self.model,
        }


@dataclass(frozen=True, slots=True)
class WorkflowEdgeFormItem:
    """Holds edge display information for form editing."""

    index: int
    source: str
    target: str
    condition: str | None

    def to_dict(self) -> dict[str, Any]:
        """Converts to a dict in API response format.

        Returns:
            Dictionary containing index, source, target, and condition.
        """
        return {
            "index": self.index,
            "source": self.source,
            "target": self.target,
            "condition": self.condition,
        }


@dataclass(frozen=True, slots=True)
class WorkflowFormView:
    """Holds the display model for the form editing screen."""

    revision: str
    nodes: tuple[WorkflowNodeFormItem, ...]
    edges: tuple[WorkflowEdgeFormItem, ...]
    prompt_catalog_keys: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Converts to a dict in API response format.

        Returns:
            Dictionary containing revision, nodes, edges, and prompt_catalog_keys.
        """
        return {
            "revision": self.revision,
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
            "prompt_catalog_keys": list(self.prompt_catalog_keys),
        }


@dataclass(frozen=True, slots=True)
class WorkflowCatalogIssue:
    """Represents an issue encountered while loading a catalog."""

    code: str
    message: str
    location: tuple[str | int, ...]

    def to_dict(self) -> dict[str, Any]:
        """Converts to a dict in API response format.

        Returns:
            Dictionary containing code, message, and location.
        """
        return {"code": self.code, "message": self.message, "location": list(self.location)}


@dataclass(frozen=True, slots=True)
class WorkflowCatalogPreview:
    """Represents a preview of the catalog configuration in workflow.params."""

    prompt_catalog_path: str | None
    prompt_catalog_keys: tuple[str, ...]
    issues: tuple[WorkflowCatalogIssue, ...]

    def to_dict(self) -> dict[str, Any]:
        """Converts to a dict in API response format.

        Returns:
            Dictionary containing prompt_catalog_path, prompt_catalog_keys, and issues.
        """
        return {
            "prompt_catalog_path": self.prompt_catalog_path,
            "prompt_catalog_keys": list(self.prompt_catalog_keys),
            "issues": [issue.to_dict() for issue in self.issues],
        }


def build_workflow_form_view(
    workflow: Mapping[str, Any],
    ui_state: Mapping[str, Any],
    workflow_path: str | PathLike[str],
    bundle_root: str | PathLike[str] | None = None,
) -> WorkflowFormView:
    """Builds a form editing display model from a workflow and UI state.

    Args:
        workflow: Workflow data to display.
        ui_state: Current UI sidecar data.
        workflow_path: Path to the workflow file.
        bundle_root: Base directory for split reference resolution.

    Returns:
        `WorkflowFormView` containing the information required for form display.

    Raises:
        ValueError: If the workflow structure is unexpected.
    """
    workflow_abspath = Path(workflow_path).expanduser().resolve()
    bundle_root_path = Path(bundle_root).expanduser().resolve() if bundle_root is not None else None

    # Resolve prompt_ref to allow retrieval of prompt.user
    try:
        resolved_workflow = resolve_workflow_references(
            payload=dict(workflow),
            workflow_path=workflow_abspath,
            bundle_root=bundle_root_path,
        )
    except Exception as exc:
        _logger.debug("prompt_ref resolution failed in build_workflow_form_view: %s", exc)
        resolved_workflow = dict(workflow)

    resolved_nodes_raw = resolved_workflow.get("nodes", []) or []
    resolved_by_id: dict[str, dict[str, Any]] = {}
    for rn in resolved_nodes_raw:
        if isinstance(rn, Mapping) and isinstance(rn.get("id"), str):
            resolved_by_id[rn["id"]] = dict(rn)

    workflow_mapping = _ensure_mapping(workflow, label="workflow")
    ui_state_mapping = _ensure_mapping(ui_state, label="ui_state")
    nodes_raw = workflow_mapping.get("nodes", [])
    edges_raw = workflow_mapping.get("edges", [])
    if nodes_raw is None:
        nodes_raw = []
    if edges_raw is None:
        edges_raw = []
    if not isinstance(nodes_raw, list):
        raise ValueError("workflow.nodes must be a list when present")
    if not isinstance(edges_raw, list):
        raise ValueError("workflow.edges must be a list when present")

    nodes: list[WorkflowNodeFormItem] = []
    for node_raw in nodes_raw:
        if not isinstance(node_raw, Mapping):
            continue
        node = dict(node_raw)
        node_id = node.get("id")
        handler = node.get("handler")
        if not isinstance(node_id, str) or not isinstance(handler, str):
            continue
        params = node.get("params")
        if params is None:
            params = {}
        if not isinstance(params, Mapping):
            continue
        params_mapping = dict(params)
        # Retrieve prompt.system and prompt.user from the resolved node
        resolved_node = resolved_by_id.get(node_id, {})
        resolved_params = resolved_node.get("params") or {}
        resolved_prompt = (
            resolved_params.get("prompt") if isinstance(resolved_params, Mapping) else None
        )
        # When whole-workflow resolution failed for this node, attempt individual
        # prompt_ref resolution so that one failing node does not block all others.
        if resolved_prompt is None:
            prompt_ref_str = _as_optional_string(params_mapping.get("prompt_ref"))
            if prompt_ref_str is not None:
                resolved_prompt = _try_load_prompt_ref(
                    prompt_ref=prompt_ref_str,
                    workflow_path=workflow_abspath,
                    bundle_root=bundle_root_path,
                )
        prompt_system: str | None = None
        prompt_user: str | None = None
        if isinstance(resolved_prompt, Mapping):
            s = resolved_prompt.get("system")
            if isinstance(s, str):
                prompt_system = s
            u = resolved_prompt.get("user")
            if isinstance(u, str):
                prompt_user = u
        nodes.append(
            WorkflowNodeFormItem(
                id=node_id,
                handler=handler,
                prompt_ref=_as_optional_string(params_mapping.get("prompt_ref")),
                prompt_system=prompt_system,
                prompt_user=prompt_user,
                model=_as_optional_mapping(params_mapping.get("model")),
            )
        )

    edges: list[WorkflowEdgeFormItem] = []
    for index, edge_raw in enumerate(edges_raw):
        if not isinstance(edge_raw, Mapping):
            continue
        edge = dict(edge_raw)
        source = edge.get("source")
        target = edge.get("target")
        condition = edge.get("condition")
        if not isinstance(source, str) or not isinstance(target, str):
            continue
        if condition is not None and not isinstance(condition, str):
            continue
        edges.append(
            WorkflowEdgeFormItem(
                index=index,
                source=source,
                target=target,
                condition=condition,
            )
        )

    return WorkflowFormView(
        revision=compute_workflow_revision(workflow_mapping, ui_state_mapping),
        nodes=tuple(nodes),
        edges=tuple(edges),
        prompt_catalog_keys=(),
    )


def build_workflow_catalog_preview(
    workflow: Mapping[str, Any],
    workflow_path: str | PathLike[str],
    bundle_root: str | PathLike[str] | None = None,
) -> WorkflowCatalogPreview:
    """Resolves the catalog configuration in workflow.params and returns candidate keys and issues.

    Args:
        workflow: Workflow data.
        workflow_path: Path to the workflow file.
        bundle_root: Base directory for split reference resolution.

    Returns:
        Catalog configuration preview.
    """
    workflow_mapping = _ensure_mapping(workflow, label="workflow")
    workflow_abspath = Path(workflow_path).expanduser().resolve()
    bundle_root_path = Path(bundle_root).expanduser().resolve() if bundle_root is not None else None
    params_raw = workflow_mapping.get("params")
    if params_raw is None:
        params_raw = {}
    if not isinstance(params_raw, Mapping):
        return WorkflowCatalogPreview(
            prompt_catalog_path=None,
            prompt_catalog_keys=(),
            issues=(
                WorkflowCatalogIssue(
                    code="invalid_workflow_params",
                    message="workflow.params must be a mapping",
                    location=("params",),
                ),
            ),
        )

    params = dict(params_raw)
    prompt_catalog_path, prompt_catalog_keys, prompt_issues = _resolve_catalog_setting(
        workflow_abspath=workflow_abspath,
        bundle_root=bundle_root_path,
        params=params,
        catalog_name="prompt_catalog",
    )
    return WorkflowCatalogPreview(
        prompt_catalog_path=prompt_catalog_path,
        prompt_catalog_keys=prompt_catalog_keys,
        issues=tuple(prompt_issues),
    )


def _resolve_catalog_setting(
    workflow_abspath: Path,
    bundle_root: Path | None,
    params: Mapping[str, Any],
    catalog_name: str,
) -> tuple[str | None, tuple[str, ...], list[WorkflowCatalogIssue]]:
    """Resolves a single catalog configuration and returns key candidates and issues."""
    location = ("params", catalog_name)
    catalog_path_raw = params.get(catalog_name)
    if catalog_path_raw is None:
        return None, (), []
    if not isinstance(catalog_path_raw, str):
        return (
            None,
            (),
            [
                WorkflowCatalogIssue(
                    code="catalog_path_type_error",
                    message=f"{catalog_name} must be a string",
                    location=location,
                )
            ],
        )
    if not catalog_path_raw.strip():
        return None, (), []

    catalog_path = _resolve_catalog_path(
        catalog_path=catalog_path_raw.strip(),
        workflow_abspath=workflow_abspath,
        bundle_root=bundle_root,
    )
    catalog_abspath = str(catalog_path)
    if not catalog_path.exists():
        return (
            catalog_abspath,
            (),
            [
                WorkflowCatalogIssue(
                    code="catalog_not_found",
                    message=f"catalog file not found: {catalog_path}",
                    location=location,
                )
            ],
        )

    try:
        with catalog_path.open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle)
    except (OSError, yaml.YAMLError) as exc:
        return (
            catalog_abspath,
            (),
            [
                WorkflowCatalogIssue(
                    code="catalog_load_error",
                    message=f"catalog file load failed: {catalog_path}: {exc}",
                    location=location,
                )
            ],
        )

    if not isinstance(payload, Mapping):
        return (
            catalog_abspath,
            (),
            [
                WorkflowCatalogIssue(
                    code="catalog_not_mapping",
                    message=f"catalog must be a mapping: {catalog_path}",
                    location=location,
                )
            ],
        )

    key_paths = _collect_key_paths(dict(payload), prefix="")
    return catalog_abspath, tuple(sorted(set(key_paths))), []


def _resolve_catalog_path(
    catalog_path: str, workflow_abspath: Path, bundle_root: Path | None
) -> Path:
    """Resolves a catalog path to an absolute path relative to the workflow.

    Args:
        catalog_path: Catalog path specified in the workflow.
        workflow_abspath: Absolute path to the workflow file.
        bundle_root: Base directory for split reference resolution.

    Returns:
        Resolved absolute path.
    """
    raw_path = Path(catalog_path)
    if raw_path.is_absolute():
        return raw_path.resolve()
    if bundle_root is not None:
        return (bundle_root / raw_path).resolve()
    return (workflow_abspath.parent / raw_path).resolve()


def _collect_key_paths(payload: dict[str, Any], prefix: str) -> list[str]:
    """Recursively traverses a dict and returns a list of keys in `a.b.c` format.

    Args:
        payload: Dictionary to traverse.
        prefix: Parent key prefix.

    Returns:
        Collected list of key paths.
    """
    paths: list[str] = []
    for key, value in payload.items():
        if not isinstance(key, str):
            continue
        current = f"{prefix}.{key}" if prefix else key
        paths.append(current)
        if isinstance(value, Mapping):
            paths.extend(_collect_key_paths(dict(value), prefix=current))
    return paths


def _try_load_prompt_ref(
    prompt_ref: str,
    workflow_path: Path,
    bundle_root: Path | None,
) -> Any | None:
    """Attempts to load a prompt_ref file and return its content.

    Parses the prompt_ref string (splitting on ``#`` for an optional section
    anchor), resolves the file path relative to the workflow directory or
    bundle_root, loads the YAML, and optionally extracts the named section.

    Args:
        prompt_ref: Relative file path string, optionally with a ``#section``
            anchor (e.g. ``"prompts/chat.yaml#default"``).
        workflow_path: Absolute path to the workflow file. The parent directory
            is used as the base for relative path resolution when ``bundle_root``
            is ``None``.
        bundle_root: Optional base directory that overrides the workflow parent
            for relative path resolution.

    Returns:
        The loaded YAML content (or the extracted section when an anchor is
        present), or ``None`` when the file cannot be read or parsed for any reason.
    """
    try:
        section: str | None
        if "#" in prompt_ref:
            file_part, _section_raw = prompt_ref.split("#", 1)
            section = _section_raw.strip() or None
        else:
            file_part, section = prompt_ref, None

        raw_path = Path(file_part.strip())
        if raw_path.is_absolute():
            file_path = raw_path.resolve()
        elif bundle_root is not None:
            file_path = (bundle_root / raw_path).resolve()
        else:
            file_path = (workflow_path.parent / raw_path).resolve()

        raw = file_path.read_text(encoding="utf-8")
        data = yaml.safe_load(raw)

        if section is not None:
            if isinstance(data, dict):
                return data.get(section)
            return None
        return data
    except Exception:
        return None


def _as_optional_mapping(value: Any) -> dict[str, Any] | None:
    """Normalizes the value as an arbitrary dict.

    Args:
        value: Value to convert.

    Returns:
        Dictionary value, or `None`.
    """
    if not isinstance(value, Mapping):
        return None
    return deepcopy(dict(value))


def _as_optional_string(value: Any) -> str | None:
    """Normalizes the value as an arbitrary string.

    Args:
        value: Value to convert.

    Returns:
        String value, or `None`.
    """
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized:
        return None
    return normalized


def _ensure_mapping(payload: Mapping[str, Any], label: str) -> dict[str, Any]:
    """Validates that the input is dict-compatible and converts it to a dict.

    Args:
        payload: Data to validate.
        label: Input name used in error messages.

    Returns:
        Shallow-copied dictionary data.

    Raises:
        ValueError: If payload is not dict-compatible.
    """
    if not isinstance(payload, Mapping):
        raise ValueError(f"{label} must be a mapping")
    return dict(payload)
