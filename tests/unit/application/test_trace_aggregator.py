"""Unit tests for trace_aggregator (M-42)."""

from __future__ import annotations

import json
from typing import Any

import pytest

from yagra.application.use_cases.trace_aggregator import (
    aggregate_traces,
    load_traces,
)


def _make_node_trace(
    node_id: str = "node_a",
    handler: str = "llm",
    status: str = "success",
    duration_ms: float = 100.0,
    llm_call: dict[str, Any] | None = None,
    error: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a minimal node trace dict for testing."""
    node: dict[str, Any] = {
        "node_id": node_id,
        "handler": handler,
        "status": status,
        "started_at": "2026-01-15T10:00:00Z",
        "ended_at": "2026-01-15T10:00:00.100000Z",
        "duration_ms": duration_ms,
        "input_snapshot": {},
        "output_snapshot": {},
        "llm_call": llm_call,
        "error": error,
    }
    return node


def _make_trace(
    workflow_name: str = "test_workflow",
    status: str = "success",
    started_at: str = "2026-01-15T10:00:00Z",
    ended_at: str = "2026-01-15T10:00:01Z",
    total_duration_ms: float = 1000.0,
    nodes: list[dict[str, Any]] | None = None,
    total_prompt_tokens: int = 0,
    total_completion_tokens: int = 0,
    total_tokens: int = 0,
    total_estimated_cost_usd: float | None = None,
) -> dict[str, Any]:
    """Create a minimal workflow run trace dict for testing."""
    if nodes is None:
        nodes = [_make_node_trace()]
    return {
        "schema_version": "1.0",
        "run_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "workflow_name": workflow_name,
        "workflow_version": "1.0",
        "workflow_path": None,
        "started_at": started_at,
        "ended_at": ended_at,
        "status": status,
        "nodes": nodes,
        "summary": {
            "total_nodes_executed": len(nodes),
            "succeeded_nodes": sum(1 for n in nodes if n["status"] == "success"),
            "failed_nodes": sum(1 for n in nodes if n["status"] == "error"),
            "total_duration_ms": total_duration_ms,
            "total_prompt_tokens": total_prompt_tokens,
            "total_completion_tokens": total_completion_tokens,
            "total_tokens": total_tokens,
            "total_estimated_cost_usd": total_estimated_cost_usd,
            "node_order": [n["node_id"] for n in nodes],
        },
        "metadata": {
            "yagra_version": "0.6.11",
            "python_version": "3.12.0",
            "platform": "Darwin",
        },
    }


def _write_trace_file(
    tmp_path: Any,
    trace: dict[str, Any],
    workflow_name: str | None = None,
    filename: str = "trace_001.json",
) -> None:
    """Write a trace dict as a JSON file in the expected directory structure."""
    wf_name = workflow_name or trace.get("workflow_name", "test_workflow")
    workflow_dir = tmp_path / wf_name
    workflow_dir.mkdir(parents=True, exist_ok=True)
    (workflow_dir / filename).write_text(
        json.dumps(trace, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


class TestLoadTraces:
    def test_load_traces_empty_dir(self, tmp_path: Any) -> None:
        result = load_traces(tmp_path)
        assert result == []

    def test_load_traces_nonexistent_dir(self, tmp_path: Any) -> None:
        result = load_traces(tmp_path / "does_not_exist")
        assert result == []

    def test_load_traces_single_file(self, tmp_path: Any) -> None:
        trace = _make_trace()
        _write_trace_file(tmp_path, trace)

        result = load_traces(tmp_path)
        assert len(result) == 1
        assert result[0]["workflow_name"] == "test_workflow"

    def test_load_traces_multiple_sorted(self, tmp_path: Any) -> None:
        trace_old = _make_trace(
            started_at="2026-01-10T08:00:00Z",
            ended_at="2026-01-10T08:00:01Z",
        )
        trace_new = _make_trace(
            started_at="2026-01-15T10:00:00Z",
            ended_at="2026-01-15T10:00:01Z",
        )
        _write_trace_file(tmp_path, trace_old, filename="trace_old.json")
        _write_trace_file(tmp_path, trace_new, filename="trace_new.json")

        result = load_traces(tmp_path)
        assert len(result) == 2
        # Most recent first
        assert result[0]["started_at"] == "2026-01-15T10:00:00Z"
        assert result[1]["started_at"] == "2026-01-10T08:00:00Z"

    def test_load_traces_with_limit(self, tmp_path: Any) -> None:
        for i in range(5):
            trace = _make_trace(
                started_at=f"2026-01-{10 + i:02d}T10:00:00Z",
                ended_at=f"2026-01-{10 + i:02d}T10:00:01Z",
            )
            _write_trace_file(tmp_path, trace, filename=f"trace_{i:03d}.json")

        result = load_traces(tmp_path, limit=3)
        assert len(result) == 3
        # Should be the 3 most recent
        assert result[0]["started_at"] == "2026-01-14T10:00:00Z"

    def test_load_traces_with_workflow_name(self, tmp_path: Any) -> None:
        trace_a = _make_trace(workflow_name="workflow_a")
        trace_b = _make_trace(workflow_name="workflow_b")
        _write_trace_file(tmp_path, trace_a, workflow_name="workflow_a")
        _write_trace_file(tmp_path, trace_b, workflow_name="workflow_b")

        result = load_traces(tmp_path, workflow_name="workflow_a")
        assert len(result) == 1
        assert result[0]["workflow_name"] == "workflow_a"

    def test_load_traces_skips_malformed_json(self, tmp_path: Any) -> None:
        workflow_dir = tmp_path / "test_workflow"
        workflow_dir.mkdir(parents=True, exist_ok=True)
        (workflow_dir / "bad.json").write_text("not valid json {{{", encoding="utf-8")

        trace = _make_trace()
        _write_trace_file(tmp_path, trace, filename="good.json")

        result = load_traces(tmp_path)
        assert len(result) == 1


class TestAggregateTraces:
    def test_aggregate_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            aggregate_traces([])

    def test_aggregate_single_trace(self) -> None:
        trace = _make_trace(
            total_duration_ms=500.0,
            nodes=[_make_node_trace(duration_ms=500.0)],
        )
        summary = aggregate_traces([trace])

        assert summary.workflow_name == "test_workflow"
        assert summary.total_runs == 1
        assert summary.successful_runs == 1
        assert summary.failed_runs == 0
        assert summary.run_success_rate == pytest.approx(1.0)
        assert summary.avg_total_duration_ms == pytest.approx(500.0)
        assert summary.min_total_duration_ms == pytest.approx(500.0)
        assert summary.max_total_duration_ms == pytest.approx(500.0)
        assert len(summary.node_stats) == 1

    def test_aggregate_multiple_traces(self) -> None:
        traces = [
            _make_trace(
                started_at="2026-01-10T10:00:00Z",
                ended_at="2026-01-10T10:00:01Z",
                total_duration_ms=800.0,
                nodes=[_make_node_trace(node_id="step1", duration_ms=800.0)],
            ),
            _make_trace(
                started_at="2026-01-11T10:00:00Z",
                ended_at="2026-01-11T10:00:01Z",
                total_duration_ms=1200.0,
                nodes=[_make_node_trace(node_id="step1", duration_ms=1200.0)],
            ),
        ]
        summary = aggregate_traces(traces)

        assert summary.total_runs == 2
        assert summary.avg_total_duration_ms == pytest.approx(1000.0)
        assert summary.min_total_duration_ms == pytest.approx(800.0)
        assert summary.max_total_duration_ms == pytest.approx(1200.0)

        assert len(summary.node_stats) == 1
        ns = summary.node_stats[0]
        assert ns.node_id == "step1"
        assert ns.execution_count == 2
        assert ns.avg_duration_ms == pytest.approx(1000.0)

    def test_aggregate_with_errors(self) -> None:
        error_node = _make_node_trace(
            node_id="fail_node",
            status="error",
            duration_ms=50.0,
            error={
                "error_type": "ValueError",
                "error_message": "something went wrong",
                "traceback": None,
            },
        )
        traces = [
            _make_trace(
                status="error",
                nodes=[
                    _make_node_trace(node_id="ok_node", duration_ms=100.0),
                    error_node,
                ],
            ),
            _make_trace(
                status="success",
                nodes=[
                    _make_node_trace(node_id="ok_node", duration_ms=120.0),
                    _make_node_trace(node_id="fail_node", duration_ms=80.0),
                ],
            ),
        ]
        summary = aggregate_traces(traces)

        assert summary.total_runs == 2
        assert summary.successful_runs == 1
        assert summary.failed_runs == 1
        assert summary.run_success_rate == pytest.approx(0.5)

        # Check fail_node stats
        fail_stats = next(ns for ns in summary.node_stats if ns.node_id == "fail_node")
        assert fail_stats.execution_count == 2
        assert fail_stats.error_count == 1
        assert fail_stats.success_count == 1
        assert fail_stats.error_types == {"ValueError": 1}

    def test_aggregate_with_llm_calls(self) -> None:
        llm_call = {
            "model": "openai/gpt-4o-mini",
            "provider": "openai",
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
            "estimated_cost_usd": 0.001,
        }
        traces = [
            _make_trace(
                total_prompt_tokens=100,
                total_completion_tokens=50,
                total_tokens=150,
                total_estimated_cost_usd=0.001,
                nodes=[_make_node_trace(node_id="llm_node", llm_call=llm_call)],
            ),
            _make_trace(
                total_prompt_tokens=200,
                total_completion_tokens=100,
                total_tokens=300,
                total_estimated_cost_usd=0.002,
                nodes=[
                    _make_node_trace(
                        node_id="llm_node",
                        llm_call={
                            **llm_call,
                            "prompt_tokens": 200,
                            "completion_tokens": 100,
                            "total_tokens": 300,
                            "estimated_cost_usd": 0.002,
                        },
                    )
                ],
            ),
        ]
        summary = aggregate_traces(traces)

        assert summary.total_prompt_tokens == 300
        assert summary.total_completion_tokens == 150
        assert summary.total_tokens == 450
        assert summary.total_estimated_cost_usd == pytest.approx(0.003)

        ns = summary.node_stats[0]
        assert ns.total_prompt_tokens == 300
        assert ns.total_completion_tokens == 150
        assert ns.total_tokens == 450
        assert ns.avg_tokens_per_call == pytest.approx(225.0)
        assert ns.total_estimated_cost_usd == pytest.approx(0.003)

    def test_aggregate_no_llm_calls(self) -> None:
        traces = [
            _make_trace(
                nodes=[_make_node_trace(node_id="custom_node", handler="custom")],
            ),
        ]
        summary = aggregate_traces(traces)

        ns = summary.node_stats[0]
        assert ns.total_prompt_tokens == 0
        assert ns.total_completion_tokens == 0
        assert ns.total_tokens == 0
        assert ns.avg_tokens_per_call == pytest.approx(0.0)
        assert ns.total_estimated_cost_usd is None

    def test_aggregate_mixed_nodes(self) -> None:
        """Nodes that don't appear in every run are handled correctly."""
        traces = [
            _make_trace(
                nodes=[
                    _make_node_trace(node_id="always_node", duration_ms=100.0),
                    _make_node_trace(node_id="sometimes_node", duration_ms=200.0),
                ],
            ),
            _make_trace(
                nodes=[
                    _make_node_trace(node_id="always_node", duration_ms=150.0),
                ],
            ),
        ]
        summary = aggregate_traces(traces)

        assert len(summary.node_stats) == 2
        always_stats = next(ns for ns in summary.node_stats if ns.node_id == "always_node")
        sometimes_stats = next(ns for ns in summary.node_stats if ns.node_id == "sometimes_node")

        assert always_stats.execution_count == 2
        assert sometimes_stats.execution_count == 1


class TestSummaryToDict:
    def test_summary_to_dict(self) -> None:
        trace = _make_trace()
        summary = aggregate_traces([trace])
        result = summary.to_dict()

        assert isinstance(result, dict)
        assert result["workflow_name"] == "test_workflow"
        assert result["total_runs"] == 1
        assert result["schema_version"] == "1.0"
        assert isinstance(result["node_stats"], list)

        # Verify JSON serializable
        json_str = json.dumps(result, ensure_ascii=False)
        assert isinstance(json_str, str)

    def test_summary_to_dict_with_none_cost(self) -> None:
        trace = _make_trace(total_estimated_cost_usd=None)
        summary = aggregate_traces([trace])
        result = summary.to_dict()

        assert result["total_estimated_cost_usd"] is None


class TestNodeStatsPercentiles:
    def test_node_stats_percentiles(self) -> None:
        """Verify p50 and p95 calculations with multiple data points."""
        durations = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
        nodes = [_make_node_trace(node_id="perf_node", duration_ms=d) for d in durations]
        traces = [_make_trace(nodes=[node]) for node in nodes]
        summary = aggregate_traces(traces)

        ns = summary.node_stats[0]
        assert ns.execution_count == 10

        # p50 (median) of [10..100] is 55.0
        assert ns.p50_duration_ms == pytest.approx(55.0)

        # statistics.quantiles(n=20, method='exclusive') returns 104.5 for this dataset
        assert ns.p95_duration_ms == pytest.approx(104.5)

    def test_node_stats_single_value(self) -> None:
        """p50 and p95 with a single data point returns that value."""
        trace = _make_trace(
            nodes=[_make_node_trace(node_id="single", duration_ms=42.0)],
        )
        summary = aggregate_traces([trace])
        ns = summary.node_stats[0]

        assert ns.p50_duration_ms == pytest.approx(42.0)
        assert ns.p95_duration_ms == pytest.approx(42.0)

    def test_node_stats_two_values(self) -> None:
        """p50 and p95 with two data points."""
        traces = [
            _make_trace(nodes=[_make_node_trace(node_id="dual", duration_ms=10.0)]),
            _make_trace(nodes=[_make_node_trace(node_id="dual", duration_ms=90.0)]),
        ]
        summary = aggregate_traces(traces)
        ns = summary.node_stats[0]

        assert ns.p50_duration_ms == pytest.approx(50.0)
        # statistics.quantiles(n=20, method='exclusive') returns 158.0 for [10, 90]
        assert ns.p95_duration_ms == pytest.approx(158.0)
