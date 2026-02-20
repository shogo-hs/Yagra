"""Trace aggregation and summary generation across multiple workflow runs (M-42).

Loads WorkflowRunTrace JSON files from the trace directory, aggregates
per-node and overall statistics, and produces a structured AggregatedSummary.
"""

from __future__ import annotations

import json
import math
import statistics
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class NodeStats:
    """Per-node aggregated statistics across multiple runs.

    Attributes:
        node_id: Unique node identifier from the workflow YAML.
        execution_count: Total number of times this node was executed.
        success_count: Number of executions with status 'success'.
        error_count: Number of executions with status 'error'.
        success_rate: Ratio of successful executions (0.0-1.0).
        avg_duration_ms: Mean execution duration in milliseconds.
        min_duration_ms: Minimum execution duration in milliseconds.
        max_duration_ms: Maximum execution duration in milliseconds.
        p50_duration_ms: Median (50th percentile) execution duration in milliseconds.
        p95_duration_ms: 95th percentile execution duration in milliseconds.
        total_prompt_tokens: Sum of prompt tokens across all LLM calls for this node.
        total_completion_tokens: Sum of completion tokens across all LLM calls for this node.
        total_tokens: Sum of all tokens across all LLM calls for this node.
        avg_tokens_per_call: Average total tokens per LLM call. 0.0 if no LLM calls.
        total_estimated_cost_usd: Aggregated estimated cost in USD. None if no pricing data.
        error_types: Distribution of error types as {error_type: count}.
    """

    node_id: str
    execution_count: int
    success_count: int
    error_count: int
    success_rate: float
    avg_duration_ms: float
    min_duration_ms: float
    max_duration_ms: float
    p50_duration_ms: float
    p95_duration_ms: float
    total_prompt_tokens: int
    total_completion_tokens: int
    total_tokens: int
    avg_tokens_per_call: float
    total_estimated_cost_usd: float | None
    error_types: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class AggregatedSummary:
    """Summary across multiple workflow runs.

    Attributes:
        workflow_name: Name of the workflow being summarized.
        total_runs: Total number of runs included in this aggregation.
        successful_runs: Number of runs with status 'success'.
        failed_runs: Number of runs with status 'error'.
        run_success_rate: Ratio of successful runs (0.0-1.0).
        avg_total_duration_ms: Mean total run duration in milliseconds.
        min_total_duration_ms: Minimum total run duration in milliseconds.
        max_total_duration_ms: Maximum total run duration in milliseconds.
        total_prompt_tokens: Sum of prompt tokens across all runs.
        total_completion_tokens: Sum of completion tokens across all runs.
        total_tokens: Sum of all tokens across all runs.
        total_estimated_cost_usd: Aggregated estimated cost in USD. None if no pricing data.
        node_stats: Per-node aggregated statistics.
        time_range_start: ISO-8601 timestamp of the earliest run.
        time_range_end: ISO-8601 timestamp of the latest run.
        schema_version: Schema version for this aggregation format.
    """

    workflow_name: str
    total_runs: int
    successful_runs: int
    failed_runs: int
    run_success_rate: float
    avg_total_duration_ms: float
    min_total_duration_ms: float
    max_total_duration_ms: float
    total_prompt_tokens: int
    total_completion_tokens: int
    total_tokens: int
    total_estimated_cost_usd: float | None
    node_stats: list[NodeStats]
    time_range_start: str
    time_range_end: str
    schema_version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        """Convert to a JSON-serializable dictionary.

        Returns:
            Dictionary representation with all fields. None values are preserved
            for explicit null representation in JSON output.
        """
        result = asdict(self)
        # asdict handles nested dataclasses automatically.
        # Ensure float values are JSON-safe (no NaN/Inf).
        sanitized = _sanitize_for_json(result)
        assert isinstance(sanitized, dict)  # guaranteed by asdict returning dict
        return sanitized


def _sanitize_for_json(obj: Any) -> Any:
    """Recursively sanitize values for JSON serialization.

    Replaces NaN and Inf float values with None to ensure valid JSON output.

    Args:
        obj: Value to sanitize.

    Returns:
        JSON-safe value.
    """
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_for_json(v) for v in obj]
    return obj


