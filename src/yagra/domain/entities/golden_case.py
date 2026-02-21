"""Golden test case domain entities for workflow regression testing (G-20).

Defines the core data structures for capturing, storing, and comparing
golden reference executions against replayed workflow runs.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from yagra.domain.entities.comparison import ComparisonStrategy

LLM_HANDLER_NAMES: frozenset[str] = frozenset({"llm", "structured_llm", "streaming_llm"})
"""Handler names recognised as LLM handlers for golden test comparison.

Used to decide whether a node's output should be mocked during replay
(LLM handlers return their golden snapshot) and whether comparison
defaults to STRUCTURAL (LLM) or EXACT (non-LLM) under the AUTO strategy.
"""


class NodeSnapshot(BaseModel):
    """Captured input/output for a single node execution in a golden case.

    Stores the handler configuration and state snapshots that were observed
    during the original successful workflow run.

    Attributes:
        node_id: Node identifier as declared in the workflow YAML.
        handler: Handler name used by the node (e.g. 'llm', 'custom_formatter').
        is_llm_handler: True for llm/structured_llm/streaming_llm handlers.
        input_snapshot: State keys read by the node before execution.
        output_snapshot: State keys written by the node after execution.
        comparison_strategy: Strategy for comparing this node during replay.
            AUTO resolves to EXACT for non-LLM and STRUCTURAL for LLM.
    """

    model_config = ConfigDict(extra="forbid")

    node_id: str = Field(
        description="Node identifier as declared in the workflow YAML.",
        examples=["translate", "format_output"],
    )
    handler: str = Field(
        description="Handler name resolved at runtime.",
        examples=["llm", "structured_llm", "custom_formatter"],
    )
    is_llm_handler: bool = Field(
        description="True for built-in LLM handlers (llm, structured_llm, streaming_llm).",
    )
    input_snapshot: dict[str, Any] = Field(
        default_factory=dict,
        description="State keys read by the node before execution.",
    )
    output_snapshot: dict[str, Any] = Field(
        default_factory=dict,
        description="State keys written by the node after execution.",
    )
    comparison_strategy: ComparisonStrategy = Field(
        default=ComparisonStrategy.AUTO,
        description=(
            "Comparison strategy for replay validation. "
            "AUTO resolves to EXACT for non-LLM, STRUCTURAL for LLM."
        ),
    )


class GoldenCase(BaseModel):
    """A saved reference execution for regression testing.

    Captures the complete execution context of a successful workflow run,
    including initial state, execution path, and per-node snapshots.
    Used as the baseline for replay-based regression testing.

    Attributes:
        schema_version: Golden case format version for future compatibility.
        case_name: Human-readable name in kebab-case (e.g. 'happy-path-translate').
        description: Optional description of what this case covers.
        workflow_name: Name of the workflow (YAML file stem).
        workflow_path: Relative path to the workflow YAML file.
        created_at: UTC timestamp when the golden case was created.
        source_run_id: run_id of the originating WorkflowRunTrace.
        initial_state: State dict passed to Yagra.invoke() for this run.
        final_state: State dict after the workflow completed.
        execution_path: Ordered list of executed node_ids.
        node_snapshots: Per-node input/output snapshots keyed by node_id.
        metadata: Optional metadata for extensibility.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="1.0",
        description="Golden case format schema version. Currently '1.0'.",
    )
    case_name: str = Field(
        description="Human-readable name in kebab-case.",
        examples=["happy-path-translate", "error-handling-case"],
    )
    description: str = Field(
        default="",
        description="Optional description of what this test case covers.",
    )
    workflow_name: str = Field(
        description="Name of the workflow (YAML file stem).",
        examples=["translate", "multi-agent-pipeline"],
    )
    workflow_path: str = Field(
        description="Relative path to the workflow YAML file.",
        examples=["workflows/translate.yaml"],
    )
    created_at: datetime = Field(
        description="UTC timestamp when the golden case was created.",
    )
    source_run_id: str = Field(
        description="run_id of the originating WorkflowRunTrace.",
        examples=["a1b2c3d4-e5f6-7890-abcd-ef1234567890"],
    )
    initial_state: dict[str, Any] = Field(
        default_factory=dict,
        description="State dict passed to Yagra.invoke() at the start of the run.",
    )
    final_state: dict[str, Any] = Field(
        default_factory=dict,
        description="State dict after the workflow completed successfully.",
    )
    execution_path: list[str] = Field(
        default_factory=list,
        description="Ordered list of executed node_ids.",
    )
    node_snapshots: dict[str, NodeSnapshot] = Field(
        default_factory=dict,
        description="Per-node snapshots keyed by node_id.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional metadata for extensibility.",
    )


