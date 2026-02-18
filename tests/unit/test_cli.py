from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
import yaml

import yagra
from yagra import main

FIXTURES_ROOT = Path(__file__).resolve().parents[1] / "fixtures"
WORKFLOW_ROOT = FIXTURES_ROOT / "workflows"


def _base_payload() -> dict[str, Any]:
    return {
        "version": "1.0",
        "start_at": "router",
        "end_at": ["finish"],
        "nodes": [
            {"id": "router", "handler": "router_handler"},
            {"id": "planner", "handler": "planner_handler"},
            {"id": "finish", "handler": "finish_handler"},
        ],
        "edges": [
            {"source": "router", "target": "planner"},
            {"source": "planner", "target": "finish"},
        ],
    }


def _write_workflow(path: Path, payload: dict[str, Any]) -> Path:
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


class TestSchemaCommand:
    """yagra schema サブコマンドのテスト。"""

    def test_schema_outputs_valid_json_to_stdout(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Schema コマンドが GraphSpec の JSON Schema を標準出力すること。"""
        monkeypatch.setattr(sys, "argv", ["yagra", "schema"])

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 0

        captured = capsys.readouterr()
        schema = json.loads(captured.out)
        assert "properties" in schema
        assert "nodes" in schema["properties"]
        assert "edges" in schema["properties"]

    def test_schema_writes_to_file(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Schema コマンドが --output 指定時にファイルへ書き出すこと。"""
        output_path = tmp_path / "schema.json"
        monkeypatch.setattr(
            sys,
            "argv",
            ["yagra", "schema", "--output", str(output_path)],
        )

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 0
        assert output_path.exists()

        schema = json.loads(output_path.read_text(encoding="utf-8"))
        assert "properties" in schema

        captured = capsys.readouterr()
        assert "schema exported:" in captured.out


class TestValidateCommand:
    """yagra validate サブコマンドのテスト。"""

    def test_validate_valid_workflow_text(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """有効なワークフローで終了コード 0 と passed メッセージを返すこと。"""
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "yagra",
                "validate",
                "--workflow",
                str(WORKFLOW_ROOT / "branch-inline.yaml"),
            ],
        )

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 0

        captured = capsys.readouterr()
        assert "passed" in captured.out

    def test_validate_invalid_workflow_text(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """無効なワークフローで終了コード 1 とエラーメッセージを返すこと。"""
        payload = _base_payload()
        del payload["edges"]
        invalid_path = _write_workflow(tmp_path / "invalid.yaml", payload)

        monkeypatch.setattr(
            sys,
            "argv",
            ["yagra", "validate", "--workflow", str(invalid_path)],
        )

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 1

        captured = capsys.readouterr()
        assert "workflow validation failed" in captured.err

    def test_validate_valid_workflow_json(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """有効なワークフローの JSON 出力で is_valid が true であること。"""
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "yagra",
                "validate",
                "--workflow",
                str(WORKFLOW_ROOT / "branch-inline.yaml"),
                "--format",
                "json",
            ],
        )

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 0

        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result["is_valid"] is True
        assert result["issues"] == []

    def test_validate_invalid_workflow_json(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """無効なワークフローの JSON 出力で is_valid が false かつ issues が存在すること。"""
        payload = _base_payload()
        del payload["edges"]
        invalid_path = _write_workflow(tmp_path / "invalid.yaml", payload)

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "yagra",
                "validate",
                "--workflow",
                str(invalid_path),
                "--format",
                "json",
            ],
        )

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 1

        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result["is_valid"] is False
        assert len(result["issues"]) > 0
        assert "code" in result["issues"][0]
        assert "message" in result["issues"][0]
        assert "location" in result["issues"][0]


def test_main_visualize_generates_html(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_path = tmp_path / "view.html"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "yagra",
            "visualize",
            "--workflow",
            str(WORKFLOW_ROOT / "branch-inline.yaml"),
            "--output",
            str(output_path),
            "--title",
            "CLI Demo",
        ],
    )

    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 0
    assert output_path.exists()
    html_text = output_path.read_text(encoding="utf-8")
    assert "CLI Demo" in html_text

    captured = capsys.readouterr()
    assert "workflow visualization generated:" in captured.out


def test_main_visualize_returns_error_for_invalid_workflow(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = _base_payload()
    del payload["edges"]
    invalid_path = _write_workflow(tmp_path / "invalid.yaml", payload)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "yagra",
            "visualize",
            "--workflow",
            str(invalid_path),
            "--output",
            str(tmp_path / "invalid.html"),
        ],
    )

    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 1

    captured = capsys.readouterr()
    assert "workflow validation failed" in captured.err


