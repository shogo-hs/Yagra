from __future__ import annotations

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
