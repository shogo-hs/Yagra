"""Unit tests for GoldenTestRunner and GoldenCaseManager (G-20, M-50)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest

from yagra.application.use_cases.golden_case_manager import (
    GoldenCaseManager,
    _extract_final_state,
    _extract_initial_state,
)
from yagra.application.use_cases.golden_test_runner import (
    _build_summary,
    _compare_all_nodes,
    _resolve_strategy,
    build_golden_registry,
    compare_node,
    create_mock_llm_handler,
)
from yagra.domain.entities.comparison import ComparisonStrategy
from yagra.domain.entities.golden_case import (
    GoldenCase,
    NodeComparisonResult,
    NodeSnapshot,
)
from yagra.domain.entities.trace import (
    NodeStatus,
    NodeTrace,
    RunSummary,
    WorkflowRunTrace,
)
from yagra.ports.outbound.golden_case_repository import GoldenCaseRepositoryPort

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_node_trace(
    node_id: str,
    handler: str,
    input_snapshot: dict[str, Any] | None = None,
    output_snapshot: dict[str, Any] | None = None,
    status: NodeStatus = NodeStatus.SUCCESS,
) -> NodeTrace:
    """Creates a minimal NodeTrace for testing."""
    now = datetime.now(tz=UTC)
    return NodeTrace(
        node_id=node_id,
        handler=handler,
        status=status,
        started_at=now,
        ended_at=now,
        duration_ms=1.0,
        input_snapshot=input_snapshot or {},
        output_snapshot=output_snapshot or {},
    )


def _make_trace(
    nodes: list[NodeTrace],
    workflow_name: str = "test-workflow",
    status: NodeStatus = NodeStatus.SUCCESS,
) -> WorkflowRunTrace:
    """Creates a minimal WorkflowRunTrace for testing."""
    now = datetime.now(tz=UTC)
    return WorkflowRunTrace(
        workflow_name=workflow_name,
        workflow_version="1.0",
        workflow_path="/path/to/workflow.yaml",
        started_at=now,
        ended_at=now,
        status=status,
        nodes=nodes,
        summary=RunSummary(
            total_nodes_executed=len(nodes),
            succeeded_nodes=len([n for n in nodes if n.status == NodeStatus.SUCCESS]),
            failed_nodes=len([n for n in nodes if n.status == NodeStatus.ERROR]),
            total_duration_ms=1.0,
            node_order=[n.node_id for n in nodes],
        ),
    )


def _make_snapshot(
    node_id: str,
    handler: str = "custom",
    is_llm: bool = False,
    input_snap: dict[str, Any] | None = None,
    output_snap: dict[str, Any] | None = None,
    strategy: ComparisonStrategy = ComparisonStrategy.AUTO,
) -> NodeSnapshot:
    """Creates a minimal NodeSnapshot for testing."""
    return NodeSnapshot(
        node_id=node_id,
        handler=handler,
        is_llm_handler=is_llm,
        input_snapshot=input_snap or {},
        output_snapshot=output_snap or {},
        comparison_strategy=strategy,
    )


def _make_golden_case(
    case_name: str = "test-case",
    workflow_name: str = "test-workflow",
    execution_path: list[str] | None = None,
    node_snapshots: dict[str, NodeSnapshot] | None = None,
    initial_state: dict[str, Any] | None = None,
    final_state: dict[str, Any] | None = None,
) -> GoldenCase:
    """Creates a minimal GoldenCase for testing."""
    return GoldenCase(
        case_name=case_name,
        workflow_name=workflow_name,
        workflow_path="workflows/test.yaml",
        created_at=datetime.now(tz=UTC),
        source_run_id=str(uuid4()),
        initial_state=initial_state or {},
        final_state=final_state or {},
        execution_path=execution_path or [],
        node_snapshots=node_snapshots or {},
    )


class FakeRepository(GoldenCaseRepositoryPort):
    """In-memory fake repository for testing."""

    def __init__(self) -> None:
        """Initializes an empty in-memory store."""
        self._store: dict[tuple[str, str], GoldenCase] = {}

    def save(self, case: GoldenCase) -> str:
        self._store[(case.workflow_name, case.case_name)] = case
        return f"/fake/{case.workflow_name}/{case.case_name}.json"

    def load(self, workflow_name: str, case_name: str) -> GoldenCase:
        key = (workflow_name, case_name)
        if key not in self._store:
            msg = f"not found: {workflow_name}/{case_name}"
            raise FileNotFoundError(msg)
        return self._store[key]

    def list(self, workflow_name: str | None = None) -> list[GoldenCase]:
        cases = list(self._store.values())
        if workflow_name is not None:
            cases = [c for c in cases if c.workflow_name == workflow_name]
        return sorted(cases, key=lambda c: (c.workflow_name, c.case_name))

    def delete(self, workflow_name: str, case_name: str) -> bool:
        key = (workflow_name, case_name)
        if key in self._store:
            del self._store[key]
            return True
        return False

    def exists(self, workflow_name: str, case_name: str) -> bool:
        return (workflow_name, case_name) in self._store


# ===========================================================================
# GoldenCaseManager Tests
# ===========================================================================


class TestGoldenCaseManagerSaveFromTrace:
    """Tests for GoldenCaseManager.save_from_trace()."""

    def test_save_from_successful_trace(self) -> None:
        repo = FakeRepository()
        manager = GoldenCaseManager(repo)

        nodes = [
            _make_node_trace(
                "translate",
                "llm",
                input_snapshot={"text": "hello"},
                output_snapshot={"translated": "hola"},
            ),
            _make_node_trace(
                "format",
                "custom_formatter",
                input_snapshot={"translated": "hola"},
                output_snapshot={"formatted": "[hola]"},
            ),
        ]
        trace = _make_trace(nodes)

        result = manager.save_from_trace(trace, "happy-path")

        assert result.case_name == "happy-path"
        assert result.workflow_name == "test-workflow"
        assert len(result.execution_path) == 2
        assert result.execution_path == ["translate", "format"]
        assert "translate" in result.node_snapshots
        assert "format" in result.node_snapshots

        # LLM handler detection
        assert result.node_snapshots["translate"].is_llm_handler is True
        assert result.node_snapshots["format"].is_llm_handler is False

        # Persisted
        assert repo.exists("test-workflow", "happy-path")

    def test_save_extracts_initial_and_final_state(self) -> None:
        repo = FakeRepository()
        manager = GoldenCaseManager(repo)

        nodes = [
            _make_node_trace(
                "step1",
                "custom",
                input_snapshot={"input": "value1"},
                output_snapshot={"result1": "out1"},
            ),
            _make_node_trace(
                "step2",
                "custom",
                input_snapshot={"input": "value1", "result1": "out1"},
                output_snapshot={"result2": "out2"},
            ),
        ]
        trace = _make_trace(nodes)

        result = manager.save_from_trace(trace, "state-test")

        assert result.initial_state == {"input": "value1"}
        assert result.final_state == {
            "input": "value1",
            "result1": "out1",
            "result2": "out2",
        }

    def test_save_rejects_failed_trace(self) -> None:
        repo = FakeRepository()
        manager = GoldenCaseManager(repo)

        trace = _make_trace([], status=NodeStatus.ERROR)

        with pytest.raises(ValueError, match="Cannot create golden case"):
            manager.save_from_trace(trace, "should-fail")

    def test_save_rejects_invalid_case_name(self) -> None:
        repo = FakeRepository()
        manager = GoldenCaseManager(repo)

        trace = _make_trace([])

        with pytest.raises(ValueError, match="kebab-case"):
            manager.save_from_trace(trace, "Invalid Name")

        with pytest.raises(ValueError, match="kebab-case"):
            manager.save_from_trace(trace, "HAS_UNDERSCORE")

        with pytest.raises(ValueError, match="kebab-case"):
            manager.save_from_trace(trace, "")

    def test_save_accepts_valid_kebab_case_names(self) -> None:
        repo = FakeRepository()
        manager = GoldenCaseManager(repo)

        trace = _make_trace(
            [
                _make_node_trace("n1", "custom"),
            ]
        )

        for name in ["simple", "two-words", "a-b-c", "test123", "v2-path"]:
            result = manager.save_from_trace(trace, name)
            assert result.case_name == name

    def test_save_with_comparison_overrides(self) -> None:
        repo = FakeRepository()
        manager = GoldenCaseManager(repo)

        nodes = [
            _make_node_trace("translate", "llm"),
            _make_node_trace("format", "custom"),
        ]
        trace = _make_trace(nodes)

        overrides = {
            "translate": ComparisonStrategy.SKIP,
            "format": ComparisonStrategy.STRUCTURAL,
        }
        result = manager.save_from_trace(trace, "override-test", comparison_overrides=overrides)

        assert result.node_snapshots["translate"].comparison_strategy == ComparisonStrategy.SKIP
        assert result.node_snapshots["format"].comparison_strategy == ComparisonStrategy.STRUCTURAL

    def test_save_with_description(self) -> None:
        repo = FakeRepository()
        manager = GoldenCaseManager(repo)

        trace = _make_trace([_make_node_trace("n", "custom")])
        result = manager.save_from_trace(trace, "desc-test", description="My description")

        assert result.description == "My description"

    def test_save_skips_skipped_nodes(self) -> None:
        repo = FakeRepository()
        manager = GoldenCaseManager(repo)

        nodes = [
            _make_node_trace("executed", "custom"),
            _make_node_trace("skipped", "custom", status=NodeStatus.SKIPPED),
        ]
        trace = _make_trace(nodes)

        result = manager.save_from_trace(trace, "skip-test")

        assert result.execution_path == ["executed"]
        assert "executed" in result.node_snapshots
        assert "skipped" not in result.node_snapshots

    def test_save_detects_structured_llm_handler(self) -> None:
        repo = FakeRepository()
        manager = GoldenCaseManager(repo)

        nodes = [
            _make_node_trace("s1", "structured_llm"),
            _make_node_trace("s2", "streaming_llm"),
        ]
        trace = _make_trace(nodes)

        result = manager.save_from_trace(trace, "llm-types")

        assert result.node_snapshots["s1"].is_llm_handler is True
        assert result.node_snapshots["s2"].is_llm_handler is True


class TestGoldenCaseManagerListAndDelete:
    """Tests for GoldenCaseManager.list_cases() and delete_case()."""

    def test_list_cases_empty(self) -> None:
        repo = FakeRepository()
        manager = GoldenCaseManager(repo)
        assert manager.list_cases() == []

    def test_list_cases_returns_all(self) -> None:
        repo = FakeRepository()
        manager = GoldenCaseManager(repo)

        trace = _make_trace([_make_node_trace("n", "custom")])
        manager.save_from_trace(trace, "case-a")
        manager.save_from_trace(trace, "case-b")

        cases = manager.list_cases()
        assert len(cases) == 2

    def test_list_cases_filters_by_workflow(self) -> None:
        repo = FakeRepository()
        manager = GoldenCaseManager(repo)

        trace1 = _make_trace([_make_node_trace("n", "custom")], workflow_name="wf1")
        trace2 = _make_trace([_make_node_trace("n", "custom")], workflow_name="wf2")
        manager.save_from_trace(trace1, "case-a")
        manager.save_from_trace(trace2, "case-b")

        wf1_cases = manager.list_cases(workflow_name="wf1")
        assert len(wf1_cases) == 1
        assert wf1_cases[0].workflow_name == "wf1"

    def test_delete_existing_case(self) -> None:
        repo = FakeRepository()
        manager = GoldenCaseManager(repo)

        trace = _make_trace([_make_node_trace("n", "custom")])
        manager.save_from_trace(trace, "to-delete")

        assert manager.delete_case("test-workflow", "to-delete") is True
        assert manager.list_cases() == []

    def test_delete_nonexistent_case(self) -> None:
        repo = FakeRepository()
        manager = GoldenCaseManager(repo)

        assert manager.delete_case("wf", "nope") is False


# ===========================================================================
# Helper Function Tests
# ===========================================================================


class TestExtractState:
    """Tests for _extract_initial_state and _extract_final_state."""

    def test_initial_state_from_first_node(self) -> None:
        nodes = [
            _make_node_trace("n1", "h", input_snapshot={"a": 1}),
            _make_node_trace("n2", "h", input_snapshot={"a": 1, "b": 2}),
        ]
        trace = _make_trace(nodes)
        assert _extract_initial_state(trace) == {"a": 1}

    def test_initial_state_empty_when_no_nodes(self) -> None:
        trace = _make_trace([])
        assert _extract_initial_state(trace) == {}

    def test_final_state_merges_last_node(self) -> None:
        nodes = [
            _make_node_trace(
                "n1",
                "h",
                input_snapshot={"a": 1},
                output_snapshot={"b": 2},
            ),
            _make_node_trace(
                "n2",
                "h",
                input_snapshot={"a": 1, "b": 2},
                output_snapshot={"c": 3},
            ),
        ]
        trace = _make_trace(nodes)
        assert _extract_final_state(trace) == {"a": 1, "b": 2, "c": 3}

    def test_final_state_empty_when_no_nodes(self) -> None:
        trace = _make_trace([])
        assert _extract_final_state(trace) == {}


# ===========================================================================
# Mock Handler Tests
# ===========================================================================


class TestCreateMockLLMHandler:
    """Tests for create_mock_llm_handler()."""

    def test_returns_output_snapshot(self) -> None:
        snapshot = _make_snapshot(
            "translate",
            "llm",
            is_llm=True,
            output_snap={"translated": "hola"},
        )
        handler = create_mock_llm_handler(snapshot)

        result = handler({"text": "hello"}, {"model": "gpt-4"})
        assert result == {"translated": "hola"}

    def test_ignores_input_state(self) -> None:
        snapshot = _make_snapshot(
            "node",
            "llm",
            is_llm=True,
            output_snap={"out": "value"},
        )
        handler = create_mock_llm_handler(snapshot)

        result1 = handler({"x": 1}, {})
        result2 = handler({"y": 2}, {})
        assert result1 == result2 == {"out": "value"}

    def test_returns_independent_dict(self) -> None:
        snapshot = _make_snapshot(
            "node",
            "llm",
            is_llm=True,
            output_snap={"out": "value"},
        )
        handler = create_mock_llm_handler(snapshot)

        r1 = handler({}, {})
        r1["extra"] = "modified"
        r2 = handler({}, {})
        assert "extra" not in r2


# ===========================================================================
# Registry Building Tests
# ===========================================================================


class TestBuildGoldenRegistry:
    """Tests for build_golden_registry()."""

    def test_mocks_llm_handlers(self) -> None:
        from yagra.adapters.outbound import InMemoryNodeRegistry

        snap_llm = _make_snapshot(
            "translate",
            "llm",
            is_llm=True,
            output_snap={"translated": "hola"},
        )
        snap_custom = _make_snapshot(
            "format",
            "my_formatter",
            is_llm=False,
        )

        golden = _make_golden_case(
            node_snapshots={
                "translate": snap_llm,
                "format": snap_custom,
            },
        )

        def real_formatter(state: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
            return {"formatted": state.get("translated", "")}

        base_registry = InMemoryNodeRegistry({"my_formatter": real_formatter})

        result_registry = build_golden_registry(golden, base_registry)

        # LLM handler should be mocked (per-node dispatch via resolve_for_node)
        mock_handler = result_registry.resolve_for_node("llm", "translate")
        assert mock_handler({}, {}) == {"translated": "hola"}

        # Non-LLM handler should be the real one
        real_handler = result_registry.resolve("my_formatter")
        assert real_handler({"translated": "test"}, {}) == {"formatted": "test"}

    def test_per_node_dispatch_for_same_handler(self) -> None:
        from yagra.adapters.outbound import InMemoryNodeRegistry

        snap1 = _make_snapshot("n1", "llm", is_llm=True, output_snap={"a": 1})
        snap2 = _make_snapshot("n2", "llm", is_llm=True, output_snap={"b": 2})

        golden = _make_golden_case(
            node_snapshots={"n1": snap1, "n2": snap2},
        )

        base_registry = InMemoryNodeRegistry()
        result = build_golden_registry(golden, base_registry)

        # Each node gets its own mock handler via resolve_for_node
        handler_n1 = result.resolve_for_node("llm", "n1")
        handler_n2 = result.resolve_for_node("llm", "n2")
        assert handler_n1({}, {}) == {"a": 1}
        assert handler_n2({}, {}) == {"b": 2}


# ===========================================================================
# Node Comparison Tests
# ===========================================================================


class TestCompareNode:
    """Tests for compare_node()."""

    def test_exact_match_passes(self) -> None:
        snapshot = _make_snapshot(
            "format",
            "custom",
            input_snap={"x": 1},
            output_snap={"y": 2},
        )
        result = compare_node(snapshot, {"x": 1}, {"y": 2})

        assert result.status == "pass"
        assert result.input_match is True
        assert result.output_match is True
        assert result.input_diff is None
        assert result.output_diff is None

    def test_input_mismatch_fails(self) -> None:
        snapshot = _make_snapshot(
            "format",
            "custom",
            input_snap={"x": 1},
            output_snap={"y": 2},
        )
        result = compare_node(snapshot, {"x": 999}, {"y": 2})

        assert result.status == "fail"
        assert result.input_match is False
        assert result.output_match is True
        assert result.input_diff is not None

    def test_output_mismatch_fails(self) -> None:
        snapshot = _make_snapshot(
            "format",
            "custom",
            input_snap={"x": 1},
            output_snap={"y": 2},
        )
        result = compare_node(snapshot, {"x": 1}, {"y": 999})

        assert result.status == "fail"
        assert result.input_match is True
        assert result.output_match is False
        assert result.output_diff is not None

    def test_skip_strategy(self) -> None:
        snapshot = _make_snapshot(
            "node",
            "custom",
            input_snap={"x": 1},
            output_snap={"y": 2},
            strategy=ComparisonStrategy.SKIP,
        )
        result = compare_node(snapshot, {"x": 999}, {"y": 999})

        assert result.status == "skip"
        assert result.input_match is None
        assert result.output_match is None

    def test_llm_node_skips_output_comparison(self) -> None:
        snapshot = _make_snapshot(
            "translate",
            "llm",
            is_llm=True,
            input_snap={"text": "hello"},
            output_snap={"translated": "hola"},
        )
        # Even with different output, LLM nodes pass on output
        result = compare_node(snapshot, {"text": "hello"}, {"translated": "different"})

        assert result.output_match is True
        assert result.output_diff is None
        assert result.status == "pass"

    def test_llm_node_input_uses_structural(self) -> None:
        snapshot = _make_snapshot(
            "translate",
            "llm",
            is_llm=True,
            input_snap={"text": "hello"},
            output_snap={"translated": "hola"},
        )
        # Same key, same type, different value -> structural match
        result = compare_node(snapshot, {"text": "different"}, {"translated": "x"})

        assert result.input_match is True
        assert result.status == "pass"

    def test_llm_node_input_structural_type_mismatch(self) -> None:
        snapshot = _make_snapshot(
            "translate",
            "llm",
            is_llm=True,
            input_snap={"text": "hello"},
        )
        # Different type -> structural mismatch
        result = compare_node(snapshot, {"text": 42}, {})

        assert result.input_match is False
        assert result.status == "fail"

    def test_message_on_pass(self) -> None:
        snapshot = _make_snapshot("node", "custom")
        result = compare_node(snapshot, {}, {})
        assert "passed" in result.message

    def test_message_on_fail(self) -> None:
        snapshot = _make_snapshot(
            "node",
            "custom",
            input_snap={"x": 1},
        )
        result = compare_node(snapshot, {"x": 999}, {})
        assert "failed" in result.message
        assert "input" in result.message


# ===========================================================================
# Compare All Nodes Tests
# ===========================================================================


class TestCompareAllNodes:
    """Tests for _compare_all_nodes()."""

    def test_all_matching(self) -> None:
        snap_a = _make_snapshot("a", "custom", input_snap={"x": 1}, output_snap={"y": 2})
        snap_b = _make_snapshot("b", "custom", input_snap={"y": 2}, output_snap={"z": 3})

        golden = _make_golden_case(
            execution_path=["a", "b"],
            node_snapshots={"a": snap_a, "b": snap_b},
        )

        results = _compare_all_nodes(
            golden,
            actual_path=["a", "b"],
            actual_snapshots={
                "a": ({"x": 1}, {"y": 2}),
                "b": ({"y": 2}, {"z": 3}),
            },
        )

        assert len(results) == 2
        assert all(r.status == "pass" for r in results)

    def test_missing_node(self) -> None:
        snap_a = _make_snapshot("a", "custom")
        snap_b = _make_snapshot("b", "custom")

        golden = _make_golden_case(
            execution_path=["a", "b"],
            node_snapshots={"a": snap_a, "b": snap_b},
        )

        results = _compare_all_nodes(
            golden,
            actual_path=["a"],
            actual_snapshots={"a": ({}, {})},
        )

        assert len(results) == 2
        assert results[0].status == "pass"
        assert results[1].status == "missing"
        assert "not executed" in results[1].message

    def test_unexpected_node(self) -> None:
        snap_a = _make_snapshot("a", "custom")

        golden = _make_golden_case(
            execution_path=["a"],
            node_snapshots={"a": snap_a},
        )

        results = _compare_all_nodes(
            golden,
            actual_path=["a", "extra"],
            actual_snapshots={
                "a": ({}, {}),
                "extra": ({"x": 1}, {"y": 2}),
            },
        )

        assert len(results) == 2
        assert results[0].status == "pass"
        assert results[1].status == "unexpected"
        assert results[1].node_id == "extra"

    def test_mixed_results(self) -> None:
        snap_a = _make_snapshot("a", "custom", input_snap={"x": 1})
        snap_b = _make_snapshot("b", "custom")

        golden = _make_golden_case(
            execution_path=["a", "b"],
            node_snapshots={"a": snap_a, "b": snap_b},
        )

        results = _compare_all_nodes(
            golden,
            actual_path=["a"],
            actual_snapshots={"a": ({"x": 999}, {})},
        )

        assert results[0].status == "fail"  # a: input mismatch
        assert results[1].status == "missing"  # b: missing


# ===========================================================================
# Strategy Resolution Tests
# ===========================================================================


class TestResolveStrategy:
    """Tests for _resolve_strategy()."""

    def test_exact_stays_exact(self) -> None:
        assert _resolve_strategy(ComparisonStrategy.EXACT, False) == ComparisonStrategy.EXACT

    def test_structural_stays_structural(self) -> None:
        assert (
            _resolve_strategy(ComparisonStrategy.STRUCTURAL, True) == ComparisonStrategy.STRUCTURAL
        )

    def test_auto_resolves_to_exact_for_non_llm(self) -> None:
        assert _resolve_strategy(ComparisonStrategy.AUTO, False) == ComparisonStrategy.EXACT

    def test_auto_resolves_to_structural_for_llm(self) -> None:
        assert _resolve_strategy(ComparisonStrategy.AUTO, True) == ComparisonStrategy.STRUCTURAL

    def test_skip_stays_skip(self) -> None:
        assert _resolve_strategy(ComparisonStrategy.SKIP, False) == ComparisonStrategy.SKIP


# ===========================================================================
# Summary Building Tests
# ===========================================================================


class TestBuildSummary:
    """Tests for _build_summary()."""

    def test_passed_summary(self) -> None:
        results = [
            NodeComparisonResult(
                node_id="a",
                status="pass",
                strategy_used=ComparisonStrategy.EXACT,
            ),
        ]
        summary = _build_summary("test", True, True, results)
        assert "PASSED" in summary
        assert "1 passed" in summary

    def test_failed_summary(self) -> None:
        results = [
            NodeComparisonResult(
                node_id="a",
                status="fail",
                strategy_used=ComparisonStrategy.EXACT,
            ),
        ]
        summary = _build_summary("test", False, True, results)
        assert "FAILED" in summary
        assert "1 failed" in summary

    def test_path_mismatch_noted(self) -> None:
        summary = _build_summary("test", False, False, [])
        assert "path mismatch" in summary.lower()

    def test_all_statuses_counted(self) -> None:
        results = [
            NodeComparisonResult(
                node_id="a", status="pass", strategy_used=ComparisonStrategy.EXACT
            ),
            NodeComparisonResult(
                node_id="b", status="fail", strategy_used=ComparisonStrategy.EXACT
            ),
            NodeComparisonResult(node_id="c", status="skip", strategy_used=ComparisonStrategy.SKIP),
            NodeComparisonResult(
                node_id="d", status="missing", strategy_used=ComparisonStrategy.EXACT
            ),
            NodeComparisonResult(
                node_id="e",
                status="unexpected",
                strategy_used=ComparisonStrategy.EXACT,
            ),
        ]
        summary = _build_summary("test", False, True, results)
        assert "5 total" in summary
        assert "1 passed" in summary
        assert "1 failed" in summary
        assert "1 skipped" in summary
        assert "1 missing" in summary
        assert "1 unexpected" in summary
