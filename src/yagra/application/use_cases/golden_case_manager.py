"""Use case for managing golden test cases (G-20, M-50).

Provides operations to create golden cases from workflow execution traces,
list saved cases, and delete cases. Acts as the orchestration layer between
the domain entities and the persistence port.
"""

from __future__ import annotations

import re
from typing import Any

from yagra.domain.entities.comparison import ComparisonStrategy
from yagra.domain.entities.golden_case import LLM_HANDLER_NAMES, GoldenCase, NodeSnapshot
from yagra.domain.entities.trace import NodeStatus, WorkflowRunTrace
from yagra.ports.outbound.golden_case_repository import GoldenCaseRepositoryPort

_KEBAB_CASE_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


class GoldenCaseManager:
    """Orchestrates golden case CRUD operations.

    Bridges the gap between raw workflow traces and the golden case
    persistence layer by extracting relevant data from WorkflowRunTrace
    and delegating storage to the repository port.

    Args:
        repository: Persistence backend for golden cases.
    """

    def __init__(self, repository: GoldenCaseRepositoryPort) -> None:
        """Initializes the manager with a repository.

        Args:
            repository: Persistence backend for golden cases.
        """
        self._repository = repository

    def save_from_trace(
        self,
        trace: WorkflowRunTrace,
        case_name: str,
        description: str = "",
        comparison_overrides: dict[str, ComparisonStrategy] | None = None,
    ) -> GoldenCase:
        """Creates and persists a golden case from a successful trace.

        Extracts per-node input/output snapshots, execution path, and
        initial/final state from the trace to build a GoldenCase entity.
        LLM handlers are automatically detected and flagged so that their
        output comparison defaults to structural matching.

        Args:
            trace: A successful WorkflowRunTrace to use as reference.
            case_name: Name for the golden case (kebab-case).
            description: Optional human-readable description.
            comparison_overrides: Per-node comparison strategy overrides.
                Keys are node_ids, values are ComparisonStrategy values.

        Returns:
            The saved GoldenCase.

        Raises:
            ValueError: If trace has failed status or case_name is invalid.
        """
        if trace.status != NodeStatus.SUCCESS:
            msg = f"Cannot create golden case from trace with status '{trace.status}'"
            raise ValueError(msg)

        if not _KEBAB_CASE_RE.match(case_name):
            msg = (
                f"Invalid case_name '{case_name}': must be kebab-case "
                "(lowercase alphanumeric with hyphens, e.g. 'happy-path')"
            )
            raise ValueError(msg)

        overrides = comparison_overrides or {}
        node_snapshots: dict[str, NodeSnapshot] = {}
        execution_path: list[str] = []

        for node_trace in trace.nodes:
            if node_trace.status == NodeStatus.SKIPPED:
                continue
            execution_path.append(node_trace.node_id)

            is_llm = node_trace.handler in LLM_HANDLER_NAMES
            strategy = overrides.get(node_trace.node_id, ComparisonStrategy.AUTO)

            node_snapshots[node_trace.node_id] = NodeSnapshot(
                node_id=node_trace.node_id,
                handler=node_trace.handler,
                is_llm_handler=is_llm,
                input_snapshot=dict(node_trace.input_snapshot),
                output_snapshot=dict(node_trace.output_snapshot),
                comparison_strategy=strategy,
            )

        initial_state = _extract_initial_state(trace)
        final_state = _extract_final_state(trace)

        golden_case = GoldenCase(
            case_name=case_name,
            description=description,
            workflow_name=trace.workflow_name,
            workflow_path=trace.workflow_path or "",
            created_at=trace.started_at,
            source_run_id=str(trace.run_id),
            initial_state=initial_state,
            final_state=final_state,
            execution_path=execution_path,
            node_snapshots=node_snapshots,
        )

        self._repository.save(golden_case)
        return golden_case

    def list_cases(self, workflow_name: str | None = None) -> list[GoldenCase]:
        """Lists saved golden cases, optionally filtered by workflow.

        Args:
            workflow_name: If provided, only returns cases for this workflow.

        Returns:
            List of golden cases sorted by workflow_name then case_name.
        """
        return self._repository.list(workflow_name)

    def delete_case(self, workflow_name: str, case_name: str) -> bool:
        """Deletes a golden case.

        Args:
            workflow_name: Name of the workflow.
            case_name: Name of the case to delete.

        Returns:
            True if the case was deleted, False if it did not exist.
        """
        return self._repository.delete(workflow_name, case_name)


def _extract_initial_state(trace: WorkflowRunTrace) -> dict[str, Any]:
    """Extracts the initial state from the first node's input snapshot.

    Args:
        trace: Workflow run trace.

    Returns:
        Initial state dict. Empty dict if no nodes were executed.
    """
    if not trace.nodes:
        return {}
    return dict(trace.nodes[0].input_snapshot)


def _extract_final_state(trace: WorkflowRunTrace) -> dict[str, Any]:
    """Extracts the final state from the last node's merged state.

    The last node's output is merged with its input to reconstruct
    the complete state at the end of execution.

    Args:
        trace: Workflow run trace.

    Returns:
        Final state dict. Empty dict if no nodes were executed.
    """
    if not trace.nodes:
        return {}
    last = trace.nodes[-1]
    merged = dict(last.input_snapshot)
    merged.update(last.output_snapshot)
    return merged