class NodeComparisonResult(BaseModel):
    """Comparison result for a single node during golden test replay.

    Attributes:
        node_id: Node identifier being compared.
        status: Result status: 'pass', 'fail', 'skip', 'missing', or 'unexpected'.
        strategy_used: The comparison strategy that was actually applied.
        input_match: Whether input snapshots matched. None if skipped.
        output_match: Whether output snapshots matched. None if skipped.
        input_diff: Diff details when input does not match. None otherwise.
        output_diff: Diff details when output does not match. None otherwise.
        message: Human-readable explanation of the result.
    """

    model_config = ConfigDict(extra="forbid")

    node_id: str = Field(
        description="Node identifier being compared.",
    )
    status: Literal["pass", "fail", "skip", "missing", "unexpected"] = Field(
        description=(
            "Result status: 'pass' (match), 'fail' (mismatch), 'skip' (strategy=skip), "
            "'missing' (expected but not executed), 'unexpected' (executed but not expected)."
        ),
    )
    strategy_used: ComparisonStrategy = Field(
        description="The comparison strategy that was actually applied.",
    )
    input_match: bool | None = Field(
        default=None,
        description="Whether input snapshots matched. None if skipped or missing.",
    )
    output_match: bool | None = Field(
        default=None,
        description="Whether output snapshots matched. None if skipped or missing.",
    )
    input_diff: dict[str, Any] | None = Field(
        default=None,
        description="Diff details when input does not match.",
    )
    output_diff: dict[str, Any] | None = Field(
        default=None,
        description="Diff details when output does not match.",
    )
    message: str = Field(
        default="",
        description="Human-readable explanation of the comparison result.",
    )


class GoldenTestResult(BaseModel):
    """Result of running a golden test case against a workflow.

    Attributes:
        case_name: Name of the golden test case.
        workflow_name: Name of the workflow tested.
        passed: Overall pass/fail status.
        executed_at: UTC timestamp when the test was executed.
        execution_path_match: Whether the execution path matched.
        expected_path: Expected execution path from the golden case.
        actual_path: Actual execution path from the replay.
        node_results: Per-node comparison results.
        summary: Human-readable summary of the test outcome.
    """

    model_config = ConfigDict(extra="forbid")

    case_name: str = Field(
        description="Name of the golden test case.",
    )
    workflow_name: str = Field(
        description="Name of the workflow tested.",
    )
    passed: bool = Field(
        description="Overall pass/fail status. True only if all checks pass.",
    )
    executed_at: datetime = Field(
        description="UTC timestamp when the test was executed.",
    )
    execution_path_match: bool = Field(
        description="Whether the execution path matched the golden reference.",
    )
    expected_path: list[str] = Field(
        default_factory=list,
        description="Expected execution path from the golden case.",
    )
    actual_path: list[str] = Field(
        default_factory=list,
        description="Actual execution path from the replay.",
    )
    node_results: list[NodeComparisonResult] = Field(
        default_factory=list,
        description="Per-node comparison results.",
    )
    summary: str = Field(
        default="",
        description="Human-readable summary of the test outcome.",
    )
