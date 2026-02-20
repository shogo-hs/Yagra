"""Trace collection hook integration for LangGraph execution (G-14, G-15).

This module provides the TraceCollector, which intercepts node execution
via a wrapping strategy to maintain compatibility with any LangGraph version.

Design decision: Rather than relying on LangGraph's callback system (which
varies across versions), we wrap node runner callables at build time with
_TracingNodeRunner. This gives us precise control over start/end timing
and error capture without coupling to LangGraph internals.

The LLM handlers communicate token data to the collector via a thread-local
TraceContext object, avoiding the need to change NodeHandler return signatures.
"""

from __future__ import annotations

import threading
import traceback as tb_module
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from yagra.domain.entities.cost_table import estimate_cost
from yagra.domain.entities.trace import (
    ErrorTrace,
    LLMCallTrace,
    NodeStatus,
    NodeTrace,
    WorkflowRunTrace,
)

# Thread-local storage for LLM handlers to report token usage back to the collector
# without changing NodeHandler return signatures.
_trace_context: threading.local = threading.local()


class TraceContext:
    """Thread-local context allowing LLM handlers to report token usage.

    LLM handlers call TraceContext.current().record_llm_call(...) after
    litellm.completion() returns. The TraceCollector reads this data when
    the node runner wrapper completes.

    Usage in LLM handlers (after litellm.completion()):
        ctx = TraceContext.current()
        if ctx is not None:
            ctx.record_llm_call(
                model=litellm_model,
                provider=provider,
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
            )
    """

    def __init__(self) -> None:
        """Initializes an empty context."""
        self._llm_call: LLMCallTrace | None = None

    @classmethod
    def current(cls) -> TraceContext | None:
        """Returns the active TraceContext for this thread, or None if not tracing.

        Returns:
            Active TraceContext, or None when trace=False.
        """
        return getattr(_trace_context, "active", None)

    def record_llm_call(
        self,
        model: str,
        provider: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
    ) -> None:
        """Records token usage from a litellm response.

        Args:
            model: Full litellm model string, e.g. 'openai/gpt-4o-mini'.
            provider: Provider name, e.g. 'openai'.
            prompt_tokens: Number of input tokens.
            completion_tokens: Number of output tokens.
            total_tokens: Total tokens consumed.
        """
        self._llm_call = LLMCallTrace(
            model=model,
            provider=provider,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=estimate_cost(model, prompt_tokens, completion_tokens),
        )

    def consume_llm_call(self) -> LLMCallTrace | None:
        """Retrieves and clears the recorded LLM call data.

        Returns:
            LLMCallTrace if recorded, otherwise None.
        """
        result = self._llm_call
        self._llm_call = None
        return result


@contextmanager
def _active_trace_context() -> Generator[TraceContext, None, None]:
    """Context manager that installs a fresh TraceContext as the thread-local active context.

    Yields:
        A fresh TraceContext instance set as the active context for this thread.
    """
    ctx = TraceContext()
    _trace_context.active = ctx
    try:
        yield ctx
    finally:
        _trace_context.active = None


def _safe_snapshot(value: Any, max_str_len: int = 500) -> Any:
    """Converts a value to a JSON-serializable form for snapshot storage.

    Args:
        value: Any Python value from workflow state.
        max_str_len: Maximum string length for repr() fallback values.

    Returns:
        JSON-serializable representation of the value.
    """
    if isinstance(value, (str, int, float, bool, type(None))):
        return value
    if isinstance(value, dict):
        return {k: _safe_snapshot(v, max_str_len) for k, v in value.items()}
    if isinstance(value, list):
        return [_safe_snapshot(item, max_str_len) for item in value]
    # Non-serializable: use repr() truncated
    return repr(value)[:max_str_len]


