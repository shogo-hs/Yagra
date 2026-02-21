"""End-to-end integration tests for golden test framework (G-20, M-50).

Tests the full workflow: trace capture → golden case save → YAML modification
→ golden test execution → result verification.

Uses simple deterministic handlers (no real LLM calls) to validate the
replay-compare cycle without external dependencies.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from yagra import Yagra
from yagra.adapters.outbound import InMemoryNodeRegistry, LocalGoldenCaseStore
from yagra.application.use_cases.golden_case_manager import GoldenCaseManager
from yagra.application.use_cases.golden_test_runner import GoldenTestRunner

# ---------------------------------------------------------------------------
# Test Handlers (deterministic, no LLM calls)
# ---------------------------------------------------------------------------


def _llm_handler(state: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    """Simulates an LLM handler that 'translates' by uppercasing."""
    text = state.get("input_text", "")
    output_key = params.get("output_key", "output")
    return {output_key: text.upper()}


def _formatter_handler(state: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    """Formats the translated text with brackets."""
    translated = state.get("translated", "")
    prefix = params.get("prefix", "Result")
    return {"formatted": f"[{prefix}] {translated}"}


def _validator_handler(state: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    """Validates the formatted text is non-empty."""
    _ = params
    formatted = state.get("formatted", "")
    return {"is_valid": len(formatted) > 0}


# ---------------------------------------------------------------------------
# Workflow YAML helpers
# ---------------------------------------------------------------------------


def _write_workflow(path: Path, payload: dict[str, Any]) -> Path:
    """Writes a workflow YAML file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return path


def _two_node_workflow() -> dict[str, Any]:
    """Workflow: llm → formatter."""
    return {
        "version": "1.0",
        "start_at": "translate",
        "end_at": ["format"],
        "nodes": [
            {
                "id": "translate",
                "handler": "llm",
                "params": {
                    "output_key": "translated",
                },
            },
            {
                "id": "format",
                "handler": "formatter",
                "params": {
                    "prefix": "Result",
                },
            },
        ],
        "edges": [
            {"source": "translate", "target": "format"},
        ],
        "params": {},
    }


def _three_node_workflow() -> dict[str, Any]:
    """Workflow: llm → formatter → validator."""
    return {
        "version": "1.0",
        "start_at": "translate",
        "end_at": ["validate"],
        "nodes": [
            {
                "id": "translate",
                "handler": "llm",
                "params": {
                    "output_key": "translated",
                },
            },
            {
                "id": "format",
                "handler": "formatter",
                "params": {
                    "prefix": "Result",
                },
            },
            {
                "id": "validate",
                "handler": "validator",
                "params": {},
            },
        ],
        "edges": [
            {"source": "translate", "target": "format"},
            {"source": "format", "target": "validate"},
        ],
        "params": {},
    }


