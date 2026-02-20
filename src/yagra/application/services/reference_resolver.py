"""Resolves `prompt_ref` references in a workflow."""

from __future__ import annotations

from collections.abc import Sequence
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

type Location = tuple[str | int, ...]


class WorkflowReferenceError(ValueError):
    """Exception raised when split reference resolution in a workflow fails."""

    def __init__(self, message: str, location: Sequence[str | int] | None = None) -> None:
        """Initializes with exception message and issue location.

        Args:
            message: Message describing the reason for the failure.
            location: Path within the workflow where the problem occurred.
        """
        super().__init__(message)
        self.location: Location = tuple(location or ())


def resolve_workflow_references(
    payload: dict[str, Any],
    workflow_path: Path,
    bundle_root: Path | None = None,
) -> dict[str, Any]:
    """Resolves `prompt_ref` references in a workflow.

    Args:
        payload: Data from `workflow.yaml` converted to a dictionary.
        workflow_path: Absolute path to the entry workflow file.
        bundle_root: Base directory for split references. Defaults to the workflow parent if not specified.

    Returns:
        Workflow data with references resolved.

    Raises:
        WorkflowReferenceError: If the reference format is invalid, the reference target does not exist, or a key is undefined.
    """
    resolved = deepcopy(payload)
    params = resolved.get("params", {})
    if params is None:
        params = {}
    if not isinstance(params, dict):
        raise WorkflowReferenceError("workflow.params must be a mapping", location=("params",))
    resolved["params"] = params

    nodes = resolved.get("nodes")
    if not isinstance(nodes, list):
        return resolved

    for index, node in enumerate(nodes):
        if not isinstance(node, dict):
            raise WorkflowReferenceError(
                f"node[{index}] must be a mapping",
                location=("nodes", index),
            )

        node_params = node.get("params")
        if node_params is None:
            node_params = {}
            node["params"] = node_params
        if not isinstance(node_params, dict):
            raise WorkflowReferenceError(
                f"node[{index}].params must be a mapping",
                location=("nodes", index, "params"),
            )

        if "prompt" in node_params and node_params["prompt"] is not None:
            raise WorkflowReferenceError(
                "inline prompt is no longer supported; use prompt_ref to reference an external prompt file.\n"
                "Example – create prompts/my_prompt.yaml:\n"
                '  system: "You are a helpful assistant."\n'
                '  user: "Answer: {input}"\n'
                'Then set: prompt_ref: "prompts/my_prompt.yaml"',
                location=("nodes", index, "params", "prompt"),
            )

        prompt_ref = _as_optional_string(
            node_params.get("prompt_ref"),
            location=("nodes", index, "params", "prompt_ref"),
        )
        if prompt_ref is not None:
            resolved_prompt = _resolve_reference(
                reference=prompt_ref,
                workflow_path=workflow_path,
                bundle_root=bundle_root,
                ref_label="prompt_ref",
                location=("nodes", index, "params", "prompt_ref"),
            )
            node_params["prompt"] = resolved_prompt

        if "model_ref" in node_params:
            raise WorkflowReferenceError(
                "model_ref is no longer supported; define params.model inline",
                location=("nodes", index, "params", "model_ref"),
            )

    return resolved


