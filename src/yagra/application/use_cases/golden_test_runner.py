"""Golden test execution engine for workflow regression testing (G-20, M-50).

Replays golden cases against modified workflows by mocking LLM handlers
with recorded output snapshots, then compares the replay results against
the golden reference to detect regressions.

The replay is deterministic: LLM nodes return their golden output_snapshot
directly, so no external API calls are made during testing.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from yagra.domain.entities.comparison import ComparisonStrategy, compare_snapshots
from yagra.domain.entities.golden_case import (
    GoldenCase,
    GoldenTestResult,
    NodeComparisonResult,
    NodeSnapshot,
)
from yagra.ports.outbound.golden_case_repository import GoldenCaseRepositoryPort
from yagra.ports.outbound.node_registry import (
    NodeHandler,
    NodeRegistryPort,
)


def create_mock_llm_handler(snapshot: NodeSnapshot) -> NodeHandler:
    """Creates a mock handler that returns the golden output snapshot.

    The mock handler ignores input state and params, returning only the
    output_snapshot from the golden case. This ensures deterministic
    replay without any external API calls.

    Args:
        snapshot: Node snapshot containing the output to replay.

    Returns:
        A callable with the standard handler signature that returns
        the golden output_snapshot.
    """
    frozen_output = dict(snapshot.output_snapshot)

    def _mock_handler(state: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
        """Returns the golden output snapshot regardless of input.

        Args:
            state: Current workflow state (ignored for LLM mocks).
            params: Node parameters (ignored for LLM mocks).

        Returns:
            A copy of the golden case output_snapshot for this node.
        """
        _ = state, params
        return dict(frozen_output)

    return _mock_handler


def build_golden_registry(
    golden_case: GoldenCase,
    base_registry: NodeRegistryPort,
) -> NodeRegistryPort:
    """Creates a registry with LLM handlers replaced by golden mocks.

    Each LLM node receives its own mock handler keyed by ``node_id``,
    so multiple nodes sharing the same handler name (e.g., two ``"llm"``
    nodes) return their individual golden output snapshots.

    Non-LLM handlers are resolved from the base registry.

    Args:
        golden_case: The golden case providing mock outputs.
        base_registry: The real registry for non-LLM handler resolution.

    Returns:
        A ``_GoldenNodeRegistry`` that dispatches per-node mocks for LLM
        handlers and falls back to *base_registry* for everything else.
    """
    node_mocks: dict[str, NodeHandler] = {}
    non_llm_handlers: dict[str, NodeHandler] = {}
    resolved_non_llm: set[str] = set()

    for node_id, snapshot in golden_case.node_snapshots.items():
        if snapshot.is_llm_handler:
            node_mocks[node_id] = create_mock_llm_handler(snapshot)
        else:
            handler_name = snapshot.handler
            if handler_name not in resolved_non_llm:
                non_llm_handlers[handler_name] = base_registry.resolve(handler_name)
                resolved_non_llm.add(handler_name)

    return _GoldenNodeRegistry(
        node_mocks=node_mocks,
        non_llm_handlers=non_llm_handlers,
        fallback=base_registry,
    )


class _GoldenNodeRegistry(NodeRegistryPort):
    """Registry that dispatches per-node mocks during golden test replay.

    LLM handlers are resolved **per node_id** so that multiple nodes
    sharing the same handler name (e.g., two ``"llm"`` nodes) each
    return their own golden output snapshot. Non-LLM handlers and any
    handlers absent from the golden case are resolved via the fallback
    base registry.

    Args:
        node_mocks: Mapping of *node_id* to mock handler for LLM nodes.
        non_llm_handlers: Mapping of *handler_name* to resolved handler
            for non-LLM nodes recorded in the golden case.
        fallback: Base registry used when a handler is not found in
            either ``node_mocks`` or ``non_llm_handlers``.
    """

    def __init__(
        self,
        node_mocks: dict[str, NodeHandler],
        non_llm_handlers: dict[str, NodeHandler],
        fallback: NodeRegistryPort,
    ) -> None:
        """Initializes with per-node mocks, non-LLM handlers, and fallback.

        Args:
            node_mocks: Per-node_id mock handlers for LLM nodes.
            non_llm_handlers: Resolved handlers for non-LLM handler names.
            fallback: Base registry for handlers not in the golden case.
        """
        self._node_mocks = node_mocks
        self._non_llm_handlers = non_llm_handlers
        self._fallback = fallback

    def register(self, name: str, handler: NodeHandler) -> None:
        """Registers a handler in the fallback registry.

        Args:
            name: Handler identifier name.
            handler: Callable to register.

        Raises:
            NodeHandlerAlreadyRegisteredError: If already registered.
        """
        self._fallback.register(name, handler)

    def resolve(self, name: str) -> NodeHandler:
        """Resolves a handler by handler name (non-node-aware fallback).

        Checks non-LLM handlers first, then delegates to the fallback
        registry. This path is used by callers that do not supply a
        ``node_id`` (e.g., legacy code or handler-compatibility checks).

        Args:
            name: Handler name to resolve.

        Returns:
            The resolved handler callable.

        Raises:
            NodeHandlerNotFoundError: If the handler cannot be resolved.
        """
        if name in self._non_llm_handlers:
            return self._non_llm_handlers[name]
        return self._fallback.resolve(name)

    def resolve_for_node(self, name: str, node_id: str) -> NodeHandler:
        """Resolves a handler for a specific node instance.

        For LLM nodes recorded in the golden case, returns the per-node
        mock handler. For non-LLM nodes, resolves by handler name. For
        handlers absent from the golden case, falls back to the base
        registry.

        Args:
            name: Handler name to resolve.
            node_id: Unique identifier of the node requesting the handler.

        Returns:
            The mock handler (LLM nodes) or real handler (non-LLM / new nodes).

        Raises:
            NodeHandlerNotFoundError: If the handler cannot be resolved.
        """
        if node_id in self._node_mocks:
            return self._node_mocks[node_id]
        return self.resolve(name)


def compare_node(
    expected: NodeSnapshot,
    actual_input: dict[str, Any],
    actual_output: dict[str, Any],
) -> NodeComparisonResult:
    """Compares a single node's replay results against its golden snapshot.

    Applies the node's comparison strategy to both input and output
    snapshots. For LLM nodes with AUTO strategy, output comparison
    uses structural matching (type-only); for non-LLM nodes, exact
    matching is used.

    Args:
        expected: The golden reference snapshot for this node.
        actual_input: The input snapshot captured during replay.
        actual_output: The output snapshot captured during replay.

    Returns:
        NodeComparisonResult with match status and diff details.
    """
    strategy = expected.comparison_strategy
    is_llm = expected.is_llm_handler

    if strategy == ComparisonStrategy.SKIP:
        return NodeComparisonResult(
            node_id=expected.node_id,
            status="skip",
            strategy_used=ComparisonStrategy.SKIP,
            message="Comparison skipped by strategy.",
        )

    resolved = _resolve_strategy(strategy, is_llm)

    input_diff = compare_snapshots(
        expected.input_snapshot, actual_input, strategy, is_llm_handler=is_llm
    )
    input_match = input_diff is None

    # For LLM nodes, skip output comparison (output is mocked)
    if is_llm:
        output_match = True
        output_diff = None
    else:
        output_diff = compare_snapshots(
            expected.output_snapshot, actual_output, strategy, is_llm_handler=is_llm
        )
        output_match = output_diff is None

    passed = input_match and output_match
    status: Literal["pass", "fail"] = "pass" if passed else "fail"

    message = _build_comparison_message(expected.node_id, passed, input_match, output_match)

    return NodeComparisonResult(
        node_id=expected.node_id,
        status=status,
        strategy_used=resolved,
        input_match=input_match,
        output_match=output_match,
        input_diff=input_diff,
        output_diff=output_diff,
        message=message,
    )


class GoldenTestRunner:
    """Executes golden test cases against workflow YAMLs.

    Orchestrates the replay-compare cycle: loads the workflow, installs
    mock LLM handlers from the golden case, executes the workflow with
    the golden initial state, and compares the results.

    Args:
        repository: Repository for loading golden cases.
    """

    def __init__(self, repository: GoldenCaseRepositoryPort) -> None:
        """Initializes the runner with a golden case repository.

        Args:
            repository: Repository for loading golden cases.
        """
        self._repository = repository

    def run(
        self,
        golden_case: GoldenCase,
        workflow_path: str | Path,
        registry: NodeRegistryPort | None = None,
        bundle_root: str | Path | None = None,
    ) -> GoldenTestResult:
        """Executes a golden test against the current workflow YAML.

        Replays the golden case by re-executing the workflow with LLM
        handlers replaced by mocks that return the golden output_snapshot.
        Compares the replay execution path and per-node snapshots against
        the golden reference.

        Args:
            golden_case: The reference golden case to test against.
            workflow_path: Path to the current workflow YAML.
            registry: Custom registry for non-LLM handlers. If None,
                an empty registry is used (only works if the workflow
                has only LLM handlers).
            bundle_root: Optional bundle root for prompt_ref resolution.

        Returns:
            GoldenTestResult with per-node comparison details.
        """
        from yagra import Yagra  # noqa: PLC0415

        workflow_path = Path(workflow_path)

        if registry is None:
            from yagra.adapters.outbound import InMemoryNodeRegistry  # noqa: PLC0415

            registry = InMemoryNodeRegistry()

        golden_registry = build_golden_registry(golden_case, registry)

        yagra = Yagra.from_workflow(
            workflow_path=workflow_path,
            registry=golden_registry,
            bundle_root=bundle_root,
            observability=True,
        )

        yagra.invoke(
            state=golden_case.initial_state,
            trace=False,
        )

        collector = yagra._trace_collector  # noqa: SLF001
        assert collector is not None, "observability=True should set trace_collector"
        actual_trace = collector.build_trace(
            started_at=datetime.now(tz=UTC),
            ended_at=datetime.now(tz=UTC),
            total_duration_ms=0.0,
        )

        actual_path = [n.node_id for n in actual_trace.nodes]
        actual_snapshots: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {
            n.node_id: (dict(n.input_snapshot), dict(n.output_snapshot)) for n in actual_trace.nodes
        }

        execution_path_match = actual_path == golden_case.execution_path

        node_results = _compare_all_nodes(
            golden_case=golden_case,
            actual_path=actual_path,
            actual_snapshots=actual_snapshots,
        )

        all_passed = execution_path_match and all(
            r.status in ("pass", "skip") for r in node_results
        )

        summary = _build_summary(
            golden_case.case_name,
            all_passed,
            execution_path_match,
            node_results,
        )

        return GoldenTestResult(
            case_name=golden_case.case_name,
            workflow_name=golden_case.workflow_name,
            passed=all_passed,
            executed_at=datetime.now(tz=UTC),
            execution_path_match=execution_path_match,
            expected_path=golden_case.execution_path,
            actual_path=actual_path,
            node_results=node_results,
            summary=summary,
        )

    def run_all(
        self,
        workflow_name: str,
        workflow_path: str | Path,
        registry: NodeRegistryPort | None = None,
        bundle_root: str | Path | None = None,
    ) -> list[GoldenTestResult]:
        """Runs all golden cases for a workflow.

        Args:
            workflow_name: Name of the workflow to test.
            workflow_path: Path to the current workflow YAML.
            registry: Custom registry for non-LLM handlers.
            bundle_root: Optional bundle root for prompt_ref resolution.

        Returns:
            List of GoldenTestResult, one per golden case.
        """
        cases = self._repository.list(workflow_name)
        return [
            self.run(
                golden_case=case,
                workflow_path=workflow_path,
                registry=registry,
                bundle_root=bundle_root,
            )
            for case in cases
        ]


def _resolve_strategy(strategy: ComparisonStrategy, is_llm: bool) -> ComparisonStrategy:
    """Resolves AUTO strategy to its concrete form.

    Args:
        strategy: The declared comparison strategy.
        is_llm: Whether the node is an LLM handler.

    Returns:
        Resolved strategy (never AUTO).
    """
    if strategy == ComparisonStrategy.AUTO:
        return ComparisonStrategy.STRUCTURAL if is_llm else ComparisonStrategy.EXACT
    return strategy


def _compare_all_nodes(
    golden_case: GoldenCase,
    actual_path: list[str],
    actual_snapshots: dict[str, tuple[dict[str, Any], dict[str, Any]]],
) -> list[NodeComparisonResult]:
    """Compares all nodes between golden case and replay.

    Handles three cases:
    - Expected and executed: full comparison
    - Expected but missing: marked as 'missing'
    - Unexpected (not in golden): marked as 'unexpected'

    Args:
        golden_case: The golden reference case.
        actual_path: Ordered list of executed node_ids from replay.
        actual_snapshots: Map of node_id to (input_snapshot, output_snapshot).

    Returns:
        List of NodeComparisonResult in execution order.
    """
    results: list[NodeComparisonResult] = []
    expected_ids = set(golden_case.execution_path)
    actual_ids = set(actual_path)

    # Compare nodes in golden execution order
    for node_id in golden_case.execution_path:
        snapshot = golden_case.node_snapshots[node_id]

        if node_id not in actual_ids:
            results.append(
                NodeComparisonResult(
                    node_id=node_id,
                    status="missing",
                    strategy_used=_resolve_strategy(
                        snapshot.comparison_strategy, snapshot.is_llm_handler
                    ),
                    message=f"Node '{node_id}' expected but not executed.",
                )
            )
            continue

        actual_input, actual_output = actual_snapshots[node_id]
        results.append(compare_node(snapshot, actual_input, actual_output))

    # Unexpected nodes (executed but not in golden case)
    for node_id in actual_path:
        if node_id not in expected_ids:
            results.append(
                NodeComparisonResult(
                    node_id=node_id,
                    status="unexpected",
                    strategy_used=ComparisonStrategy.EXACT,
                    message=f"Node '{node_id}' executed but not expected.",
                )
            )

    return results


def _build_comparison_message(
    node_id: str,
    passed: bool,
    input_match: bool,
    output_match: bool,
) -> str:
    """Builds a human-readable comparison message.

    Args:
        node_id: Node identifier.
        passed: Whether the overall comparison passed.
        input_match: Whether inputs matched.
        output_match: Whether outputs matched.

    Returns:
        Descriptive message string.
    """
    if passed:
        return f"Node '{node_id}' passed."

    mismatches: list[str] = []
    if not input_match:
        mismatches.append("input")
    if not output_match:
        mismatches.append("output")
    return f"Node '{node_id}' failed: {' and '.join(mismatches)} mismatch."


def _build_summary(
    case_name: str,
    passed: bool,
    path_match: bool,
    node_results: list[NodeComparisonResult],
) -> str:
    """Builds a human-readable test summary.

    Args:
        case_name: Name of the golden test case.
        passed: Overall pass/fail status.
        path_match: Whether execution paths matched.
        node_results: Per-node comparison results.

    Returns:
        Summary string.
    """
    total = len(node_results)
    passed_count = sum(1 for r in node_results if r.status == "pass")
    failed_count = sum(1 for r in node_results if r.status == "fail")
    skipped_count = sum(1 for r in node_results if r.status == "skip")
    missing_count = sum(1 for r in node_results if r.status == "missing")
    unexpected_count = sum(1 for r in node_results if r.status == "unexpected")

    status = "PASSED" if passed else "FAILED"
    parts = [f"Golden test '{case_name}': {status}"]

    if not path_match:
        parts.append("Execution path mismatch.")

    parts.append(
        f"Nodes: {total} total, {passed_count} passed, {failed_count} failed, "
        f"{skipped_count} skipped, {missing_count} missing, {unexpected_count} unexpected."
    )

    return " ".join(parts)