class TraceCollector:
    """Collects node execution traces during a single Yagra.invoke() call.

    Usage:
        collector = TraceCollector(
            workflow_name="translate",
            workflow_version="1.0",
        )
        wrapped_handler = collector.wrap_node(
            node_id="translate",
            handler=original_handler,
            handler_name="llm",
        )
        # Build graph with wrapped handlers, then:
        run_trace = collector.build_trace(
            started_at=started_at,
            ended_at=ended_at,
            total_duration_ms=total_ms,
        )

    Attributes:
        workflow_name: Name of the workflow being executed.
        workflow_version: Version string from GraphSpec.
        workflow_path: Path to the workflow YAML, if available.
        include_traceback: Whether to include Python tracebacks in ErrorTrace.
        snapshot_keys: If set, only these state keys are included in snapshots.
    """

    def __init__(
        self,
        workflow_name: str,
        workflow_version: str,
        workflow_path: str | None = None,
        include_traceback: bool = True,
        snapshot_keys: frozenset[str] | None = None,
    ) -> None:
        """Initializes the collector.

        Args:
            workflow_name: Workflow stem name.
            workflow_version: Version from GraphSpec.
            workflow_path: Absolute path to the workflow YAML.
            include_traceback: Whether to capture full Python tracebacks.
            snapshot_keys: Allowlist of state keys to capture. None = all keys.
        """
        self._workflow_name = workflow_name
        self._workflow_version = workflow_version
        self._workflow_path = workflow_path
        self._include_traceback = include_traceback
        self._snapshot_keys = snapshot_keys
        self._node_traces: list[NodeTrace] = []
        self._lock = threading.Lock()

    def wrap_node(
        self,
        node_id: str,
        handler: Any,
        handler_name: str,
    ) -> Any:
        """Returns a wrapped handler that records a NodeTrace on each invocation.

        The wrapper installs a thread-local TraceContext so LLM handlers can
        report token usage back. It captures input/output snapshots and elapsed time.

        Args:
            node_id: Node identifier from the workflow YAML.
            handler: Original node handler callable.
            handler_name: Handler name string for trace metadata.

        Returns:
            Wrapped callable with identical signature to handler.
        """
        collector = self

        def _traced_run(state: dict[str, Any]) -> dict[str, Any]:
            started_at = datetime.now(tz=UTC)
            t0 = perf_counter()

            input_snapshot = collector._make_snapshot(state)

            result: dict[str, Any] = {}
            status = NodeStatus.SUCCESS
            output_snapshot: dict[str, Any] = {}
            error_trace: ErrorTrace | None = None
            llm_call: LLMCallTrace | None = None

            with _active_trace_context() as ctx:
                try:
                    result = handler(state)
                    status = NodeStatus.SUCCESS
                    output_snapshot = collector._make_snapshot(result if result is not None else {})
                    llm_call = ctx.consume_llm_call()
                except Exception as exc:
                    status = NodeStatus.ERROR
                    output_snapshot = {}
                    traceback_str = tb_module.format_exc() if collector._include_traceback else None
                    error_trace = ErrorTrace(
                        error_type=f"{type(exc).__module__}.{type(exc).__qualname__}",
                        error_message=str(exc)[:2000],
                        traceback=traceback_str,
                    )
                    llm_call = ctx.consume_llm_call()
                    raise
                finally:
                    ended_at = datetime.now(tz=UTC)
                    duration_ms = (perf_counter() - t0) * 1000.0

                    node_trace = NodeTrace(
                        node_id=node_id,
                        handler=handler_name,
                        status=status,
                        started_at=started_at,
                        ended_at=ended_at,
                        duration_ms=round(duration_ms, 3),
                        input_snapshot=input_snapshot,
                        output_snapshot=output_snapshot,
                        llm_call=llm_call,
                        error=error_trace,
                    )
                    with collector._lock:
                        collector._node_traces.append(node_trace)

            return result

        return _traced_run

    def _make_snapshot(self, state: dict[str, Any]) -> dict[str, Any]:
        """Creates a safe JSON-serializable snapshot of state.

        Args:
            state: State dict to snapshot.

        Returns:
            Filtered and serialized snapshot.
        """
        keys = self._snapshot_keys
        if keys is not None:
            filtered = {k: v for k, v in state.items() if k in keys}
        else:
            filtered = dict(state)
        return {k: _safe_snapshot(v) for k, v in filtered.items()}

    def build_trace(
        self,
        started_at: datetime,
        ended_at: datetime,
        total_duration_ms: float,
    ) -> WorkflowRunTrace:
        """Assembles a complete WorkflowRunTrace from collected node traces.

        Args:
            started_at: When Yagra.invoke() was called.
            ended_at: When Yagra.invoke() returned.
            total_duration_ms: Total wall-clock time of the run.

        Returns:
            Completed WorkflowRunTrace ready for persistence.
        """
        with self._lock:
            nodes = list(self._node_traces)

        overall_status = (
            NodeStatus.ERROR
            if any(n.status == NodeStatus.ERROR for n in nodes)
            else NodeStatus.SUCCESS
        )
        summary = WorkflowRunTrace.compute_summary(nodes, total_duration_ms)

        return WorkflowRunTrace(
            workflow_name=self._workflow_name,
            workflow_version=self._workflow_version,
            workflow_path=self._workflow_path,
            started_at=started_at,
            ended_at=ended_at,
            status=overall_status,
            nodes=nodes,
            summary=summary,
            metadata=WorkflowRunTrace.build_metadata(),
        )