def test_main_studio_starts_and_stops_server(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake_server = MagicMock()
    fake_server.serve_forever.return_value = None
    fake_server.server_close.return_value = None
    monkeypatch.setattr(yagra, "create_workflow_studio_server", lambda **_: fake_server)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "yagra",
            "studio",
            "--workflow",
            str(WORKFLOW_ROOT / "branch-inline.yaml"),
            "--port",
            "8899",
        ],
    )

    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 0
    fake_server.serve_forever.assert_called_once()
    fake_server.server_close.assert_called_once()

    captured = capsys.readouterr()
    assert "workflow studio started:" in captured.out


def test_main_studio_starts_without_workflow(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake_server = MagicMock()
    fake_server.serve_forever.return_value = None
    fake_server.server_close.return_value = None
    captured_args: dict[str, Any] = {}

    def _fake_create_server(**kwargs: Any) -> Any:
        captured_args.update(kwargs)
        return fake_server

    monkeypatch.setattr(yagra, "create_workflow_studio_server", _fake_create_server)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "yagra",
            "studio",
            "--port",
            "8899",
        ],
    )

    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 0
    fake_server.serve_forever.assert_called_once()
    fake_server.server_close.assert_called_once()
    assert captured_args["workflow_path"] is None

    captured = capsys.readouterr()
    assert "workflow studio started:" in captured.out


def test_main_studio_rejects_ui_state_without_workflow(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    called = False

    def _fake_create_server(**_: Any) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(yagra, "create_workflow_studio_server", _fake_create_server)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "yagra",
            "studio",
            "--ui-state",
            "/tmp/workflow.workflow-ui.json",
        ],
    )

    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 2
    assert called is False
    captured = capsys.readouterr()
    assert "--ui-state は --workflow 指定時のみ利用できます。" in captured.err


class TestValidateCommandStdin:
    """yagra validate --workflow - (stdin) のテスト。"""

    def _valid_yaml(self) -> str:
        return yaml.safe_dump(_base_payload(), sort_keys=False, allow_unicode=True)

    def test_validate_stdin_valid_yaml_exits_zero(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """stdin に有効な YAML を渡すと終了コード 0 と passed メッセージを返すこと。"""
        import io

        monkeypatch.setattr(sys, "stdin", io.StringIO(self._valid_yaml()))
        monkeypatch.setattr(sys, "argv", ["yagra", "validate", "--workflow", "-"])

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 0
        captured = capsys.readouterr()
        assert "passed" in captured.out

    def test_validate_stdin_valid_yaml_json_format(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """stdin に有効な YAML を渡して --format json を指定すると is_valid が true であること。"""
        import io

        monkeypatch.setattr(sys, "stdin", io.StringIO(self._valid_yaml()))
        monkeypatch.setattr(
            sys, "argv", ["yagra", "validate", "--workflow", "-", "--format", "json"]
        )

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 0
        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result["is_valid"] is True
        assert result["issues"] == []

    def test_validate_stdin_invalid_yaml_syntax_exits_one(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """stdin に YAML パースエラーがある文字列を渡すと終了コード 1 を返すこと。"""
        import io

        broken_yaml = "key: [unclosed bracket"
        monkeypatch.setattr(sys, "stdin", io.StringIO(broken_yaml))
        monkeypatch.setattr(sys, "argv", ["yagra", "validate", "--workflow", "-"])

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert "workflow validation failed" in captured.err

    def test_validate_stdin_invalid_yaml_syntax_json_format(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """stdin に YAML パースエラーがある文字列を --format json で渡すと is_valid が false かつ issues が存在すること。"""
        import io

        broken_yaml = "key: [unclosed bracket"
        monkeypatch.setattr(sys, "stdin", io.StringIO(broken_yaml))
        monkeypatch.setattr(
            sys, "argv", ["yagra", "validate", "--workflow", "-", "--format", "json"]
        )

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 1
        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result["is_valid"] is False
        assert len(result["issues"]) > 0
        assert result["issues"][0]["code"] == "schema_error"

    def test_validate_stdin_non_mapping_yaml_exits_one(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """stdin にマッピングでない YAML (リスト等) を渡すと終了コード 1 を返すこと。"""
        import io

        list_yaml = "- item1\n- item2\n"
        monkeypatch.setattr(sys, "stdin", io.StringIO(list_yaml))
        monkeypatch.setattr(sys, "argv", ["yagra", "validate", "--workflow", "-"])

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert "workflow validation failed" in captured.err

    def test_validate_stdin_invalid_workflow_schema_exits_one(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """stdin にスキーマ不正な YAML (edges 欠損) を渡すと終了コード 1 を返すこと。"""
        import io

        payload = _base_payload()
        del payload["edges"]
        invalid_yaml = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)
        monkeypatch.setattr(sys, "stdin", io.StringIO(invalid_yaml))
        monkeypatch.setattr(sys, "argv", ["yagra", "validate", "--workflow", "-"])

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert "workflow validation failed" in captured.err
