"""Unit tests for reference_resolver to improve coverage."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from yagra.application.services.reference_resolver import (
    WorkflowReferenceError,
    resolve_workflow_references,
)


def _write_yaml(path: Path, data: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# workflow.params handling
# ---------------------------------------------------------------------------


def test_resolve_workflow_references_params_none_becomes_empty_dict(tmp_path: Path) -> None:
    """Line 50: when params is None it should be replaced with an empty dict."""
    workflow_path = tmp_path / "workflow.yaml"
    workflow_path.write_text("", encoding="utf-8")
    payload: dict[str, Any] = {
        "version": "1.0",
        "start_at": "a",
        "end_at": ["a"],
        "nodes": [],
        "params": None,
    }
    result = resolve_workflow_references(payload, workflow_path)
    assert result["params"] == {}


def test_resolve_workflow_references_params_not_mapping_raises(tmp_path: Path) -> None:
    """Line 52: when params is not a mapping (e.g. a list) it should raise."""
    workflow_path = tmp_path / "workflow.yaml"
    workflow_path.write_text("", encoding="utf-8")
    payload: dict[str, Any] = {
        "version": "1.0",
        "start_at": "a",
        "params": ["not", "a", "dict"],
    }
    with pytest.raises(WorkflowReferenceError, match="workflow.params must be a mapping"):
        resolve_workflow_references(payload, workflow_path)


# ---------------------------------------------------------------------------
# _resolve_reference: empty catalog path
# ---------------------------------------------------------------------------


def test_resolve_workflow_references_empty_prompt_ref_path_raises(tmp_path: Path) -> None:
    """Line 134: catalog_path empty (prompt_ref is just '#key') should raise."""
    workflow_path = tmp_path / "workflow.yaml"
    workflow_path.write_text("", encoding="utf-8")
    payload: dict[str, Any] = {
        "version": "1.0",
        "start_at": "a",
        "end_at": ["a"],
        "nodes": [
            {"id": "a", "handler": "llm", "params": {"prompt_ref": "#some_key"}},
        ],
        "edges": [],
    }
    with pytest.raises(WorkflowReferenceError, match="path is empty"):
        resolve_workflow_references(payload, workflow_path)


def test_resolve_workflow_references_empty_key_after_hash_raises(tmp_path: Path) -> None:
    """Line 140: key path is empty (prompt_ref ends with '#') should raise."""
    workflow_path = tmp_path / "workflow.yaml"
    workflow_path.write_text("", encoding="utf-8")
    # Create a real file so path resolution works
    catalog = tmp_path / "prompts.yaml"
    _write_yaml(catalog, {"key": "value"})
    payload: dict[str, Any] = {
        "version": "1.0",
        "start_at": "a",
        "end_at": ["a"],
        "nodes": [
            {"id": "a", "handler": "llm", "params": {"prompt_ref": "prompts.yaml#"}},
        ],
        "edges": [],
    }
    with pytest.raises(WorkflowReferenceError, match="key is empty"):
        resolve_workflow_references(payload, workflow_path)


# ---------------------------------------------------------------------------
# _resolve_reference: MCP sentinel error path
# ---------------------------------------------------------------------------


def test_resolve_workflow_references_mcp_sentinel_gives_hint_on_missing_file() -> None:
    """Lines 154-160: MCP sentinel path with missing file should give a hint."""
    mcp_workflow_path = Path("<mcp>")
    catalog_filename = "non_existent_prompts.yaml"
    payload: dict[str, Any] = {
        "version": "1.0",
        "start_at": "a",
        "end_at": ["a"],
        "nodes": [
            {"id": "a", "handler": "llm", "params": {"prompt_ref": catalog_filename}},
        ],
        "edges": [],
    }
    with pytest.raises(WorkflowReferenceError, match="Hint: pass base_dir"):
        resolve_workflow_references(payload, mcp_workflow_path)


# ---------------------------------------------------------------------------
# _resolve_catalog_path: bundle_root and explicit relative prefix paths
# ---------------------------------------------------------------------------


def test_resolve_workflow_references_uses_bundle_root_when_provided(tmp_path: Path) -> None:
    """Line 182: when bundle_root is provided, references are resolved relative to it."""
    bundle_root = tmp_path / "bundle"
    bundle_root.mkdir()
    catalog = bundle_root / "prompts" / "catalog.yaml"
    _write_yaml(catalog, {"system": "Hello", "user": "Hi"})

    workflow_dir = tmp_path / "subdir"
    workflow_dir.mkdir()
    workflow_path = workflow_dir / "workflow.yaml"
    workflow_path.write_text("", encoding="utf-8")

    payload: dict[str, Any] = {
        "version": "1.0",
        "start_at": "a",
        "end_at": ["a"],
        "nodes": [
            {
                "id": "a",
                "handler": "llm",
                "params": {"prompt_ref": "prompts/catalog.yaml"},
            }
        ],
        "edges": [],
    }
    result = resolve_workflow_references(payload, workflow_path, bundle_root=bundle_root)
    assert result["nodes"][0]["params"]["prompt"] == {"system": "Hello", "user": "Hi"}


def test_resolve_workflow_references_uses_absolute_path(tmp_path: Path) -> None:
    """Line 177: absolute catalog path is resolved directly (is_absolute branch)."""
    workflow_path = tmp_path / "workflow.yaml"
    workflow_path.write_text("", encoding="utf-8")
    # Create a catalog at an absolute path
    catalog = tmp_path / "abs_catalog.yaml"
    _write_yaml(catalog, {"system": "Absolute", "user": "Path"})

    payload: dict[str, Any] = {
        "version": "1.0",
        "start_at": "a",
        "end_at": ["a"],
        "nodes": [
            {
                "id": "a",
                "handler": "llm",
                "params": {"prompt_ref": str(catalog.resolve())},
            }
        ],
        "edges": [],
    }
    result = resolve_workflow_references(payload, workflow_path)
    assert result["nodes"][0]["params"]["prompt"] == {"system": "Absolute", "user": "Path"}


def test_resolve_workflow_references_uses_explicit_relative_prefix_dotdot(tmp_path: Path) -> None:
    """Line 185: explicit ../ prefix forces workflow-relative path resolution (non-existent)."""
    # Create a nested workflow path
    workflow_dir = tmp_path / "workflows"
    workflow_dir.mkdir()
    workflow_path = workflow_dir / "workflow.yaml"
    workflow_path.write_text("", encoding="utf-8")
    # Place catalog in parent directory (accessed via ../)
    catalog = tmp_path / "catalog.yaml"
    _write_yaml(catalog, {"system": "Parent", "user": "Dir"})

    payload: dict[str, Any] = {
        "version": "1.0",
        "start_at": "a",
        "end_at": ["a"],
        "nodes": [
            {
                "id": "a",
                "handler": "llm",
                "params": {"prompt_ref": "../catalog.yaml"},
            }
        ],
        "edges": [],
    }
    result = resolve_workflow_references(payload, workflow_path)
    assert result["nodes"][0]["params"]["prompt"] == {"system": "Parent", "user": "Dir"}


# ---------------------------------------------------------------------------
# _lookup_key_path: key not found
# ---------------------------------------------------------------------------


def test_resolve_workflow_references_key_not_found_raises(tmp_path: Path) -> None:
    """Line 252: when the key is not found in the catalog, raise WorkflowReferenceError."""
    workflow_path = tmp_path / "workflow.yaml"
    workflow_path.write_text("", encoding="utf-8")
    catalog = tmp_path / "catalog.yaml"
    _write_yaml(catalog, {"existing_key": {"system": "s", "user": "u"}})

    payload: dict[str, Any] = {
        "version": "1.0",
        "start_at": "a",
        "end_at": ["a"],
        "nodes": [
            {
                "id": "a",
                "handler": "llm",
                "params": {"prompt_ref": "catalog.yaml#missing_key"},
            }
        ],
        "edges": [],
    }
    with pytest.raises(WorkflowReferenceError, match="key not found"):
        resolve_workflow_references(payload, workflow_path)


# ---------------------------------------------------------------------------
# _as_optional_string: non-string and whitespace-only
# ---------------------------------------------------------------------------


def test_resolve_workflow_references_prompt_ref_not_string_raises(tmp_path: Path) -> None:
    """Line 276: prompt_ref value that is not a string should raise."""
    workflow_path = tmp_path / "workflow.yaml"
    workflow_path.write_text("", encoding="utf-8")
    payload: dict[str, Any] = {
        "version": "1.0",
        "start_at": "a",
        "end_at": ["a"],
        "nodes": [
            {"id": "a", "handler": "llm", "params": {"prompt_ref": 12345}},
        ],
        "edges": [],
    }
    with pytest.raises(WorkflowReferenceError, match="reference value must be a string"):
        resolve_workflow_references(payload, workflow_path)


def test_resolve_workflow_references_prompt_ref_whitespace_only_is_ignored(
    tmp_path: Path,
) -> None:
    """Line 279: prompt_ref that is whitespace-only is treated as None (no resolution)."""
    workflow_path = tmp_path / "workflow.yaml"
    workflow_path.write_text("", encoding="utf-8")
    payload: dict[str, Any] = {
        "version": "1.0",
        "start_at": "a",
        "end_at": ["a"],
        "nodes": [
            {"id": "a", "handler": "llm", "params": {"prompt_ref": "   "}},
        ],
        "edges": [],
    }
    # Should not raise; whitespace-only prompt_ref is treated as absent
    result = resolve_workflow_references(payload, workflow_path)
    # prompt key should not have been set (no resolution happened)
    assert "prompt" not in result["nodes"][0]["params"]
