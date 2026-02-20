"""Unit tests for TraceCollector (G-14, G-15)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from yagra.application.use_cases.trace_collector import (
    TraceCollector,
    TraceContext,
    _safe_snapshot,
)
from yagra.domain.entities.trace import NodeStatus


class TestSafeSnapshot:
    def test_primitives_pass_through(self) -> None:
        assert _safe_snapshot("hello") == "hello"
        assert _safe_snapshot(42) == 42
        assert _safe_snapshot(3.14) == pytest.approx(3.14)
        assert _safe_snapshot(True) is True
        assert _safe_snapshot(None) is None

    def test_dict_is_recursed(self) -> None:
        result = _safe_snapshot({"a": 1, "b": "two"})
        assert result == {"a": 1, "b": "two"}

    def test_list_is_recursed(self) -> None:
        result = _safe_snapshot([1, "two", None])
        assert result == [1, "two", None]

    def test_non_serializable_returns_repr(self) -> None:
        class Custom:
            def __repr__(self) -> str:
                return "<Custom instance>"

        result = _safe_snapshot(Custom())
        assert isinstance(result, str)
        assert "Custom" in result

    def test_truncation_applied(self) -> None:
        class LongRepr:
            def __repr__(self) -> str:
                return "x" * 1000

        result = _safe_snapshot(LongRepr(), max_str_len=10)
        assert len(result) == 10


class TestTraceContext:
    def test_current_returns_none_outside_context(self) -> None:
        assert TraceContext.current() is None

    def test_record_and_consume(self) -> None:
        ctx = TraceContext()
        ctx.record_llm_call(
            model="openai/gpt-4o-mini",
            provider="openai",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        )
        result = ctx.consume_llm_call()
        assert result is not None
        assert result.model == "openai/gpt-4o-mini"
        assert result.prompt_tokens == 100
        assert result.total_tokens == 150

    def test_consume_clears_data(self) -> None:
        ctx = TraceContext()
        ctx.record_llm_call(
            model="openai/gpt-4o-mini",
            provider="openai",
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
        )
        ctx.consume_llm_call()
        assert ctx.consume_llm_call() is None

    def test_consume_without_record_returns_none(self) -> None:
        ctx = TraceContext()
        assert ctx.consume_llm_call() is None

    def test_cost_estimation_applied_for_known_model(self) -> None:
        ctx = TraceContext()
        ctx.record_llm_call(
            model="openai/gpt-4o-mini",
            provider="openai",
            prompt_tokens=1000,
            completion_tokens=500,
            total_tokens=1500,
        )
        result = ctx.consume_llm_call()
        assert result is not None
        assert result.estimated_cost_usd is not None
        assert result.estimated_cost_usd > 0

    def test_cost_estimation_none_for_unknown_model(self) -> None:
        ctx = TraceContext()
        ctx.record_llm_call(
            model="unknown/model-xyz",
            provider="unknown",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        )
        result = ctx.consume_llm_call()
        assert result is not None
        assert result.estimated_cost_usd is None


class TestTraceCollector:
    def _make_collector(self, **kwargs: Any) -> TraceCollector:
        defaults = {
            "workflow_name": "test_workflow",
            "workflow_version": "1.0",
        }
        return TraceCollector(**(defaults | kwargs))

    def test_wrap_node_records_success(self) -> None:
        collector = self._make_collector()

        def simple_handler(state: dict) -> dict:
            return {"output": "hello"}

        wrapped = collector.wrap_node(
            node_id="my_node",
            handler=simple_handler,
            handler_name="custom",
        )
        result = wrapped({"input": "world"})
        assert result == {"output": "hello"}

        now = datetime.now(tz=UTC)
        trace = collector.build_trace(
            started_at=now,
            ended_at=now,
            total_duration_ms=100.0,
        )
        assert len(trace.nodes) == 1
        node = trace.nodes[0]
        assert node.node_id == "my_node"
        assert node.handler == "custom"
        assert node.status == NodeStatus.SUCCESS
        assert node.duration_ms >= 0
        assert node.llm_call is None
        assert node.error is None

    def test_wrap_node_records_error(self) -> None:
        collector = self._make_collector()

        def failing_handler(state: dict) -> dict:
            raise ValueError("test error")

        wrapped = collector.wrap_node(
            node_id="fail_node",
            handler=failing_handler,
            handler_name="custom",
        )
        with pytest.raises(ValueError, match="test error"):
            wrapped({})

        now = datetime.now(tz=UTC)
        trace = collector.build_trace(
            started_at=now,
            ended_at=now,
            total_duration_ms=50.0,
        )
        assert len(trace.nodes) == 1
        node = trace.nodes[0]
        assert node.status == NodeStatus.ERROR
        assert node.error is not None
        assert "test error" in node.error.error_message
        assert "ValueError" in node.error.error_type

    def test_wrap_node_captures_snapshots(self) -> None:
        collector = self._make_collector()

        def handler(state: dict) -> dict:
            return {"result": "done"}

        wrapped = collector.wrap_node("n1", handler, "custom")
        wrapped({"key1": "val1", "key2": 42})

        now = datetime.now(tz=UTC)
        trace = collector.build_trace(started_at=now, ended_at=now, total_duration_ms=10.0)
        node = trace.nodes[0]
        assert node.input_snapshot["key1"] == "val1"
        assert node.input_snapshot["key2"] == 42
        assert "result" in node.output_snapshot

    def test_build_trace_summary_aggregated(self) -> None:
        collector = self._make_collector()

        def handler_a(state: dict) -> dict:
            return {"a": 1}

        def handler_b(state: dict) -> dict:
            return {"b": 2}

        wrapped_a = collector.wrap_node("node_a", handler_a, "custom")
        wrapped_b = collector.wrap_node("node_b", handler_b, "custom")

        wrapped_a({})
        wrapped_b({})

        now = datetime.now(tz=UTC)
        trace = collector.build_trace(started_at=now, ended_at=now, total_duration_ms=200.0)
        assert trace.summary.total_nodes_executed == 2
        assert trace.summary.succeeded_nodes == 2
        assert trace.summary.node_order == ["node_a", "node_b"]

    def test_snapshot_key_filtering(self) -> None:
        collector = self._make_collector(snapshot_keys=frozenset({"allowed"}))

        def handler(state: dict) -> dict:
            return {"allowed": "yes", "secret": "no"}

        wrapped = collector.wrap_node("n1", handler, "custom")
        wrapped({"allowed": "hello", "secret": "hidden"})

        now = datetime.now(tz=UTC)
        trace = collector.build_trace(started_at=now, ended_at=now, total_duration_ms=5.0)
        node = trace.nodes[0]
        assert "allowed" in node.input_snapshot
        assert "secret" not in node.input_snapshot

    def test_include_traceback_false(self) -> None:
        collector = self._make_collector(include_traceback=False)

        def failing_handler(state: dict) -> dict:
            raise RuntimeError("no tb")

        wrapped = collector.wrap_node("n1", failing_handler, "custom")
        with pytest.raises(RuntimeError):
            wrapped({})

        now = datetime.now(tz=UTC)
        trace = collector.build_trace(started_at=now, ended_at=now, total_duration_ms=5.0)
        assert trace.nodes[0].error is not None
        assert trace.nodes[0].error.traceback is None

    def test_overall_status_is_error_when_any_node_fails(self) -> None:
        collector = self._make_collector()

        collector.wrap_node("ok_node", lambda s: {"x": 1}, "custom")({})
        with pytest.raises(ValueError):
            collector.wrap_node(
                "err_node", lambda s: (_ for _ in ()).throw(ValueError("oops")), "custom"
            )({})

        now = datetime.now(tz=UTC)
        trace = collector.build_trace(started_at=now, ended_at=now, total_duration_ms=10.0)
        assert trace.status == NodeStatus.ERROR