def load_traces(
    trace_dir: str | Path,
    workflow_name: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Load trace JSON files from directory.

    Scans the trace directory for JSON files, parses them, sorts by started_at
    in descending order (most recent first), and optionally limits the result count.

    Args:
        trace_dir: Root trace directory (e.g., .yagra/traces).
        workflow_name: Filter by workflow name subdirectory. If None, load from
            all workflow subdirectories.
        limit: Maximum number of traces to load (most recent first). If None,
            load all available traces.

    Returns:
        List of trace dicts parsed from JSON files, sorted by started_at descending.
    """
    trace_path = Path(trace_dir)
    if not trace_path.exists():
        return []

    if workflow_name is not None:
        pattern = f"{workflow_name}/*.json"
    else:
        pattern = "**/*.json"

    traces: list[dict[str, Any]] = []
    for json_file in trace_path.glob(pattern):
        if not json_file.is_file():
            continue
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                traces.append(data)
        except (json.JSONDecodeError, OSError):
            # Skip malformed or unreadable files silently
            continue

    # Sort by started_at descending (most recent first)
    traces.sort(key=lambda t: t.get("started_at", ""), reverse=True)

    if limit is not None:
        traces = traces[:limit]

    return traces


def aggregate_traces(traces: list[dict[str, Any]]) -> AggregatedSummary:
    """Aggregate multiple trace records into a summary.

    Computes overall run statistics and per-node statistics including duration
    percentiles, token counts, costs, and error type distributions.

    Args:
        traces: List of trace dicts (as loaded from JSON files). Each dict
            should conform to the WorkflowRunTrace.model_dump(mode="json") format.

    Returns:
        AggregatedSummary with per-node and overall statistics.

    Raises:
        ValueError: If traces list is empty.
    """
    if not traces:
        raise ValueError("Cannot aggregate an empty list of traces.")

    # --- Overall run statistics ---
    total_runs = len(traces)
    successful_runs = sum(1 for t in traces if t.get("status") != "error")
    failed_runs = total_runs - successful_runs
    run_success_rate = successful_runs / total_runs if total_runs > 0 else 0.0

    # Workflow name from the first trace
    workflow_name = traces[0].get("workflow_name", "unknown")

    # Duration statistics from the summary.total_duration_ms field
    run_durations: list[float] = []
    for t in traces:
        summary = t.get("summary", {})
        duration = summary.get("total_duration_ms")
        if duration is not None:
            run_durations.append(float(duration))

    avg_total_duration = statistics.mean(run_durations) if run_durations else 0.0
    min_total_duration = min(run_durations) if run_durations else 0.0
    max_total_duration = max(run_durations) if run_durations else 0.0

    # Token and cost aggregation across all runs
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_tokens = 0
    total_estimated_cost: float | None = None

    for t in traces:
        summary = t.get("summary", {})
        total_prompt_tokens += summary.get("total_prompt_tokens", 0)
        total_completion_tokens += summary.get("total_completion_tokens", 0)
        total_tokens += summary.get("total_tokens", 0)
        cost = summary.get("total_estimated_cost_usd")
        if cost is not None:
            total_estimated_cost = (total_estimated_cost or 0.0) + cost

    # Time range
    started_ats = [t.get("started_at", "") for t in traces if t.get("started_at")]
    ended_ats = [t.get("ended_at", "") for t in traces if t.get("ended_at")]
    time_range_start = min(started_ats) if started_ats else ""
    time_range_end = max(ended_ats) if ended_ats else ""

    # --- Per-node statistics ---
    node_stats = _compute_node_stats(traces)

    return AggregatedSummary(
        workflow_name=workflow_name,
        total_runs=total_runs,
        successful_runs=successful_runs,
        failed_runs=failed_runs,
        run_success_rate=run_success_rate,
        avg_total_duration_ms=avg_total_duration,
        min_total_duration_ms=min_total_duration,
        max_total_duration_ms=max_total_duration,
        total_prompt_tokens=total_prompt_tokens,
        total_completion_tokens=total_completion_tokens,
        total_tokens=total_tokens,
        total_estimated_cost_usd=total_estimated_cost,
        node_stats=node_stats,
        time_range_start=time_range_start,
        time_range_end=time_range_end,
    )


def _compute_node_stats(traces: list[dict[str, Any]]) -> list[NodeStats]:
    """Compute per-node aggregated statistics from trace data.

    Iterates through all nodes across all runs, grouping by node_id, and
    computes duration percentiles, token sums, and error distributions.

    Args:
        traces: List of trace dicts.

    Returns:
        List of NodeStats, one per unique node_id, ordered by first appearance.
    """
    # Collect raw data per node_id, preserving insertion order
    node_data: dict[str, _NodeAccumulator] = {}

    for trace in traces:
        nodes = trace.get("nodes", [])
        for node in nodes:
            node_id = node.get("node_id", "")
            if node_id not in node_data:
                node_data[node_id] = _NodeAccumulator()
            node_data[node_id].add(node)

    return [acc.to_node_stats(node_id) for node_id, acc in node_data.items()]


class _NodeAccumulator:
    """Internal helper that accumulates raw node data for aggregation.

    Collects duration values, token counts, error types, and status counts
    as nodes are added, then produces a final NodeStats via to_node_stats().
    """

    def __init__(self) -> None:
        """Initializes empty accumulator."""
        self.execution_count: int = 0
        self.success_count: int = 0
        self.error_count: int = 0
        self.durations: list[float] = []
        self.prompt_tokens: int = 0
        self.completion_tokens: int = 0
        self.total_tokens_sum: int = 0
        self.llm_call_count: int = 0
        self.estimated_cost: float | None = None
        self.error_types: dict[str, int] = {}

    def add(self, node: dict[str, Any]) -> None:
        """Add a single node trace record to the accumulator.

        Args:
            node: Node trace dict from a WorkflowRunTrace.
        """
        self.execution_count += 1

        status = node.get("status", "")
        if status == "success":
            self.success_count += 1
        elif status == "error":
            self.error_count += 1

        duration = node.get("duration_ms")
        if duration is not None:
            self.durations.append(float(duration))

        llm_call = node.get("llm_call")
        if llm_call is not None:
            self.llm_call_count += 1
            self.prompt_tokens += llm_call.get("prompt_tokens", 0)
            self.completion_tokens += llm_call.get("completion_tokens", 0)
            self.total_tokens_sum += llm_call.get("total_tokens", 0)
            cost = llm_call.get("estimated_cost_usd")
            if cost is not None:
                self.estimated_cost = (self.estimated_cost or 0.0) + cost

        error = node.get("error")
        if error is not None:
            error_type = error.get("error_type", "Unknown")
            self.error_types[error_type] = self.error_types.get(error_type, 0) + 1

    def to_node_stats(self, node_id: str) -> NodeStats:
        """Compute final NodeStats from accumulated data.

        Args:
            node_id: The node identifier.

        Returns:
            Finalized NodeStats dataclass instance.
        """
        success_rate = (
            self.success_count / self.execution_count if self.execution_count > 0 else 0.0
        )

        if self.durations:
            avg_dur = statistics.mean(self.durations)
            min_dur = min(self.durations)
            max_dur = max(self.durations)
            p50_dur = statistics.median(self.durations)
            p95_dur = _percentile_95(self.durations)
        else:
            avg_dur = 0.0
            min_dur = 0.0
            max_dur = 0.0
            p50_dur = 0.0
            p95_dur = 0.0

        avg_tokens = self.total_tokens_sum / self.llm_call_count if self.llm_call_count > 0 else 0.0

        return NodeStats(
            node_id=node_id,
            execution_count=self.execution_count,
            success_count=self.success_count,
            error_count=self.error_count,
            success_rate=success_rate,
            avg_duration_ms=avg_dur,
            min_duration_ms=min_dur,
            max_duration_ms=max_dur,
            p50_duration_ms=p50_dur,
            p95_duration_ms=p95_dur,
            total_prompt_tokens=self.prompt_tokens,
            total_completion_tokens=self.completion_tokens,
            total_tokens=self.total_tokens_sum,
            avg_tokens_per_call=avg_tokens,
            total_estimated_cost_usd=self.estimated_cost,
            error_types=dict(self.error_types),
        )


def _percentile_95(values: list[float]) -> float:
    """Compute the 95th percentile of a list of values.

    Uses statistics.quantiles with n=20 to get the 95th percentile (19th of 20
    quantile boundaries). For lists with fewer than 2 elements, returns the
    single value or 0.0.

    Args:
        values: Non-empty list of numeric values.

    Returns:
        95th percentile value.
    """
    if len(values) == 0:
        return 0.0
    if len(values) == 1:
        return values[0]
    # quantiles(data, n=20) returns 19 cut points; the last one is the 95th percentile
    quantile_points = statistics.quantiles(values, n=20)
    return quantile_points[-1]
