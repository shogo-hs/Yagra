from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import yaml

import yagra
from yagra import _normalize_registry, main
from yagra.adapters.outbound import InMemoryNodeRegistry

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
        """Stdin に有効な YAML を渡すと終了コード 0 と passed メッセージを返すこと。"""
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
        """Stdin に有効な YAML を渡して --format json を指定すると is_valid が true であること。"""
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
        """Stdin に YAML パースエラーがある文字列を渡すと終了コード 1 を返すこと。"""
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
        """Stdin に YAML パースエラーがある文字列を --format json で渡すと is_valid が false かつ issues が存在すること。"""
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
        """Stdin にマッピングでない YAML (リスト等) を渡すと終了コード 1 を返すこと。"""
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
        """Stdin にスキーマ不正な YAML (edges 欠損) を渡すと終了コード 1 を返すこと。"""
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


# ---------------------------------------------------------------------------
# Yagra.invoke
# ---------------------------------------------------------------------------


class TestYagraInvoke:
    """Yagra.invoke の TypeError ブランチのテスト。"""

    def test_invoke_raises_type_error_when_graph_returns_non_mapping(self) -> None:
        """compiled_graph が非 Mapping を返した場合に TypeError を送出すること。"""
        fake_graph = MagicMock()
        fake_graph.invoke.return_value = "not-a-mapping"

        instance = yagra.Yagra(compiled_graph=fake_graph)

        with pytest.raises(TypeError, match="compiled graph returned non-mapping result"):
            instance.invoke({"key": "value"})


# ---------------------------------------------------------------------------
# _normalize_registry
# ---------------------------------------------------------------------------


class TestNormalizeRegistry:
    """_normalize_registry の TypeError ブランチのテスト。"""

    def test_raises_type_error_for_invalid_registry_type(self) -> None:
        """NodeRegistryPort でも Mapping でもない型を渡すと TypeError を送出すること。"""
        with pytest.raises(TypeError, match="registry must be NodeRegistryPort or mapping"):
            _normalize_registry(42)  # type: ignore[arg-type]

    def test_returns_registry_port_unchanged(self) -> None:
        """NodeRegistryPort を渡すとそのまま返すこと。"""
        registry = InMemoryNodeRegistry({})
        result = _normalize_registry(registry)
        assert result is registry

    def test_wraps_plain_mapping(self) -> None:
        """dict を渡すと InMemoryNodeRegistry でラップして返すこと。"""
        result = _normalize_registry({})
        assert isinstance(result, InMemoryNodeRegistry)


# ---------------------------------------------------------------------------
# init コマンド
# ---------------------------------------------------------------------------


class TestInitCommand:
    """yagra init サブコマンドのテスト。"""

    def test_list_with_templates_returns_zero(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """--list でテンプレートが存在する場合に終了コード 0 を返すこと。"""
        monkeypatch.setattr(sys, "argv", ["yagra", "init", "--list"])
        monkeypatch.setattr(yagra, "list_templates", lambda: ["branch", "loop"])

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 0
        captured = capsys.readouterr()
        assert "branch" in captured.out
        assert "loop" in captured.out

    def test_list_with_no_templates_returns_one(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """--list でテンプレートが 0 件の場合に終了コード 1 を返すこと。"""
        monkeypatch.setattr(sys, "argv", ["yagra", "init", "--list"])
        monkeypatch.setattr(yagra, "list_templates", lambda: [])

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert "利用可能なテンプレートがありません" in captured.out

    def test_no_template_arg_returns_two(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """--template も --list も指定しない場合に終了コード 2 を返すこと。"""
        monkeypatch.setattr(sys, "argv", ["yagra", "init"])

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 2
        captured = capsys.readouterr()
        assert "--template または --list" in captured.err

    def test_unknown_template_returns_one(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """存在しないテンプレート名を指定すると終了コード 1 を返すこと。"""
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "yagra",
                "init",
                "--template",
                "nonexistent-template",
                "--output",
                str(tmp_path),
            ],
        )

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert "nonexistent-template" in captured.err

    def test_file_already_exists_without_force_returns_one(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """出力先に既存ファイルがあり --force なし の場合に終了コード 1 を返すこと。"""
        from yagra.application.services.template_initializer import FileAlreadyExistsError

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "yagra",
                "init",
                "--template",
                "branch",
                "--output",
                str(tmp_path),
            ],
        )

        def _raise_file_exists(**_: Any) -> None:
            raise FileAlreadyExistsError([tmp_path / "workflow.yaml"])

        monkeypatch.setattr(yagra, "initialize_from_template", _raise_file_exists)

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert captured.err != ""


# ---------------------------------------------------------------------------
# studio コマンド：KeyboardInterrupt ブランチ
# ---------------------------------------------------------------------------


def test_main_studio_keyboard_interrupt_exits_zero(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """serve_forever が KeyboardInterrupt を発生させた場合でも終了コード 0 を返すこと。"""
    fake_server = MagicMock()
    fake_server.serve_forever.side_effect = KeyboardInterrupt
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


# ---------------------------------------------------------------------------
# explain コマンド
# ---------------------------------------------------------------------------


class TestExplainCommand:
    """yagra explain サブコマンドのテスト。"""

    def test_explain_valid_workflow_json_format(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """有効なワークフローで --format json のとき終了コード 0 と JSON を返すこと。"""
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "yagra",
                "explain",
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
        assert "entry_point" in result
        assert "exit_points" in result
        assert "required_handlers" in result
        assert "execution_paths" in result

    def test_explain_valid_workflow_text_format(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """有効なワークフローで --format text のとき終了コード 0 とテキストを返すこと。"""
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "yagra",
                "explain",
                "--workflow",
                str(WORKFLOW_ROOT / "branch-inline.yaml"),
                "--format",
                "text",
            ],
        )

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 0
        captured = capsys.readouterr()
        assert "entry_point:" in captured.out
        assert "exit_points:" in captured.out

    def test_explain_invalid_workflow_returns_one(
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
            [
                "yagra",
                "explain",
                "--workflow",
                str(invalid_path),
            ],
        )

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert "workflow validation failed" in captured.err


# ---------------------------------------------------------------------------
# mcp コマンド
# ---------------------------------------------------------------------------


class TestMcpCommand:
    """yagra mcp サブコマンドのテスト。"""

    def test_mcp_not_installed_returns_one(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """mcp パッケージが未インストールのとき終了コード 1 を返すこと。"""
        monkeypatch.setattr(sys, "argv", ["yagra", "mcp"])

        import builtins

        original_import = builtins.__import__

        def _raise_import_error(name: str, *args: Any, **kwargs: Any) -> Any:
            if "mcp_server" in name:
                raise ImportError("No module named 'mcp'")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", _raise_import_error)

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert captured.err != ""

    def test_mcp_installed_runs_asyncio(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """mcp パッケージがインストール済みのとき asyncio.run が呼び出されること。"""
        monkeypatch.setattr(sys, "argv", ["yagra", "mcp"])

        called: list[Any] = []

        async def _fake_run_mcp_server() -> None:
            called.append(True)

        with patch.dict(
            "sys.modules",
            {"yagra.adapters.inbound.mcp_server": MagicMock(run_mcp_server=_fake_run_mcp_server)},
        ):
            with pytest.raises(SystemExit) as exc:
                main()

        assert exc.value.code == 0
        assert called
