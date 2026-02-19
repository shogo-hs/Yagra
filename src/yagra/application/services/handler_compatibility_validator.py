"""Validates compatibility between handler types and edge configurations."""

from __future__ import annotations

from dataclasses import dataclass

from yagra.domain.entities import GraphSpec

type Location = tuple[str | int, ...]

# Built-in handlers that produce structured output and do NOT write __next__
# automatically. Using these as a conditional branch source is an error unless
# the workflow author explicitly writes __next__ in a downstream custom handler.
_STRUCTURED_OUTPUT_HANDLERS = frozenset({"structured_llm", "streaming_llm"})


@dataclass(frozen=True, slots=True)
class HandlerCompatibilityIssue:
    """A single issue detected during handler compatibility validation."""

    message: str
    location: Location
    context: dict[str, object] | None = None


def collect_handler_compatibility_issues(spec: GraphSpec) -> list[HandlerCompatibilityIssue]:
    """Detects incompatibilities between handler types and edge configurations.

    Currently checks:
    - A node using a built-in structured-output handler (``structured_llm``,
      ``streaming_llm``) is the source of one or more conditional edges.
      These handlers write their result to ``output_key`` (default ``"output"``)
      but never write ``__next__``, so the conditional branch can never be
      satisfied at runtime.

    Args:
        spec: Workflow definition to validate.

    Returns:
        List of detected issues. Empty list if no issues found.
    """
    issues: list[HandlerCompatibilityIssue] = []

    # Build a map: node_id → node_index (for location reporting)
    node_index_by_id: dict[str, int] = {node.id: i for i, node in enumerate(spec.nodes)}

    # Collect sources that have at least one conditional edge
    conditional_sources: set[str] = {
        edge.source for edge in spec.edges if edge.condition is not None
    }

    for node_id in conditional_sources:
        node_index = node_index_by_id.get(node_id)
        if node_index is None:
            continue  # undefined node — already caught by structure validation

        node = spec.nodes[node_index]
        if node.handler not in _STRUCTURED_OUTPUT_HANDLERS:
            continue

        output_key = node.params.get("output_key", "output")
        issues.append(
            HandlerCompatibilityIssue(
                message=(
                    f"node '{node_id}' uses handler '{node.handler}' which writes to "
                    f"'{output_key}' but never writes '__next__'. "
                    f"Conditional edges from this node can never be satisfied. "
                    f"Use a 'custom' handler that sets state['__next__'] to route execution."
                ),
                location=("nodes", node_index, "handler"),
                context={
                    "node_id": node_id,
                    "handler": node.handler,
                    "output_key": output_key,
                    "suggestion": (
                        "Replace this node's handler with a custom handler that sets "
                        "state['__next__'] = '<condition_label>', or restructure the "
                        "workflow so the branching node is a separate custom handler."
                    ),
                },
            )
        )

    return issues