def _resolve_reference(
    reference: str,
    workflow_path: Path,
    bundle_root: Path | None,
    ref_label: str,
    location: Location = (),
) -> Any:
    """Loads and resolves a single reference.

    Args:
        reference: The reference string to resolve.
        workflow_path: Absolute path to the entry workflow.
        bundle_root: Base directory for reference resolution.
        ref_label: Reference label for error messages.
        location: Workflow path where the problem occurred.

    Returns:
        The resolved value.

    Raises:
        WorkflowReferenceError: If the reference string or reference target is invalid.
    """
    raw_path, _, raw_key = reference.partition("#")
    catalog_path = raw_path.strip()
    if not catalog_path:
        raise WorkflowReferenceError(
            f"{ref_label} path is empty: {reference}",
            location=location,
        )
    key_path: str | None = raw_key.strip() if _ else None
    if key_path is not None and not key_path:
        raise WorkflowReferenceError(
            f"{ref_label} key is empty: {reference}",
            location=location,
        )

    target_path = _resolve_catalog_path(
        catalog_path=catalog_path,
        workflow_path=workflow_path,
        bundle_root=bundle_root,
    )
    try:
        catalog_data = _load_yaml_file(target_path, location=location)
    except WorkflowReferenceError:
        if _is_mcp_sentinel(workflow_path) and bundle_root is None:
            raise WorkflowReferenceError(
                f"reference file not found: {target_path}\n"
                "Hint: pass base_dir (the directory containing your workflow YAML) "
                "to resolve relative paths, or use validate_workflow_file / "
                "explain_workflow_file instead.",
                location=location,
            ) from None
        raise
    if key_path is None:
        return deepcopy(catalog_data)
    return _lookup_key_path(
        catalog_data,
        key_path,
        ref_label=ref_label,
        target_path=target_path,
        location=location,
    )


def _resolve_catalog_path(catalog_path: str, workflow_path: Path, bundle_root: Path | None) -> Path:
    """Resolves the real path of the referenced YAML."""
    raw = Path(catalog_path)
    if raw.is_absolute():
        return raw.resolve()

    workflow_relative_path = (workflow_path.parent / raw).resolve()

    if bundle_root is not None:
        return (bundle_root / raw).resolve()

    if _has_explicit_relative_prefix(raw):
        return workflow_relative_path

    if workflow_relative_path.exists():
        return workflow_relative_path

    for ancestor in workflow_path.parents[1:]:
        candidate = (ancestor / raw).resolve()
        if candidate.exists():
            return candidate

    return workflow_relative_path


def _has_explicit_relative_prefix(path: Path) -> bool:
    """Returns whether the path is an explicit relative path containing `./` or `../`."""
    return any(part in {".", ".."} for part in path.parts)


def _is_mcp_sentinel(workflow_path: Path) -> bool:
    """Returns whether the workflow_path is the MCP sentinel value."""
    return str(workflow_path) == "<mcp>"


def _load_yaml_file(path: Path, location: Location = ()) -> Any:
    """Loads a YAML file.

    Args:
        path: Path to the YAML file to load.
        location: Workflow path where the problem occurred.

    Returns:
        The parsed YAML object.

    Raises:
        WorkflowReferenceError: If the referenced file does not exist.
    """
    if not path.exists():
        raise WorkflowReferenceError(f"reference file not found: {path}", location=location)
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _lookup_key_path(
    data: Any,
    key_path: str,
    ref_label: str,
    target_path: Path,
    location: Location = (),
) -> Any:
    """Traverses YAML data using a key in `a.b.c` format.

    Args:
        data: The YAML data to traverse.
        key_path: Dot-separated key.
        ref_label: Reference label for error messages.
        target_path: Path to the referenced catalog.
        location: Workflow path where the problem occurred.

    Returns:
        The resolved value.

    Raises:
        WorkflowReferenceError: If the key is not found.
    """
    current = data
    for segment in key_path.split("."):
        if not isinstance(current, dict) or segment not in current:
            raise WorkflowReferenceError(
                f"{ref_label} key not found: {key_path} (file: {target_path})",
                location=location,
            )
        current = current[segment]
    return deepcopy(current)


def _as_optional_string(value: Any, location: Location = ()) -> str | None:
    """Normalizes the value as an arbitrary string.

    Args:
        value: The value to convert.
        location: Workflow path where the problem occurred.

    Returns:
        Normalized string. Whitespace-only strings become `None`.

    Raises:
        WorkflowReferenceError: If a non-string value is given.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        raise WorkflowReferenceError("reference value must be a string", location=location)
    normalized = value.strip()
    if not normalized:
        return None
    return normalized
