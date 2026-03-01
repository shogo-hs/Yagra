"""Unit tests for the ``yagra prompt info`` CLI command."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

from yagra import main as yagra_main


def _write_yaml(path: Path, data: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


class TestPromptInfoCommand:
    """Tests for ``yagra prompt info``."""

    def test_info_with_meta(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Displays version and prompt keys when _meta is present."""
        prompt_file = tmp_path / "prompts.yaml"
        _write_yaml(
            prompt_file,
            {
                "_meta": {"version": "2.0", "changelog": ["2.0: Updated"]},
                "greeting": {"system": "Hello", "user": "Hi"},
                "farewell": {"system": "Bye", "user": "Goodbye"},
            },
        )
        monkeypatch.setattr(
            sys,
            "argv",
            ["yagra", "prompt", "info", "--file", str(prompt_file)],
        )

        with pytest.raises(SystemExit, match="0"):
            yagra_main()

        captured = capsys.readouterr()
        assert "Version: 2.0" in captured.out
        assert "greeting" in captured.out
        assert "farewell" in captured.out
        assert "2.0: Updated" in captured.out

    def test_info_without_meta(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Shows '(not set)' when _meta is absent."""
        prompt_file = tmp_path / "prompts.yaml"
        _write_yaml(
            prompt_file,
            {
                "greeting": {"system": "Hello", "user": "Hi"},
            },
        )
        monkeypatch.setattr(
            sys,
            "argv",
            ["yagra", "prompt", "info", "--file", str(prompt_file)],
        )

        with pytest.raises(SystemExit, match="0"):
            yagra_main()

        captured = capsys.readouterr()
        assert "(not set)" in captured.out
        assert "greeting" in captured.out

    def test_info_json_format(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """JSON output contains expected fields."""
        prompt_file = tmp_path / "prompts.yaml"
        _write_yaml(
            prompt_file,
            {
                "_meta": {"version": "1.0"},
                "greeting": {"system": "Hello", "user": "Hi"},
            },
        )
        monkeypatch.setattr(
            sys,
            "argv",
            ["yagra", "prompt", "info", "--file", str(prompt_file), "--format", "json"],
        )

        with pytest.raises(SystemExit, match="0"):
            yagra_main()

        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result["version"] == "1.0"
        assert "greeting" in result["prompt_keys"]
        assert "_meta" not in result["prompt_keys"]

    def test_info_file_not_found(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Returns exit code 1 when file does not exist."""
        missing = tmp_path / "nonexistent.yaml"
        monkeypatch.setattr(
            sys,
            "argv",
            ["yagra", "prompt", "info", "--file", str(missing)],
        )

        with pytest.raises(SystemExit, match="1"):
            yagra_main()

        captured = capsys.readouterr()
        assert "file not found" in captured.err

    def test_info_invalid_yaml(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Returns exit code 1 for invalid YAML."""
        bad_file = tmp_path / "bad.yaml"
        bad_file.write_text("{{invalid yaml", encoding="utf-8")
        monkeypatch.setattr(
            sys,
            "argv",
            ["yagra", "prompt", "info", "--file", str(bad_file)],
        )

        with pytest.raises(SystemExit, match="1"):
            yagra_main()

        captured = capsys.readouterr()
        assert "failed to parse YAML" in captured.err

    def test_info_non_mapping_yaml(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Returns exit code 1 when YAML is not a mapping."""
        list_file = tmp_path / "list.yaml"
        list_file.write_text("- item1\n- item2\n", encoding="utf-8")
        monkeypatch.setattr(
            sys,
            "argv",
            ["yagra", "prompt", "info", "--file", str(list_file)],
        )

        with pytest.raises(SystemExit, match="1"):
            yagra_main()

        captured = capsys.readouterr()
        assert "must be a YAML mapping" in captured.err

    def test_info_empty_prompt_keys(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Shows '(none)' when there are no prompt keys."""
        prompt_file = tmp_path / "empty.yaml"
        _write_yaml(prompt_file, {"_meta": {"version": "1.0"}})
        monkeypatch.setattr(
            sys,
            "argv",
            ["yagra", "prompt", "info", "--file", str(prompt_file)],
        )

        with pytest.raises(SystemExit, match="0"):
            yagra_main()

        captured = capsys.readouterr()
        assert "(none)" in captured.out
