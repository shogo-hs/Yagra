from __future__ import annotations

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
    """Tests for the yagra schema subcommand."""

    def test_schema_outputs_valid_json_to_stdout(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """The schema command should output the GraphSpec JSON Schema to stdout."""
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
        """The schema command should write to a file when --output is specified."""
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
    """Tests for the yagra validate subcommand."""

    def test_validate_valid_workflow_text(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Should return exit code 0 and a passed message for a valid workflow."""
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
        """Should return exit code 1 and an error message for an invalid workflow."""
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
        """The JSON output for a valid workflow should have is_valid set to true."""
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
        error_issues = [i for i in result["issues"] if i["severity"] == "error"]
        assert error_issues == []

    def test_validate_invalid_workflow_json(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """The JSON output for an invalid workflow should have is_valid set to false and issues present."""
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
    assert "--ui-state is only available when --workflow is specified." in captured.err


class TestValidateCommandStdin:
    """Tests for yagra validate --workflow - (stdin)."""

    def _valid_yaml(self) -> str:
        return yaml.safe_dump(_base_payload(), sort_keys=False, allow_unicode=True)

    def test_validate_stdin_valid_yaml_exits_zero(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Should return exit code 0 and a passed message when valid YAML is passed to stdin."""
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
        """Should have is_valid set to true when valid YAML is passed to stdin with --format json."""
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
        """Should return exit code 1 when a string with a YAML parse error is passed to stdin."""
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
        """Should have is_valid set to false and issues present when a YAML parse error string is passed to stdin with --format json."""
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
        """Should return exit code 1 when non-mapping YAML (such as a list) is passed to stdin."""
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
        """Should return exit code 1 when schema-invalid YAML (missing edges) is passed to stdin."""
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
    """Tests for the TypeError branch of Yagra.invoke."""

    def test_invoke_raises_type_error_when_graph_returns_non_mapping(self) -> None:
        """Should raise TypeError when compiled_graph returns a non-Mapping value."""
        fake_graph = MagicMock()
        fake_graph.invoke.return_value = "not-a-mapping"

        instance = yagra.Yagra(compiled_graph=fake_graph)

        with pytest.raises(TypeError, match="compiled graph returned non-mapping result"):
            instance.invoke({"key": "value"})


# ---------------------------------------------------------------------------
# _normalize_registry
# ---------------------------------------------------------------------------


class TestNormalizeRegistry:
    """Tests for the TypeError branch of _normalize_registry."""

    def test_raises_type_error_for_invalid_registry_type(self) -> None:
        """Should raise TypeError when a type that is neither NodeRegistryPort nor Mapping is passed."""
        with pytest.raises(TypeError, match="registry must be NodeRegistryPort or mapping"):
            _normalize_registry(42)  # type: ignore[arg-type]

    def test_returns_registry_port_unchanged(self) -> None:
        """Should return the NodeRegistryPort unchanged when one is passed."""
        registry = InMemoryNodeRegistry({})
        result = _normalize_registry(registry)
        assert result is registry

    def test_wraps_plain_mapping(self) -> None:
        """Should wrap a dict in InMemoryNodeRegistry and return it."""
        result = _normalize_registry({})
        assert isinstance(result, InMemoryNodeRegistry)


# ---------------------------------------------------------------------------
# init command
# ---------------------------------------------------------------------------


class TestInitCommand:
    """Tests for the yagra init subcommand."""

    def test_list_with_templates_returns_zero(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Should return exit code 0 when templates exist with --list."""
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
        """Should return exit code 1 when no templates exist with --list."""
        monkeypatch.setattr(sys, "argv", ["yagra", "init", "--list"])
        monkeypatch.setattr(yagra, "list_templates", lambda: [])

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert "No templates available." in captured.out

    def test_no_template_arg_returns_two(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Should return exit code 2 when neither --template nor --list is specified."""
        monkeypatch.setattr(sys, "argv", ["yagra", "init"])

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 2
        captured = capsys.readouterr()
        assert "--template or --list" in captured.err

    def test_unknown_template_returns_one(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Should return exit code 1 when a nonexistent template name is specified."""
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
        """Should return exit code 1 when existing files are present at the output destination and --force is not specified."""
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
# studio command: KeyboardInterrupt branch
# ---------------------------------------------------------------------------


def test_main_studio_keyboard_interrupt_exits_zero(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Should return exit code 0 even when serve_forever raises KeyboardInterrupt."""
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
# explain command
# ---------------------------------------------------------------------------


class TestExplainCommand:
    """Tests for the yagra explain subcommand."""

    def test_explain_valid_workflow_json_format(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Should return exit code 0 and JSON for a valid workflow with --format json."""
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
        """Should return exit code 0 and text output for a valid workflow with --format text."""
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
        """Should return exit code 1 and an error message for an invalid workflow."""
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
# mcp command
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Yagra.compiled_graph property
# ---------------------------------------------------------------------------


class TestYagraCompiledGraphProperty:
    """Tests for the Yagra.compiled_graph property."""

    def test_compiled_graph_returns_held_graph(self) -> None:
        """Should return the compiled graph passed to __init__."""
        fake_graph = MagicMock()
        instance = yagra.Yagra(compiled_graph=fake_graph)
        assert instance.compiled_graph is fake_graph


# ---------------------------------------------------------------------------
# Yagra.resume
# ---------------------------------------------------------------------------


class TestYagraResume:
    """Tests for the Yagra.resume method."""

    def test_resume_raises_type_error_when_graph_returns_non_mapping(self) -> None:
        """Should raise TypeError when compiled_graph returns a non-Mapping value."""
        fake_graph = MagicMock()
        fake_graph.invoke.return_value = "not-a-mapping"
        instance = yagra.Yagra(compiled_graph=fake_graph)

        with pytest.raises(TypeError, match="compiled graph returned non-mapping result"):
            instance.resume()

    def test_resume_returns_dict_on_success(self) -> None:
        """Should return a dict when compiled_graph returns a Mapping."""
        fake_graph = MagicMock()
        fake_graph.invoke.return_value = {"result": "ok"}
        instance = yagra.Yagra(compiled_graph=fake_graph)

        result = instance.resume(thread_id="t1")
        assert result == {"result": "ok"}

    def test_resume_with_update_calls_update_state(self) -> None:
        """Should call update_state when update is provided."""
        fake_graph = MagicMock()
        fake_graph.invoke.return_value = {"result": "ok"}
        instance = yagra.Yagra(compiled_graph=fake_graph)

        instance.resume(update={"key": "new_value"}, thread_id="t1")
        fake_graph.update_state.assert_called_once()


# ---------------------------------------------------------------------------
# handlers command
# ---------------------------------------------------------------------------


class TestHandlersCommand:
    """Tests for the yagra handlers subcommand."""

    def test_handlers_text_format_outputs_handler_info(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Should return exit code 0 and print handler names in text format."""
        monkeypatch.setattr(sys, "argv", ["yagra", "handlers"])

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 0
        captured = capsys.readouterr()
        assert "llm" in captured.out
        assert "structured_llm" in captured.out
        assert "streaming_llm" in captured.out

    def test_handlers_json_format_outputs_valid_json(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Should return exit code 0 and output valid JSON for --format json."""
        monkeypatch.setattr(sys, "argv", ["yagra", "handlers", "--format", "json"])

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "handlers" in data
        handler_names = [h["name"] for h in data["handlers"]]
        assert "llm" in handler_names
        assert "structured_llm" in handler_names
        assert "streaming_llm" in handler_names


# ---------------------------------------------------------------------------
# main() unknown command fallback (SystemExit(2))
# ---------------------------------------------------------------------------


def test_main_unknown_command_exits_two(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Should exit with code 2 when no subcommand is matched."""
    # Bypass argparse by directly invoking main with a fake args object that
    # sets command to an unknown value after parser runs.
    import argparse

    fake_args = argparse.Namespace(command="__unknown_command__")

    def _fake_parse(self: argparse.ArgumentParser, *args: Any, **kwargs: Any) -> argparse.Namespace:
        return fake_args

    monkeypatch.setattr(argparse.ArgumentParser, "parse_args", _fake_parse)

    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 2


# ---------------------------------------------------------------------------
# init --list: template without use_case (line 295)
# ---------------------------------------------------------------------------


class TestInitListTemplateWithoutUseCase:
    """Tests for the init --list branch with templates lacking use_case."""

    def test_list_template_without_use_case_shows_name_only(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Template entries without use_case should show only the name."""
        from yagra.application.services.template_initializer import TemplateInfo

        monkeypatch.setattr(sys, "argv", ["yagra", "init", "--list"])
        monkeypatch.setattr(yagra, "list_templates", lambda: ["plain"])
        monkeypatch.setattr(
            yagra,
            "list_templates_with_info",
            lambda: [TemplateInfo(name="plain", description="", use_case="")],
        )

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 0
        captured = capsys.readouterr()
        assert "plain" in captured.out
        # No use_case bracket should appear
        assert "[" not in captured.out


# ---------------------------------------------------------------------------
# init --template: success path with workflow validation (lines 323-340)
# ---------------------------------------------------------------------------


class TestInitCommandSuccessPath:
    """Tests for the init subcommand success path including workflow validation."""

    def test_init_success_with_valid_generated_workflow(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Should return exit code 0 and show validation success when init succeeds."""
        from yagra.application.use_cases import WorkflowValidationReport

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

        # Create a dummy workflow.yaml so the validation branch is reached
        workflow_yaml = tmp_path / "workflow.yaml"
        workflow_yaml.write_text("version: '1.0'\n", encoding="utf-8")

        def _fake_initialize(**_: Any) -> None:
            pass  # no-op; file already created above

        valid_report = WorkflowValidationReport(issues=[])

        monkeypatch.setattr(yagra, "initialize_from_template", _fake_initialize)
        monkeypatch.setattr(yagra, "validate_workflow_for_ui", lambda **_: valid_report)

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 0
        captured = capsys.readouterr()
        assert "workflow is valid" in captured.out

    def test_init_success_with_invalid_generated_workflow(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Should return exit code 1 when the generated workflow fails validation."""
        from yagra.application.use_cases import (
            WorkflowValidationIssue,
            WorkflowValidationReport,
        )

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

        # Create a dummy workflow.yaml so the validation branch is reached
        workflow_yaml = tmp_path / "workflow.yaml"
        workflow_yaml.write_text("version: '1.0'\n", encoding="utf-8")

        def _fake_initialize(**_: Any) -> None:
            pass

        invalid_report = WorkflowValidationReport(
            issues=[
                WorkflowValidationIssue(
                    code="schema_error",
                    message="missing required field",
                    location=(),
                )
            ]
        )

        monkeypatch.setattr(yagra, "initialize_from_template", _fake_initialize)
        monkeypatch.setattr(yagra, "validate_workflow_for_ui", lambda **_: invalid_report)

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert captured.err != ""

    def test_init_success_without_workflow_yaml(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Should return exit code 0 when init succeeds but no workflow.yaml is generated."""
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

        def _fake_initialize(**_: Any) -> None:
            pass  # no-op; don't create workflow.yaml

        monkeypatch.setattr(yagra, "initialize_from_template", _fake_initialize)

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 0
        captured = capsys.readouterr()
        assert "Initialized from template" in captured.out


# ---------------------------------------------------------------------------
# analyze command
# ---------------------------------------------------------------------------


class TestAnalyzeCommand:
    """Tests for the yagra analyze subcommand."""

    def _make_trace(
        self,
        trace_dir: Path,
        workflow_name: str = "test_wf",
        *,
        status: str = "success",
        duration_ms: float = 100.0,
        node_id: str = "node_a",
        include_error_type: bool = False,
        include_cost: bool = False,
    ) -> None:
        """Write a minimal trace JSON file."""
        wf_dir = trace_dir / workflow_name
        wf_dir.mkdir(parents=True, exist_ok=True)
        node: dict[str, Any] = {
            "node_id": node_id,
            "status": status,
            "duration_ms": duration_ms,
        }
        if include_error_type:
            node["error"] = {"error_type": "ValueError"}
        trace: dict[str, Any] = {
            "workflow_name": workflow_name,
            "started_at": "2024-01-01T00:00:00Z",
            "ended_at": "2024-01-01T00:00:01Z",
            "status": status,
            "summary": {
                "total_duration_ms": duration_ms,
                "total_prompt_tokens": 10,
                "total_completion_tokens": 5,
                "total_tokens": 15,
            },
            "nodes": [node],
        }
        if include_cost:
            trace["summary"]["total_estimated_cost_usd"] = 0.001
        import uuid

        (wf_dir / f"{uuid.uuid4()}.json").write_text(json.dumps(trace), encoding="utf-8")

    def test_analyze_no_traces_returns_one(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Should return exit code 1 when no traces are found."""
        empty_dir = tmp_path / "traces"
        empty_dir.mkdir()
        monkeypatch.setattr(
            sys,
            "argv",
            ["yagra", "analyze", "--trace-dir", str(empty_dir)],
        )

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert "No traces found" in captured.err

    def test_analyze_text_format(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Should return exit code 0 and text output when traces exist."""
        trace_dir = tmp_path / "traces"
        self._make_trace(trace_dir)
        monkeypatch.setattr(
            sys,
            "argv",
            ["yagra", "analyze", "--trace-dir", str(trace_dir)],
        )

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 0
        captured = capsys.readouterr()
        assert "Workflow:" in captured.out
        assert "Runs:" in captured.out

    def test_analyze_json_format(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Should return exit code 0 and valid JSON when --format json is specified."""
        trace_dir = tmp_path / "traces"
        self._make_trace(trace_dir)
        monkeypatch.setattr(
            sys,
            "argv",
            ["yagra", "analyze", "--trace-dir", str(trace_dir), "--format", "json"],
        )

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "workflow_name" in data
        assert "total_runs" in data

    def test_analyze_with_workflow_filter(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Should filter traces by workflow name when --workflow is specified."""
        trace_dir = tmp_path / "traces"
        self._make_trace(trace_dir, workflow_name="target_wf")
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "yagra",
                "analyze",
                "--trace-dir",
                str(trace_dir),
                "--workflow",
                "target_wf",
            ],
        )

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 0

    def test_analyze_with_limit(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Should limit trace count when --limit is specified."""
        trace_dir = tmp_path / "traces"
        for _ in range(3):
            self._make_trace(trace_dir)
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "yagra",
                "analyze",
                "--trace-dir",
                str(trace_dir),
                "--limit",
                "1",
            ],
        )

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 0
        captured = capsys.readouterr()
        assert "Workflow:" in captured.out

    def test_analyze_text_with_node_stats_and_errors(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Should print per-node table and error types when node has errors."""
        trace_dir = tmp_path / "traces"
        self._make_trace(trace_dir, status="error", include_error_type=True)
        monkeypatch.setattr(
            sys,
            "argv",
            ["yagra", "analyze", "--trace-dir", str(trace_dir)],
        )

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 0
        captured = capsys.readouterr()
        assert "Node" in captured.out
        assert "error:" in captured.out

    def test_analyze_text_with_estimated_cost(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Should print estimated cost when it is present in trace data."""
        trace_dir = tmp_path / "traces"
        self._make_trace(trace_dir, include_cost=True)
        monkeypatch.setattr(
            sys,
            "argv",
            ["yagra", "analyze", "--trace-dir", str(trace_dir)],
        )

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 0
        captured = capsys.readouterr()
        assert "Estimated cost:" in captured.out
        assert "N/A" not in captured.out

    def test_analyze_text_estimated_cost_none(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Should print 'N/A' for estimated cost when no cost data is available."""
        trace_dir = tmp_path / "traces"
        self._make_trace(trace_dir, include_cost=False)
        monkeypatch.setattr(
            sys,
            "argv",
            ["yagra", "analyze", "--trace-dir", str(trace_dir)],
        )

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 0
        captured = capsys.readouterr()
        assert "Estimated cost: N/A" in captured.out

    def test_analyze_text_with_no_node_stats(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Should print 'No node statistics available.' when trace has no node data."""
        trace_dir = tmp_path / "traces"
        wf_dir = trace_dir / "test_wf"
        wf_dir.mkdir(parents=True)
        # Trace with empty nodes list -> no node_stats after aggregation
        trace: dict[str, Any] = {
            "workflow_name": "test_wf",
            "started_at": "2024-01-01T00:00:00Z",
            "ended_at": "2024-01-01T00:00:01Z",
            "status": "success",
            "summary": {
                "total_duration_ms": 50.0,
                "total_prompt_tokens": 0,
                "total_completion_tokens": 0,
                "total_tokens": 0,
            },
            "nodes": [],
        }
        import uuid

        (wf_dir / f"{uuid.uuid4()}.json").write_text(json.dumps(trace), encoding="utf-8")
        monkeypatch.setattr(
            sys,
            "argv",
            ["yagra", "analyze", "--trace-dir", str(trace_dir)],
        )

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 0
        captured = capsys.readouterr()
        assert "No node statistics available." in captured.out


class TestMcpCommand:
    """Tests for the yagra mcp subcommand."""

    def test_mcp_not_installed_returns_one(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Should return exit code 1 when the mcp package is not installed."""
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
        """Should call asyncio.run when the mcp package is installed."""
        monkeypatch.setattr(sys, "argv", ["yagra", "mcp"])

        called: list[Any] = []

        # asyncio.run itself is monkeypatched to avoid event loop conflict
        # when running inside pytest's async runner.
        fake_asyncio = MagicMock()
        fake_asyncio.run = lambda coro: called.append(True)

        fake_mcp_server = MagicMock()
        fake_mcp_server.run_mcp_server = MagicMock(return_value=MagicMock())

        with patch.dict(
            "sys.modules",
            {
                "asyncio": fake_asyncio,
                "yagra.adapters.inbound.mcp_server": fake_mcp_server,
            },
        ):
            with pytest.raises(SystemExit) as exc:
                main()

        assert exc.value.code == 0
        assert called
