"""Unit tests for @version parsing and PromptVersionInfo collection."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from yagra.application.services.reference_resolver import (
    PromptVersionInfo,
    _parse_prompt_ref,
    resolve_workflow_references,
)


def _write_yaml(path: Path, data: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# _parse_prompt_ref unit tests
# ---------------------------------------------------------------------------


class TestParsePromptRef:
    """Tests for the _parse_prompt_ref helper function."""

    def test_file_only(self) -> None:
        """Plain file path without key or version."""
        assert _parse_prompt_ref("prompts.yaml") == ("prompts.yaml", None, None)

    def test_file_with_key(self) -> None:
        """File with key, no version."""
        assert _parse_prompt_ref("prompts.yaml#greeting") == (
            "prompts.yaml",
            "greeting",
            None,
        )

    def test_file_with_key_and_version(self) -> None:
        """File with key and version suffix."""
        assert _parse_prompt_ref("prompts.yaml#greeting@v2") == (
            "prompts.yaml",
            "greeting",
            "v2",
        )

    def test_file_with_version_no_key(self) -> None:
        """File with version but no key."""
        assert _parse_prompt_ref("prompts.yaml@v2") == (
            "prompts.yaml",
            None,
            "v2",
        )

    def test_dotted_key_with_version(self) -> None:
        """Dotted key path with version suffix."""
        assert _parse_prompt_ref("catalog.yaml#messages.system@1.0") == (
            "catalog.yaml",
            "messages.system",
            "1.0",
        )

    def test_empty_version_after_at_ignored(self) -> None:
        """Trailing @ with empty version is treated as no version."""
        assert _parse_prompt_ref("prompts.yaml#greeting@") == (
            "prompts.yaml",
            "greeting@",
            None,
        )

    def test_empty_key_after_hash(self) -> None:
        """Hash with empty key returns empty string to signal error."""
        path, key, version = _parse_prompt_ref("prompts.yaml#")
        assert path == "prompts.yaml"
        assert key == ""
        assert version is None

    def test_at_in_directory_path(self) -> None:
        """@ in directory name is not treated as version separator."""
        # No # separator, so @ is checked in path part
        # "user@host/prompts.yaml" — the @ splits path, but the part before is not empty
        assert _parse_prompt_ref("user@host/prompts.yaml") == (
            "user",
            None,
            "host/prompts.yaml",
        )

    def test_file_with_key_at_only_in_key(self) -> None:
        """Key containing @ but with empty version part."""
        # "file#key@" — version part is empty after strip
        assert _parse_prompt_ref("file.yaml#key@") == (
            "file.yaml",
            "key@",
            None,
        )

    def test_whitespace_handling(self) -> None:
        """Whitespace is stripped from all components."""
        assert _parse_prompt_ref("  prompts.yaml # greeting @ v2  ") == (
            "prompts.yaml",
            "greeting",
            "v2",
        )


# ---------------------------------------------------------------------------
# resolve_workflow_references with prompt_version_collector
# ---------------------------------------------------------------------------


class TestPromptVersionCollector:
    """Tests for version info collection during reference resolution."""

    def _make_payload(self, prompt_ref: str) -> dict[str, Any]:
        return {
            "version": "1.0",
            "start_at": "a",
            "end_at": ["a"],
            "nodes": [
                {"id": "a", "handler": "llm", "params": {"prompt_ref": prompt_ref}},
            ],
            "edges": [],
        }

    def test_collector_receives_version_info(self, tmp_path: Path) -> None:
        """Collector is populated with PromptVersionInfo on resolution."""
        catalog = tmp_path / "prompts.yaml"
        _write_yaml(
            catalog,
            {
                "_meta": {"version": "1.0"},
                "greeting": {"system": "Hello", "user": "Hi"},
            },
        )
        workflow_path = tmp_path / "workflow.yaml"
        workflow_path.write_text("", encoding="utf-8")

        collector: list[PromptVersionInfo] = []
        resolve_workflow_references(
            self._make_payload("prompts.yaml#greeting@1.0"),
            workflow_path,
            prompt_version_collector=collector,
        )
        assert len(collector) == 1
        assert collector[0].version_requested == "1.0"
        assert collector[0].version_actual == "1.0"
        assert collector[0].key_path == "greeting"

    def test_collector_version_mismatch(self, tmp_path: Path) -> None:
        """Collector captures version mismatch."""
        catalog = tmp_path / "prompts.yaml"
        _write_yaml(
            catalog,
            {
                "_meta": {"version": "2.0"},
                "greeting": {"system": "Hello", "user": "Hi"},
            },
        )
        workflow_path = tmp_path / "workflow.yaml"
        workflow_path.write_text("", encoding="utf-8")

        collector: list[PromptVersionInfo] = []
        resolve_workflow_references(
            self._make_payload("prompts.yaml#greeting@1.0"),
            workflow_path,
            prompt_version_collector=collector,
        )
        assert collector[0].version_requested == "1.0"
        assert collector[0].version_actual == "2.0"

    def test_collector_no_meta_version(self, tmp_path: Path) -> None:
        """Collector records None when _meta.version is absent."""
        catalog = tmp_path / "prompts.yaml"
        _write_yaml(catalog, {"greeting": {"system": "Hello", "user": "Hi"}})
        workflow_path = tmp_path / "workflow.yaml"
        workflow_path.write_text("", encoding="utf-8")

        collector: list[PromptVersionInfo] = []
        resolve_workflow_references(
            self._make_payload("prompts.yaml#greeting@v1"),
            workflow_path,
            prompt_version_collector=collector,
        )
        assert collector[0].version_requested == "v1"
        assert collector[0].version_actual is None

    def test_collector_meta_exists_no_version_requested(self, tmp_path: Path) -> None:
        """Collector records actual version when no @version in prompt_ref."""
        catalog = tmp_path / "prompts.yaml"
        _write_yaml(
            catalog,
            {
                "_meta": {"version": "3.0"},
                "greeting": {"system": "Hello", "user": "Hi"},
            },
        )
        workflow_path = tmp_path / "workflow.yaml"
        workflow_path.write_text("", encoding="utf-8")

        collector: list[PromptVersionInfo] = []
        resolve_workflow_references(
            self._make_payload("prompts.yaml#greeting"),
            workflow_path,
            prompt_version_collector=collector,
        )
        assert collector[0].version_requested is None
        assert collector[0].version_actual == "3.0"

    def test_collector_none_skips_collection(self, tmp_path: Path) -> None:
        """When collector is None, no error occurs (backward compat)."""
        catalog = tmp_path / "prompts.yaml"
        _write_yaml(catalog, {"greeting": {"system": "Hello", "user": "Hi"}})
        workflow_path = tmp_path / "workflow.yaml"
        workflow_path.write_text("", encoding="utf-8")

        # Should not raise
        resolve_workflow_references(
            self._make_payload("prompts.yaml#greeting"),
            workflow_path,
            prompt_version_collector=None,
        )

    def test_collector_numeric_meta_version(self, tmp_path: Path) -> None:
        """Numeric _meta.version is converted to string."""
        catalog = tmp_path / "prompts.yaml"
        _write_yaml(
            catalog,
            {
                "_meta": {"version": 2},
                "greeting": {"system": "Hello", "user": "Hi"},
            },
        )
        workflow_path = tmp_path / "workflow.yaml"
        workflow_path.write_text("", encoding="utf-8")

        collector: list[PromptVersionInfo] = []
        resolve_workflow_references(
            self._make_payload("prompts.yaml#greeting"),
            workflow_path,
            prompt_version_collector=collector,
        )
        assert collector[0].version_actual == "2"

    def test_collector_multiple_nodes(self, tmp_path: Path) -> None:
        """Collector accumulates entries for multiple nodes."""
        catalog = tmp_path / "prompts.yaml"
        _write_yaml(
            catalog,
            {
                "_meta": {"version": "1.0"},
                "greeting": {"system": "Hello", "user": "Hi"},
                "farewell": {"system": "Bye", "user": "Goodbye"},
            },
        )
        workflow_path = tmp_path / "workflow.yaml"
        workflow_path.write_text("", encoding="utf-8")

        payload: dict[str, Any] = {
            "version": "1.0",
            "start_at": "a",
            "end_at": ["b"],
            "nodes": [
                {
                    "id": "a",
                    "handler": "llm",
                    "params": {"prompt_ref": "prompts.yaml#greeting@1.0"},
                },
                {"id": "b", "handler": "llm", "params": {"prompt_ref": "prompts.yaml#farewell"}},
            ],
            "edges": [{"from": "a", "to": "b"}],
        }
        collector: list[PromptVersionInfo] = []
        resolve_workflow_references(
            payload,
            workflow_path,
            prompt_version_collector=collector,
        )
        assert len(collector) == 2
        assert collector[0].key_path == "greeting"
        assert collector[0].version_requested == "1.0"
        assert collector[1].key_path == "farewell"
        assert collector[1].version_requested is None

    def test_version_in_file_only_ref(self, tmp_path: Path) -> None:
        """file@version without key works correctly."""
        catalog = tmp_path / "prompts.yaml"
        _write_yaml(
            catalog,
            {
                "_meta": {"version": "1.0"},
                "system": "Hello",
                "user": "Hi",
            },
        )
        workflow_path = tmp_path / "workflow.yaml"
        workflow_path.write_text("", encoding="utf-8")

        collector: list[PromptVersionInfo] = []
        resolve_workflow_references(
            self._make_payload("prompts.yaml@1.0"),
            workflow_path,
            prompt_version_collector=collector,
        )
        assert collector[0].version_requested == "1.0"
        assert collector[0].key_path is None
