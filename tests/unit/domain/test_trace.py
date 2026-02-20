"""Unit tests for trace domain entities (G-14, G-15)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest

from yagra.domain.entities.trace import (
    ErrorTrace,
    LLMCallTrace,
    NodeStatus,
    NodeTrace,
    WorkflowRunTrace,
)


class TestNodeStatus:
    def test_success_value(self) -> None:
        assert NodeStatus.SUCCESS == "success"

    def test_error_value(self) -> None:
        assert NodeStatus.ERROR == "error"

    def test_skipped_value(self) -> None:
        assert NodeStatus.SKIPPED == "skipped"


class TestLLMCallTrace:
    def _make(self, **overrides: Any) -> LLMCallTrace:
        defaults: dict[str, Any] = {
            "model": "openai/gpt-4o-mini",
            "provider": "openai",
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
        }
        return LLMCallTrace(**(defaults | overrides))

    def test_basic_creation(self) -> None:
        trace = self._make()
        assert trace.model == "openai/gpt-4o-mini"
        assert trace.provider == "openai"
        assert trace.prompt_tokens == 100
        assert trace.completion_tokens == 50
        assert trace.total_tokens == 150
        assert trace.estimated_cost_usd is None

    def test_with_estimated_cost(self) -> None:
        trace = self._make(estimated_cost_usd=0.0001)
        assert trace.estimated_cost_usd == pytest.approx(0.0001)

    def test_prompt_tokens_cannot_be_negative(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            self._make(prompt_tokens=-1)

    def test_extra_fields_forbidden(self) -> None:
        from pydantic import ValidationError

        data: dict[str, Any] = {
            "model": "openai/gpt-4o-mini",
            "provider": "openai",
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
            "unknown_field": "x",
        }
        with pytest.raises(ValidationError):
            LLMCallTrace(**data)


class TestErrorTrace:
    def test_basic_creation(self) -> None:
        err = ErrorTrace(
            error_type="ValueError",
            error_message="something went wrong",
        )
        assert err.error_type == "ValueError"
        assert err.error_message == "something went wrong"
        assert err.traceback is None

    def test_with_traceback(self) -> None:
        err = ErrorTrace(
            error_type="RuntimeError",
            error_message="boom",
            traceback="Traceback (most recent call last):\n  ...",
        )
        assert err.traceback is not None
        assert "Traceback" in err.traceback


class TestNodeTrace:
    def _make(self, **overrides: Any) -> NodeTrace:
        now = datetime.now(tz=UTC)
        defaults: dict[str, Any] = {
            "node_id": "translate",
            "handler": "llm",
            "status": NodeStatus.SUCCESS,
            "started_at": now,
            "ended_at": now,
            "duration_ms": 123.456,
        }
        return NodeTrace(**(defaults | overrides))

    def test_basic_creation(self) -> None:
        trace = self._make()
        assert trace.node_id == "translate"
        assert trace.handler == "llm"
        assert trace.status == NodeStatus.SUCCESS
        assert trace.duration_ms == pytest.approx(123.456)
        assert trace.llm_call is None
        assert trace.error is None
        assert trace.input_snapshot == {}
        assert trace.output_snapshot == {}

    def test_with_llm_call(self) -> None:
        llm_call = LLMCallTrace(
            model="openai/gpt-4o-mini",
            provider="openai",
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
        )
        trace = self._make(llm_call=llm_call)
        assert trace.llm_call is not None
        assert trace.llm_call.total_tokens == 15

    def test_with_error(self) -> None:
        error = ErrorTrace(error_type="ValueError", error_message="oops")
        trace = self._make(status=NodeStatus.ERROR, error=error)
        assert trace.status == NodeStatus.ERROR
        assert trace.error is not None
        assert trace.error.error_message == "oops"

    def test_duration_cannot_be_negative(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            self._make(duration_ms=-1.0)


class TestWorkflowRunTrace:
    def _make_node_traces(self, count: int = 1) -> list[NodeTrace]:
        now = datetime.now(tz=UTC)
        return [
            NodeTrace(
                node_id=f"node_{i}",
                handler="llm",
                status=NodeStatus.SUCCESS,
                started_at=now,
                ended_at=now,
                duration_ms=float(100 + i),
            )
            for i in range(count)
        ]

    def test_compute_summary_no_llm(self) -> None:
        nodes = self._make_node_traces(3)
        summary = WorkflowRunTrace.compute_summary(nodes, total_duration_ms=500.0)
        assert summary.total_nodes_executed == 3
        assert summary.succeeded_nodes == 3
        assert summary.failed_nodes == 0
        assert summary.total_tokens == 0
        assert summary.total_estimated_cost_usd is None
        assert summary.node_order == ["node_0", "node_1", "node_2"]

    def test_compute_summary_with_llm(self) -> None:
        nodes = self._make_node_traces(2)
        nodes[0].llm_call = LLMCallTrace(
            model="openai/gpt-4o-mini",
            provider="openai",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            estimated_cost_usd=0.0001,
        )
        nodes[1].llm_call = LLMCallTrace(
            model="openai/gpt-4o-mini",
            provider="openai",
            prompt_tokens=200,
            completion_tokens=80,
            total_tokens=280,
            estimated_cost_usd=0.0002,
        )
        summary = WorkflowRunTrace.compute_summary(nodes, total_duration_ms=300.0)
        assert summary.total_prompt_tokens == 300
        assert summary.total_completion_tokens == 130
        assert summary.total_tokens == 430
        assert summary.total_estimated_cost_usd == pytest.approx(0.0003)

    def test_compute_summary_mixed_status(self) -> None:
        nodes = self._make_node_traces(3)
        nodes[2] = NodeTrace(
            node_id="node_2",
            handler="llm",
            status=NodeStatus.ERROR,
            started_at=nodes[0].started_at,
            ended_at=nodes[0].ended_at,
            duration_ms=50.0,
            error=ErrorTrace(error_type="ValueError", error_message="fail"),
        )
        summary = WorkflowRunTrace.compute_summary(nodes, total_duration_ms=250.0)
        assert summary.succeeded_nodes == 2
        assert summary.failed_nodes == 1

    def test_build_metadata_returns_dict(self) -> None:
        meta = WorkflowRunTrace.build_metadata()
        assert "yagra_version" in meta
        assert "python_version" in meta
        assert "platform" in meta

    def test_full_construction(self) -> None:
        now = datetime.now(tz=UTC)
        nodes = self._make_node_traces(1)
        summary = WorkflowRunTrace.compute_summary(nodes, total_duration_ms=150.0)
        run_trace = WorkflowRunTrace(
            workflow_name="translate",
            workflow_version="1.0",
            started_at=now,
            ended_at=now,
            status=NodeStatus.SUCCESS,
            nodes=nodes,
            summary=summary,
        )
        assert run_trace.schema_version == "1.0"
        assert isinstance(run_trace.run_id, UUID)
        assert run_trace.workflow_name == "translate"

    def test_model_dump_json_serializable(self) -> None:
        """model_dump(mode='json') must produce only JSON-primitive types."""
        import json

        now = datetime.now(tz=UTC)
        nodes = self._make_node_traces(1)
        summary = WorkflowRunTrace.compute_summary(nodes, total_duration_ms=150.0)
        run_trace = WorkflowRunTrace(
            workflow_name="translate",
            workflow_version="1.0",
            started_at=now,
            ended_at=now,
            status=NodeStatus.SUCCESS,
            nodes=nodes,
            summary=summary,
        )
        payload = run_trace.model_dump(mode="json")
        # Should not raise
        json_str = json.dumps(payload)
        assert len(json_str) > 0
