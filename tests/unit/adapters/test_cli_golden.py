"""Tests for yagra golden CLI subcommands (M-51, G-20).

Tests the golden save, test, and list CLI subcommands that manage
golden test cases for workflow regression testing.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from yagra import main
from yagra.domain.entities.comparison import ComparisonStrategy
from yagra.domain.entities.golden_case import (
    GoldenCase,
    GoldenTestResult,
    NodeComparisonResult,
    NodeSnapshot,
)


def _make_trace_dict(
    workflow_name: str = "test-wf",
    workflow_path: str | None = "/tmp/test-wf.yaml",
    status: str = "success",
) -> dict[str, Any]:
    """Creates a minimal trace dict for testing."""
    now = datetime.now(tz=UTC).isoformat()
    return {
        "schema_version": "1.0",
        "run_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "workflow_name": workflow_name,
        "workflow_version": "1.0",
        "workflow_path": workflow_path,
        "started_at": now,
        "ended_at": now,
        "status": status,
        "nodes": [
            {
                "node_id": "node_a",
                "handler": "llm",
                "status": "success",
                "started_at": now,
                "ended_at": now,
                "duration_ms": 100.0,
                "input_snapshot": {"input_text": "hello"},
                "output_snapshot": {"translated": "HELLO"},
            },
            {
                "node_id": "node_b",
                "handler": "formatter",
                "status": "success",
                "started_at": now,
                "ended_at": now,
                "duration_ms": 10.0,
                "input_snapshot": {"translated": "HELLO"},
                "output_snapshot": {"formatted": "[Result] HELLO"},
            },
        ],
        "summary": {
            "total_nodes_executed": 2,
            "succeeded_nodes": 2,
            "failed_nodes": 0,
            "total_duration_ms": 110.0,
            "total_prompt_tokens": 10,
            "total_completion_tokens": 5,
            "total_tokens": 15,
            "node_order": ["node_a", "node_b"],
        },
    }


def _write_trace(path: Path, trace_dict: dict[str, Any] | None = None) -> Path:
    """Writes a trace JSON file and returns the path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = trace_dict or _make_trace_dict()
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def _make_golden_case(
    case_name: str = "happy-path",
    workflow_name: str = "test-wf",
) -> GoldenCase:
    """Creates a minimal GoldenCase for testing."""
    now = datetime.now(tz=UTC)
    return GoldenCase(
        case_name=case_name,
        workflow_name=workflow_name,
        workflow_path="test-wf.yaml",
        created_at=now,
        source_run_id="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        initial_state={"input_text": "hello"},
        final_state={"input_text": "hello", "translated": "HELLO", "formatted": "[Result] HELLO"},
        execution_path=["node_a", "node_b"],
        node_snapshots={
            "node_a": NodeSnapshot(
                node_id="node_a",
                handler="llm",
                is_llm_handler=True,
                input_snapshot={"input_text": "hello"},
                output_snapshot={"translated": "HELLO"},
            ),
            "node_b": NodeSnapshot(
                node_id="node_b",
                handler="formatter",
                is_llm_handler=False,
                input_snapshot={"translated": "HELLO"},
                output_snapshot={"formatted": "[Result] HELLO"},
            ),
        },
        description="Test golden case",
    )


# ---------------------------------------------------------------------------
# golden save
# ---------------------------------------------------------------------------