def _build_registry() -> InMemoryNodeRegistry:
    """Creates a registry with test handlers."""
    return InMemoryNodeRegistry(
        {
            "llm": _llm_handler,
            "formatter": _formatter_handler,
            "validator": _validator_handler,
        }
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGoldenTestE2EPassingCase:
    """E2E: unchanged workflow should produce passing golden tests."""

    def test_unchanged_workflow_passes(self, tmp_path: Path) -> None:
        """Save golden case from trace, run golden test without YAML changes.

        Expected: all nodes pass, execution path matches.
        """
        workflow_path = _write_workflow(
            tmp_path / "workflow.yaml",
            _two_node_workflow(),
        )
        registry = _build_registry()

        # Step 1: Execute workflow with tracing to capture trace
        yagra = Yagra.from_workflow(
            workflow_path=workflow_path,
            registry=registry,
            observability=True,
        )
        result = yagra.invoke({"input_text": "hello world"}, trace=False)
        assert result["formatted"] == "[Result] HELLO WORLD"

        # Capture trace from the collector
        from datetime import UTC, datetime

        trace = yagra._trace_collector.build_trace(  # noqa: SLF001
            started_at=datetime.now(tz=UTC),
            ended_at=datetime.now(tz=UTC),
            total_duration_ms=1.0,
        )

        # Step 2: Save golden case
        golden_dir = tmp_path / ".yagra" / "golden"
        store = LocalGoldenCaseStore(base_dir=golden_dir)
        manager = GoldenCaseManager(store)
        golden = manager.save_from_trace(trace, "happy-path", description="Basic flow")

        assert golden.execution_path == ["translate", "format"]
        assert golden.node_snapshots["translate"].is_llm_handler is True
        assert golden.node_snapshots["format"].is_llm_handler is False

        # Step 3: Run golden test (unchanged workflow)
        runner = GoldenTestRunner(store)
        test_result = runner.run(
            golden_case=golden,
            workflow_path=workflow_path,
            registry=registry,
        )

        assert test_result.passed is True
        assert test_result.execution_path_match is True
        assert test_result.expected_path == ["translate", "format"]
        assert test_result.actual_path == ["translate", "format"]
        assert all(r.status in ("pass", "skip") for r in test_result.node_results)

    def test_run_all_with_multiple_cases(self, tmp_path: Path) -> None:
        """Tests run_all with multiple golden cases for the same workflow."""
        workflow_path = _write_workflow(
            tmp_path / "workflow.yaml",
            _two_node_workflow(),
        )
        registry = _build_registry()

        golden_dir = tmp_path / ".yagra" / "golden"
        store = LocalGoldenCaseStore(base_dir=golden_dir)
        manager = GoldenCaseManager(store)

        # Create two golden cases from different inputs
        for case_name, input_text in [("case-a", "foo"), ("case-b", "bar")]:
            yagra = Yagra.from_workflow(
                workflow_path=workflow_path,
                registry=registry,
                observability=True,
            )
            yagra.invoke({"input_text": input_text}, trace=False)

            from datetime import UTC, datetime

            trace = yagra._trace_collector.build_trace(  # noqa: SLF001
                started_at=datetime.now(tz=UTC),
                ended_at=datetime.now(tz=UTC),
                total_duration_ms=1.0,
            )
            manager.save_from_trace(trace, case_name)

        # Run all golden tests
        runner = GoldenTestRunner(store)
        results = runner.run_all(
            workflow_name=workflow_path.stem,
            workflow_path=workflow_path,
            registry=registry,
        )

        assert len(results) == 2
        assert all(r.passed for r in results)


class TestGoldenTestE2EFailingCase:
    """E2E: modified workflow should detect regressions."""

    def test_node_output_change_detected(self, tmp_path: Path) -> None:
        """Change non-LLM node params → output_snapshot mismatch → FAIL."""
        workflow_path = _write_workflow(
            tmp_path / "workflow.yaml",
            _two_node_workflow(),
        )
        registry = _build_registry()

        # Capture golden case
        yagra = Yagra.from_workflow(
            workflow_path=workflow_path,
            registry=registry,
            observability=True,
        )
        yagra.invoke({"input_text": "hello"}, trace=False)

        from datetime import UTC, datetime

        trace = yagra._trace_collector.build_trace(  # noqa: SLF001
            started_at=datetime.now(tz=UTC),
            ended_at=datetime.now(tz=UTC),
            total_duration_ms=1.0,
        )

        golden_dir = tmp_path / ".yagra" / "golden"
        store = LocalGoldenCaseStore(base_dir=golden_dir)
        manager = GoldenCaseManager(store)
        golden = manager.save_from_trace(trace, "before-change")

        # Modify the workflow: change formatter prefix
        modified = _two_node_workflow()
        modified["nodes"][1]["params"]["prefix"] = "Changed"
        _write_workflow(workflow_path, modified)

        # Run golden test → should fail on format node's output
        runner = GoldenTestRunner(store)
        test_result = runner.run(
            golden_case=golden,
            workflow_path=workflow_path,
            registry=registry,
        )

        assert test_result.passed is False
        # Execution path still matches (same nodes executed)
        assert test_result.execution_path_match is True

        # Find the format node result
        format_result = next(r for r in test_result.node_results if r.node_id == "format")
        assert format_result.status == "fail"
        assert format_result.output_match is False

    def test_execution_path_change_detected(self, tmp_path: Path) -> None:
        """Add a new node to workflow → execution path mismatch → FAIL."""
        workflow_path = _write_workflow(
            tmp_path / "workflow.yaml",
            _two_node_workflow(),
        )
        registry = _build_registry()

        # Capture golden case with 2-node workflow
        yagra = Yagra.from_workflow(
            workflow_path=workflow_path,
            registry=registry,
            observability=True,
        )
        yagra.invoke({"input_text": "test"}, trace=False)

        from datetime import UTC, datetime

        trace = yagra._trace_collector.build_trace(  # noqa: SLF001
            started_at=datetime.now(tz=UTC),
            ended_at=datetime.now(tz=UTC),
            total_duration_ms=1.0,
        )

        golden_dir = tmp_path / ".yagra" / "golden"
        store = LocalGoldenCaseStore(base_dir=golden_dir)
        manager = GoldenCaseManager(store)
        golden = manager.save_from_trace(trace, "two-node-path")

        # Modify workflow: add a validator node (3-node workflow)
        _write_workflow(workflow_path, _three_node_workflow())

        runner = GoldenTestRunner(store)
        test_result = runner.run(
            golden_case=golden,
            workflow_path=workflow_path,
            registry=registry,
        )

        assert test_result.passed is False
        assert test_result.execution_path_match is False
        assert "validate" in test_result.actual_path
        assert "validate" not in test_result.expected_path

        # Verify the unexpected node is reported
        unexpected = [r for r in test_result.node_results if r.status == "unexpected"]
        assert len(unexpected) == 1
        assert unexpected[0].node_id == "validate"


class TestGoldenTestE2EResultFormat:
    """E2E: verify GoldenTestResult JSON serialization."""

    def test_result_serializes_to_json(self, tmp_path: Path) -> None:
        """GoldenTestResult should be JSON-serializable for MCP output."""
        workflow_path = _write_workflow(
            tmp_path / "workflow.yaml",
            _two_node_workflow(),
        )
        registry = _build_registry()

        yagra = Yagra.from_workflow(
            workflow_path=workflow_path,
            registry=registry,
            observability=True,
        )
        yagra.invoke({"input_text": "hello"}, trace=False)

        from datetime import UTC, datetime

        trace = yagra._trace_collector.build_trace(  # noqa: SLF001
            started_at=datetime.now(tz=UTC),
            ended_at=datetime.now(tz=UTC),
            total_duration_ms=1.0,
        )

        golden_dir = tmp_path / ".yagra" / "golden"
        store = LocalGoldenCaseStore(base_dir=golden_dir)
        manager = GoldenCaseManager(store)
        golden = manager.save_from_trace(trace, "json-test")

        runner = GoldenTestRunner(store)
        result = runner.run(
            golden_case=golden,
            workflow_path=workflow_path,
            registry=registry,
        )

        # Verify JSON serialization works
        result_dict = result.model_dump(mode="json")
        assert isinstance(result_dict, dict)
        assert "case_name" in result_dict
        assert "passed" in result_dict
        assert "node_results" in result_dict
        assert "summary" in result_dict

        import json

        json_str = json.dumps(result_dict)
        assert json.loads(json_str) == result_dict