class TestGoldenSaveCommand:
    """Tests for the yagra golden save subcommand."""

    def test_save_success(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Should save golden case and print success message."""
        trace_path = _write_trace(tmp_path / "trace.json")
        golden_dir = tmp_path / "golden"

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "yagra",
                "golden",
                "save",
                "--trace",
                str(trace_path),
                "--name",
                "happy-path",
                "--description",
                "A test case",
                "--golden-dir",
                str(golden_dir),
            ],
        )

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 0
        captured = capsys.readouterr()
        assert "Golden case saved:" in captured.out
        assert "happy-path" in captured.out

        # Verify the file was actually created
        golden_file = golden_dir / "test-wf" / "happy-path.json"
        assert golden_file.exists()

    def test_save_trace_file_not_found(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Should return exit code 1 when trace file does not exist."""
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "yagra",
                "golden",
                "save",
                "--trace",
                str(tmp_path / "nonexistent.json"),
                "--name",
                "test-case",
            ],
        )

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert "trace file not found" in captured.err

    def test_save_invalid_json_trace(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Should return exit code 1 when trace file contains invalid JSON."""
        bad_trace = tmp_path / "bad.json"
        bad_trace.write_text("{invalid json}", encoding="utf-8")

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "yagra",
                "golden",
                "save",
                "--trace",
                str(bad_trace),
                "--name",
                "test-case",
            ],
        )

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert "failed to read trace file" in captured.err

    def test_save_invalid_trace_format(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Should return exit code 1 when trace file has wrong schema."""
        bad_trace = tmp_path / "bad.json"
        bad_trace.write_text('{"not": "a trace"}', encoding="utf-8")

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "yagra",
                "golden",
                "save",
                "--trace",
                str(bad_trace),
                "--name",
                "test-case",
            ],
        )

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert "invalid trace format" in captured.err

    def test_save_invalid_case_name(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Should return exit code 1 when case name is not kebab-case."""
        trace_path = _write_trace(tmp_path / "trace.json")

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "yagra",
                "golden",
                "save",
                "--trace",
                str(trace_path),
                "--name",
                "Invalid Case Name",
            ],
        )

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert "Error:" in captured.err

    def test_save_failed_trace_rejected(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Should return exit code 1 when trace has error status."""
        trace_dict = _make_trace_dict(status="error")
        trace_path = _write_trace(tmp_path / "trace.json", trace_dict)

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "yagra",
                "golden",
                "save",
                "--trace",
                str(trace_path),
                "--name",
                "test-case",
            ],
        )

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert "Error:" in captured.err

    def test_save_with_default_golden_dir(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Should use .yagra/golden as default golden-dir."""
        trace_path = _write_trace(tmp_path / "trace.json")

        # Change cwd so .yagra/golden is created in tmp_path
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "yagra",
                "golden",
                "save",
                "--trace",
                str(trace_path),
                "--name",
                "default-dir-test",
            ],
        )

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 0
        assert (tmp_path / ".yagra" / "golden" / "test-wf" / "default-dir-test.json").exists()

    def test_save_with_single_strategy_override(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Should save a golden case with one explicit node strategy override."""
        trace_path = _write_trace(tmp_path / "trace.json")
        golden_dir = tmp_path / "golden"

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "yagra",
                "golden",
                "save",
                "--trace",
                str(trace_path),
                "--name",
                "single-strategy",
                "--golden-dir",
                str(golden_dir),
                "--strategy",
                "node_b:skip",
            ],
        )

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 0

        golden_file = golden_dir / "test-wf" / "single-strategy.json"
        payload = json.loads(golden_file.read_text(encoding="utf-8"))
        assert payload["node_snapshots"]["node_b"]["comparison_strategy"] == "skip"
        assert payload["node_snapshots"]["node_a"]["comparison_strategy"] == "auto"

    def test_save_with_multiple_strategy_overrides(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Should save a golden case with multiple per-node strategy overrides."""
        trace_path = _write_trace(tmp_path / "trace.json")
        golden_dir = tmp_path / "golden"

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "yagra",
                "golden",
                "save",
                "--trace",
                str(trace_path),
                "--name",
                "multi-strategy",
                "--golden-dir",
                str(golden_dir),
                "--strategy",
                "node_a:structural",
                "--strategy",
                "node_b:exact",
            ],
        )

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 0

        golden_file = golden_dir / "test-wf" / "multi-strategy.json"
        payload = json.loads(golden_file.read_text(encoding="utf-8"))
        assert payload["node_snapshots"]["node_a"]["comparison_strategy"] == "structural"
        assert payload["node_snapshots"]["node_b"]["comparison_strategy"] == "exact"

    def test_save_strategy_invalid_format(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Should return exit code 1 when --strategy format is invalid."""
        trace_path = _write_trace(tmp_path / "trace.json")

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "yagra",
                "golden",
                "save",
                "--trace",
                str(trace_path),
                "--name",
                "invalid-format",
                "--strategy",
                "invalid_format",
            ],
        )

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert "Invalid --strategy format" in captured.err
        assert "node_id:strategy" in captured.err

    def test_save_strategy_unknown_strategy(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Should return exit code 1 when --strategy uses an unknown value."""
        trace_path = _write_trace(tmp_path / "trace.json")

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "yagra",
                "golden",
                "save",
                "--trace",
                str(trace_path),
                "--name",
                "unknown-strategy",
                "--strategy",
                "node_a:unknown",
            ],
        )

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert "Unknown strategy 'unknown'" in captured.err
        assert "Valid strategies:" in captured.err

    def test_save_strategy_empty_node_id(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Should return exit code 1 when --strategy node_id is empty."""
        trace_path = _write_trace(tmp_path / "trace.json")

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "yagra",
                "golden",
                "save",
                "--trace",
                str(trace_path),
                "--name",
                "empty-node-id",
                "--strategy",
                ":exact",
            ],
        )

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert "Invalid --strategy format" in captured.err
        assert "node_id must not be empty" in captured.err

    def test_save_strategy_duplicate_node_id(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Should return exit code 1 when duplicate --strategy node_id is provided."""
        trace_path = _write_trace(tmp_path / "trace.json")

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "yagra",
                "golden",
                "save",
                "--trace",
                str(trace_path),
                "--name",
                "duplicate-node-id",
                "--strategy",
                "node_a:exact",
                "--strategy",
                "node_a:skip",
            ],
        )

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert "Duplicate --strategy for node 'node_a'" in captured.err


# ---------------------------------------------------------------------------
# golden test
# ---------------------------------------------------------------------------


class TestGoldenTestCommand:
    """Tests for the yagra golden test subcommand."""

    def test_test_workflow_not_found(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Should return exit code 1 when workflow file does not exist."""
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "yagra",
                "golden",
                "test",
                "--workflow",
                str(tmp_path / "nonexistent.yaml"),
            ],
        )

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert "workflow file not found" in captured.err

    def test_test_case_not_found(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Should return exit code 1 when named golden case does not exist."""
        workflow_path = tmp_path / "test-wf.yaml"
        workflow_path.write_text("version: '1.0'\n", encoding="utf-8")

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "yagra",
                "golden",
                "test",
                "--workflow",
                str(workflow_path),
                "--name",
                "nonexistent-case",
                "--golden-dir",
                str(tmp_path / "golden"),
            ],
        )

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert "golden case not found" in captured.err

    def test_test_no_cases_for_workflow(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Should return exit code 1 when no golden cases exist for workflow."""
        workflow_path = tmp_path / "test-wf.yaml"
        workflow_path.write_text("version: '1.0'\n", encoding="utf-8")
        golden_dir = tmp_path / "golden"
        golden_dir.mkdir(parents=True)

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "yagra",
                "golden",
                "test",
                "--workflow",
                str(workflow_path),
                "--golden-dir",
                str(golden_dir),
            ],
        )

        # Mock run_all to return empty list
        with patch(
            "yagra.application.use_cases.golden_test_runner.GoldenTestRunner.run_all",
            return_value=[],
        ):
            with pytest.raises(SystemExit) as exc:
                main()

        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert "No golden cases found" in captured.err

    def test_test_pass_text_format(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Should print PASS and exit 0 when all tests pass."""
        workflow_path = tmp_path / "test-wf.yaml"
        workflow_path.write_text("version: '1.0'\n", encoding="utf-8")

        now = datetime.now(tz=UTC)
        mock_result = GoldenTestResult(
            case_name="happy-path",
            workflow_name="test-wf",
            passed=True,
            executed_at=now,
            execution_path_match=True,
            expected_path=["node_a", "node_b"],
            actual_path=["node_a", "node_b"],
            node_results=[
                NodeComparisonResult(
                    node_id="node_a",
                    status="pass",
                    strategy_used=ComparisonStrategy.STRUCTURAL,
                    input_match=True,
                    output_match=True,
                    message="Node 'node_a' passed.",
                ),
            ],
            summary="Golden test 'happy-path': PASSED Nodes: 1 total, 1 passed, 0 failed, 0 skipped, 0 missing, 0 unexpected.",
        )

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "yagra",
                "golden",
                "test",
                "--workflow",
                str(workflow_path),
                "--golden-dir",
                str(tmp_path / "golden"),
            ],
        )

        with patch(
            "yagra.application.use_cases.golden_test_runner.GoldenTestRunner.run_all",
            return_value=[mock_result],
        ):
            with pytest.raises(SystemExit) as exc:
                main()

        assert exc.value.code == 0
        captured = capsys.readouterr()
        assert "PASS" in captured.out
        assert "happy-path" in captured.out

    def test_test_fail_text_format(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Should print FAIL, node details, and exit 1 when tests fail."""
        workflow_path = tmp_path / "test-wf.yaml"
        workflow_path.write_text("version: '1.0'\n", encoding="utf-8")

        now = datetime.now(tz=UTC)
        mock_result = GoldenTestResult(
            case_name="regression-case",
            workflow_name="test-wf",
            passed=False,
            executed_at=now,
            execution_path_match=False,
            expected_path=["node_a", "node_b"],
            actual_path=["node_a", "node_b", "node_c"],
            node_results=[
                NodeComparisonResult(
                    node_id="node_b",
                    status="fail",
                    strategy_used=ComparisonStrategy.EXACT,
                    input_match=True,
                    output_match=False,
                    message="Node 'node_b' failed: output mismatch.",
                ),
                NodeComparisonResult(
                    node_id="node_c",
                    status="unexpected",
                    strategy_used=ComparisonStrategy.EXACT,
                    message="Node 'node_c' executed but not expected.",
                ),
            ],
            summary="Golden test 'regression-case': FAILED Execution path mismatch.",
        )

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "yagra",
                "golden",
                "test",
                "--workflow",
                str(workflow_path),
                "--golden-dir",
                str(tmp_path / "golden"),
            ],
        )

        with patch(
            "yagra.application.use_cases.golden_test_runner.GoldenTestRunner.run_all",
            return_value=[mock_result],
        ):
            with pytest.raises(SystemExit) as exc:
                main()

        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert "FAIL" in captured.out
        assert "expected path:" in captured.out
        assert "actual path:" in captured.out
        assert "node_b" in captured.out

    def test_test_json_format(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Should output valid JSON when --format json is specified."""
        workflow_path = tmp_path / "test-wf.yaml"
        workflow_path.write_text("version: '1.0'\n", encoding="utf-8")

        now = datetime.now(tz=UTC)
        mock_result = GoldenTestResult(
            case_name="json-test",
            workflow_name="test-wf",
            passed=True,
            executed_at=now,
            execution_path_match=True,
            expected_path=["node_a"],
            actual_path=["node_a"],
            node_results=[],
            summary="Golden test 'json-test': PASSED",
        )

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "yagra",
                "golden",
                "test",
                "--workflow",
                str(workflow_path),
                "--golden-dir",
                str(tmp_path / "golden"),
                "--format",
                "json",
            ],
        )

        with patch(
            "yagra.application.use_cases.golden_test_runner.GoldenTestRunner.run_all",
            return_value=[mock_result],
        ):
            with pytest.raises(SystemExit) as exc:
                main()

        assert exc.value.code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["case_name"] == "json-test"
        assert data[0]["passed"] is True

    def test_test_specific_case_by_name(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Should run only the named case when --name is specified."""
        workflow_path = tmp_path / "test-wf.yaml"
        workflow_path.write_text("version: '1.0'\n", encoding="utf-8")

        golden_case = _make_golden_case()
        now = datetime.now(tz=UTC)
        mock_result = GoldenTestResult(
            case_name="happy-path",
            workflow_name="test-wf",
            passed=True,
            executed_at=now,
            execution_path_match=True,
            expected_path=["node_a", "node_b"],
            actual_path=["node_a", "node_b"],
            node_results=[],
            summary="Golden test 'happy-path': PASSED",
        )

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "yagra",
                "golden",
                "test",
                "--workflow",
                str(workflow_path),
                "--name",
                "happy-path",
                "--golden-dir",
                str(tmp_path / "golden"),
            ],
        )

        with (
            patch(
                "yagra.adapters.outbound.local_golden_case_store.LocalGoldenCaseStore.load",
                return_value=golden_case,
            ),
            patch(
                "yagra.application.use_cases.golden_test_runner.GoldenTestRunner.run",
                return_value=mock_result,
            ),
        ):
            with pytest.raises(SystemExit) as exc:
                main()

        assert exc.value.code == 0
        captured = capsys.readouterr()
        assert "PASS" in captured.out

    def test_test_execution_error_returns_one(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Should return exit code 1 when golden test execution raises an exception."""
        workflow_path = tmp_path / "test-wf.yaml"
        workflow_path.write_text("version: '1.0'\n", encoding="utf-8")

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "yagra",
                "golden",
                "test",
                "--workflow",
                str(workflow_path),
                "--golden-dir",
                str(tmp_path / "golden"),
            ],
        )

        with patch(
            "yagra.application.use_cases.golden_test_runner.GoldenTestRunner.run_all",
            side_effect=RuntimeError("workflow build failed"),
        ):
            with pytest.raises(SystemExit) as exc:
                main()

        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert "golden test execution failed" in captured.err


# ---------------------------------------------------------------------------
# golden list
# ---------------------------------------------------------------------------


class TestGoldenListCommand:
    """Tests for the yagra golden list subcommand."""

    def test_list_empty(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Should print 'No golden cases found.' when no cases exist."""
        golden_dir = tmp_path / "golden"
        golden_dir.mkdir(parents=True)

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "yagra",
                "golden",
                "list",
                "--golden-dir",
                str(golden_dir),
            ],
        )

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 0
        captured = capsys.readouterr()
        assert "No golden cases found." in captured.out

    def test_list_with_cases_text_format(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Should list golden cases in text format."""
        golden_dir = tmp_path / "golden"

        # Save a golden case first
        from yagra.adapters.outbound.local_golden_case_store import LocalGoldenCaseStore

        store = LocalGoldenCaseStore(base_dir=golden_dir)
        golden = _make_golden_case()
        store.save(golden)

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "yagra",
                "golden",
                "list",
                "--golden-dir",
                str(golden_dir),
            ],
        )

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 0
        captured = capsys.readouterr()
        assert "test-wf/happy-path" in captured.out
        assert "Test golden case" in captured.out
        assert "created:" in captured.out
        assert "nodes:" in captured.out

    def test_list_json_format(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Should output valid JSON when --format json is specified."""
        golden_dir = tmp_path / "golden"

        from yagra.adapters.outbound.local_golden_case_store import LocalGoldenCaseStore

        store = LocalGoldenCaseStore(base_dir=golden_dir)
        golden = _make_golden_case()
        store.save(golden)

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "yagra",
                "golden",
                "list",
                "--golden-dir",
                str(golden_dir),
                "--format",
                "json",
            ],
        )

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["case_name"] == "happy-path"
        assert data[0]["workflow_name"] == "test-wf"

    def test_list_with_workflow_filter(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Should filter by workflow name when --workflow is specified."""
        golden_dir = tmp_path / "golden"

        from yagra.adapters.outbound.local_golden_case_store import LocalGoldenCaseStore

        store = LocalGoldenCaseStore(base_dir=golden_dir)
        store.save(_make_golden_case(case_name="case-a", workflow_name="wf-alpha"))
        store.save(_make_golden_case(case_name="case-b", workflow_name="wf-beta"))

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "yagra",
                "golden",
                "list",
                "--workflow",
                "wf-alpha",
                "--golden-dir",
                str(golden_dir),
            ],
        )

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 0
        captured = capsys.readouterr()
        assert "wf-alpha/case-a" in captured.out
        assert "wf-beta" not in captured.out

    def test_list_empty_json_format(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Should output empty JSON array when no cases exist."""
        golden_dir = tmp_path / "golden"
        golden_dir.mkdir(parents=True)

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "yagra",
                "golden",
                "list",
                "--golden-dir",
                str(golden_dir),
                "--format",
                "json",
            ],
        )

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data == []

    def test_list_case_without_description(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Should not show description suffix when description is empty."""
        golden_dir = tmp_path / "golden"

        from yagra.adapters.outbound.local_golden_case_store import LocalGoldenCaseStore

        store = LocalGoldenCaseStore(base_dir=golden_dir)
        case = _make_golden_case()
        case_no_desc = case.model_copy(update={"description": ""})
        store.save(case_no_desc)

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "yagra",
                "golden",
                "list",
                "--golden-dir",
                str(golden_dir),
            ],
        )

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 0
        captured = capsys.readouterr()
        assert "test-wf/happy-path" in captured.out
        # No " - " description suffix
        lines = captured.out.strip().split("\n")
        first_line = lines[0].strip()
        assert first_line == "test-wf/happy-path"
