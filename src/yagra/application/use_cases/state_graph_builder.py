"""Builds a LangGraph StateGraph from a GraphSpec."""

from __future__ import annotations

import operator
import threading
import time
from collections.abc import Hashable, Mapping
from copy import deepcopy
from os import PathLike
from pathlib import Path
from typing import Annotated, Any, TypedDict, cast

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Send

from yagra.application.use_cases.workflow_loader import load_graph_spec_from_workflow
from yagra.domain.entities import GraphSpec
from yagra.domain.entities.graph_schema import NodeSpec, RetrySpec, StateFieldSpec
from yagra.ports.outbound import NodeRegistryPort
from yagra.ports.outbound.node_registry import NodeHandler

# Mapping from YAML type name to Python type
_PYTHON_TYPE_MAP: dict[str, type] = {
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "list": list,
    "dict": dict,
}


class GraphBuildError(ValueError):
    """Exception raised when StateGraph construction fails."""


class _FanOutWithTarget:
    """Internal holder combining FanOutSpec data with the target node ID."""

    __slots__ = ("target", "items_key", "item_key")

    def __init__(self, target: str, items_key: str, item_key: str) -> None:
        self.target = target
        self.items_key = items_key
        self.item_key = item_key


def build_state_schema_type(state_schema: dict[str, StateFieldSpec]) -> type:
    """Builds a TypedDict class from a state_schema definition.

    Converts the YAML state_schema into a LangGraph-compatible TypedDict.
    Fields with type 'messages' get the add_messages reducer via Annotated,
    enabling automatic appending of chat messages instead of overwriting.
    Fields with 'reducer: add' get Annotated[list, operator.add], enabling
    fan-in from parallel nodes (Send API / fan-out patterns).

    If state_schema is empty, returns dict (legacy behavior).

    Args:
        state_schema: Mapping of field name to StateFieldSpec from GraphSpec.

    Returns:
        A TypedDict class for use as LangGraph state_schema, or dict if empty.

    Raises:
        GraphBuildError: If an unsupported field type is encountered.
    """
    if not state_schema:
        return dict

    annotations: dict[str, Any] = {}

    for field_name, field_spec in state_schema.items():
        field_type = field_spec.type
        if field_type == "messages":
            # Annotated[list, add_messages] → LangGraph applies add_messages reducer
            annotations[field_name] = Annotated[list, add_messages]
        elif field_spec.reducer == "add":
            # Annotated[list, operator.add] → enables fan-in from parallel Send nodes
            annotations[field_name] = Annotated[list, operator.add]
        else:
            py_type = _PYTHON_TYPE_MAP.get(field_type)
            if py_type is None:
                raise GraphBuildError(
                    f"unsupported state field type: '{field_type}' for key '{field_name}'"
                )
            annotations[field_name] = py_type

    # TypedDict() functional form: TypedDict("Name", {"key": type, ...})
    # This is the correct way to dynamically create a TypedDict at runtime.
    # total=False makes all fields optional (matches dict behavior).
    # mypy does not support the functional form of TypedDict well; cast is used here.
    td = TypedDict("WorkflowState", annotations, total=False)  # type: ignore[misc]
    return cast(type, td)


def build_state_graph(
    spec: GraphSpec,
    registry: NodeRegistryPort,
    state_schema: Any = None,
    checkpointer: BaseCheckpointSaver | None = None,
    workflow_path: PathLike[str] | str | None = None,
    trace_collector: Any | None = None,
) -> CompiledStateGraph:
    """Builds a compiled StateGraph from a `GraphSpec` and registry.

    If `spec.state_schema` is defined in the YAML, it is automatically used to
    build a TypedDict-based state schema. Fields with type 'messages' get the
    add_messages reducer for chat history management. Fields with 'reducer: add'
    get operator.add for fan-in from parallel Send nodes. If `state_schema`
    argument is explicitly provided, it takes precedence over `spec.state_schema`.

    If `spec.interrupt_before` / `spec.interrupt_after` are specified,
    a checkpointer is required to enable HITL (Human-in-the-Loop).
    If checkpointer is None, interrupt configuration is ignored.

    Nodes with ``handler: "subgraph"`` and ``params.workflow_ref`` are resolved
    as nested subgraph workflows. The subgraph's compiled StateGraph is embedded
    as a node in the parent graph.

    Args:
        spec: Validated workflow definition.
        registry: Registry resolving handler names to callables.
        state_schema: LangGraph state schema. If None, automatically resolved
            from spec.state_schema (TypedDict) or defaults to dict.
        checkpointer: LangGraph checkpointer. Required when using interrupts.
            If None, interrupt_before/interrupt_after are ignored.
        workflow_path: Path to the current workflow file. Required to resolve
            relative ``workflow_ref`` paths in subgraph nodes.
        trace_collector: Optional TraceCollector instance. If provided, each node runner
            is wrapped to record execution traces (G-14, G-15).

    Returns:
        Compiled `CompiledStateGraph`.

    Raises:
        GraphBuildError: If edge definitions are inconsistent or conditional routing is invalid.
    """
    # Resolve state_schema: explicit arg > YAML spec > dict fallback
    if state_schema is None:
        state_schema = build_state_schema_type(spec.state_schema)

    state_graph = StateGraph(state_schema)

    state_graph.set_entry_point(spec.start_at)

    conditional_by_source, unconditional_by_source, fanout_by_source = _split_edges(spec)
    _validate_edge_source_conflicts(conditional_by_source, unconditional_by_source)
    _validate_fanout_conflicts(fanout_by_source, conditional_by_source, unconditional_by_source)

    cond_source_ids = frozenset(conditional_by_source)

    for node in spec.nodes:
        if node.handler == "subgraph":
            compiled_subgraph = _build_subgraph_node(
                node=node,
                registry=registry,
                checkpointer=checkpointer,
                parent_workflow_path=workflow_path,
            )
            state_graph.add_node(node.id, compiled_subgraph)
        else:
            handler = registry.resolve_for_node(node.handler, node.id)
            node_runner = _build_node_runner(
                handler=handler,
                node_params=node.params,
                is_cond_source=node.id in cond_source_ids,
                retry_spec=node.retry,
                timeout_seconds=node.timeout_seconds,
                fallback_node_id=node.fallback,
            )
            if trace_collector is not None:
                node_runner = trace_collector.wrap_node(
                    node_id=node.id,
                    handler=node_runner,
                    handler_name=node.handler,
                )
            state_graph.add_node(node.id, node_runner)

    # Collect node IDs that have fallback configured
    fallback_node_ids = frozenset(node.id for node in spec.nodes if node.fallback is not None)

    for source, targets in unconditional_by_source.items():
        if source in fallback_node_ids:
            # Skip unconditional edges for fallback nodes — they will be
            # replaced by conditional edges with fallback routing below.
            continue
        for target in targets:
            state_graph.add_edge(source, target)

    for source, route_map in conditional_by_source.items():
        hashable_route_map = cast(dict[Hashable, str], dict(route_map))
        state_graph.add_conditional_edges(
            source,
            _build_router(source=source, route_map=route_map),
            hashable_route_map,
        )

    for source, fanout in fanout_by_source.items():
        state_graph.add_conditional_edges(
            source,
            _build_fan_out_dispatcher(fanout=fanout),
        )

    # Auto-generate conditional edges for nodes with fallback targets.
    # A fallback node's runner wraps the handler in try-except and sets
    # state["__next__"] = "__fallback__" on failure, routing to the fallback node.
    for node in spec.nodes:
        if node.fallback is not None and node.id not in conditional_by_source:
            # Determine the "continue" target: the original unconditional edge target(s)
            continue_targets = unconditional_by_source.get(node.id, [])
            if len(continue_targets) == 1:
                continue_target = continue_targets[0]
            else:
                # If no unconditional edges or multiple, route back to self
                # (will be handled by downstream edges)
                continue_target = node.id

            hashable_map = cast(
                dict[Hashable, str],
                {"__fallback__": node.fallback, "__continue__": continue_target},
            )
            state_graph.add_conditional_edges(
                node.id,
                _build_fallback_router(node.id),
                hashable_map,
            )

    for end_node in spec.end_at:
        state_graph.set_finish_point(end_node)

    # interrupt_before / interrupt_after are only effective when a checkpointer is provided
    interrupt_before = list(spec.interrupt_before) if checkpointer is not None else []
    interrupt_after = list(spec.interrupt_after) if checkpointer is not None else []

    return state_graph.compile(
        checkpointer=checkpointer,
        interrupt_before=interrupt_before or None,
        interrupt_after=interrupt_after or None,
    )


def build_from_workflow_path(
    workflow_path: str | PathLike[str],
    registry: NodeRegistryPort,
    bundle_root: str | PathLike[str] | None = None,
    state_schema: Any = None,
    checkpointer: BaseCheckpointSaver | None = None,
    trace_collector: Any | None = None,
) -> CompiledStateGraph:
    """Builds a `CompiledStateGraph` starting from a workflow path.

    Args:
        workflow_path: Path to the entry workflow file.
        registry: Registry resolving handler names to callables.
        bundle_root: Base directory for split references. Defaults to workflow parent directory.
        state_schema: LangGraph state schema. If None, automatically resolved
            from the workflow's state_schema definition or defaults to dict.
        checkpointer: LangGraph checkpointer. Required when using interrupts.
        trace_collector: Optional TraceCollector instance. Passed through to
            build_state_graph() to wrap node runners (G-14, G-15).

    Returns:
        Compiled `CompiledStateGraph`.
    """
    spec = load_graph_spec_from_workflow(workflow_path=workflow_path, bundle_root=bundle_root)
    return build_state_graph(
        spec=spec,
        registry=registry,
        state_schema=state_schema,
        checkpointer=checkpointer,
        workflow_path=workflow_path,
        trace_collector=trace_collector,
    )


def _split_edges(
    spec: GraphSpec,
) -> tuple[dict[str, dict[str, str]], dict[str, list[str]], dict[str, _FanOutWithTarget]]:
    """Classifies edges into conditional, normal, and fan-out transitions.

    Returns:
        Tuple of (conditional_by_source, unconditional_by_source, fanout_by_source).
        - conditional_by_source: {source: {condition_label: target}}
        - unconditional_by_source: {source: [target, ...]}
        - fanout_by_source: {source: FanOutSpec with target}
    """
    conditional_by_source: dict[str, dict[str, str]] = {}
    unconditional_by_source: dict[str, list[str]] = {}
    fanout_by_source: dict[str, _FanOutWithTarget] = {}

    for edge in spec.edges:
        if edge.fan_out is not None:
            if edge.source in fanout_by_source:
                raise GraphBuildError(
                    f"multiple fan_out edges from source '{edge.source}' are not allowed"
                )
            # Store fan_out spec alongside target info by attaching target into a copy
            # We use a simple approach: store (target, fan_out) by source
            # Use a wrapper to keep target accessible
            fanout_by_source[edge.source] = _FanOutWithTarget(
                target=edge.target,
                items_key=edge.fan_out.items_key,
                item_key=edge.fan_out.item_key,
            )
            continue

        if edge.condition is None:
            unconditional_by_source.setdefault(edge.source, []).append(edge.target)
            continue

        route_map = conditional_by_source.setdefault(edge.source, {})
        if edge.condition in route_map:
            raise GraphBuildError(
                f"duplicate conditional edge label '{edge.condition}' for source '{edge.source}'"
            )
        route_map[edge.condition] = edge.target

    return conditional_by_source, unconditional_by_source, fanout_by_source


def _validate_edge_source_conflicts(
    conditional_by_source: Mapping[str, Any],
    unconditional_by_source: Mapping[str, Any],
) -> None:
    """Verifies that conditional and normal transitions are not mixed for the same source."""
    conflict_sources = sorted(set(conditional_by_source) & set(unconditional_by_source))
    if conflict_sources:
        labels = ", ".join(conflict_sources)
        raise GraphBuildError(f"mixed conditional and normal edges are not allowed: {labels}")


def _validate_fanout_conflicts(
    fanout_by_source: Mapping[str, Any],
    conditional_by_source: Mapping[str, Any],
    unconditional_by_source: Mapping[str, Any],
) -> None:
    """Verifies that fan_out edges are not mixed with other edge types for the same source.

    Args:
        fanout_by_source: Mapping of source node ID to _FanOutWithTarget.
        conditional_by_source: Mapping of source to conditional route map.
        unconditional_by_source: Mapping of source to unconditional targets.

    Raises:
        GraphBuildError: If a source node has both fan_out and other edge types.
    """
    conflict_sources = sorted(
        set(fanout_by_source) & (set(conditional_by_source) | set(unconditional_by_source))
    )
    if conflict_sources:
        labels = ", ".join(conflict_sources)
        raise GraphBuildError(
            f"fan_out edge cannot be combined with other edge types for source: {labels}"
        )


def _build_fan_out_dispatcher(fanout: _FanOutWithTarget) -> NodeHandler:
    """Returns a conditional edge function that dispatches items via Send API.

    The returned function reads ``state[fanout.items_key]`` (expected to be a list)
    and returns a list of ``Send(fanout.target, {fanout.item_key: item})`` objects,
    enabling LangGraph's parallel fan-out (map-reduce) pattern.

    Args:
        fanout: Fan-out configuration containing target, items_key, and item_key.

    Returns:
        Callable that takes state and returns list[Send].
    """
    target = fanout.target
    items_key = fanout.items_key
    item_key = fanout.item_key

    # NOTE: _dispatch intentionally has no type annotations on state/return.
    # LangGraph calls get_type_hints() on conditional edge functions to infer schema.
    # With `from __future__ import annotations`, all annotations become strings,
    # and LangGraph cannot resolve `Send` from the string `"list[Send]"` in the
    # module's namespace. Omitting annotations avoids this forward-reference issue.
    def _dispatch(state):  # noqa: ANN001, ANN202
        items = state.get(items_key)
        if not isinstance(items, list):
            raise GraphBuildError(
                f"fan_out requires state['{items_key}'] to be a list, got {type(items).__name__}"
            )
        return [Send(target, {item_key: item}) for item in items]

    return _dispatch


def _build_subgraph_node(
    node: NodeSpec,
    registry: NodeRegistryPort,
    checkpointer: BaseCheckpointSaver | None,
    parent_workflow_path: PathLike[str] | str | None,
) -> CompiledStateGraph:
    """Builds a compiled subgraph from a node with handler='subgraph'.

    Resolves the ``workflow_ref`` parameter relative to the parent workflow path,
    loads and validates the sub-workflow YAML, and compiles it as a nested graph.

    Args:
        node: NodeSpec with handler='subgraph' and params.workflow_ref.
        registry: Handler registry shared with the parent graph.
        checkpointer: Checkpointer shared with the parent graph.
        parent_workflow_path: Path to the parent workflow file, used to resolve
            relative workflow_ref paths.

    Returns:
        Compiled subgraph as a CompiledStateGraph.

    Raises:
        GraphBuildError: If workflow_ref is missing, path cannot be resolved,
            or the sub-workflow fails to load/validate.
    """
    from yagra.application.use_cases.workflow_loader import load_graph_spec_from_workflow

    workflow_ref = node.params.get("workflow_ref")
    if not workflow_ref:
        raise GraphBuildError(
            f"node '{node.id}' with handler='subgraph' requires params.workflow_ref"
        )
    if not isinstance(workflow_ref, str):
        raise GraphBuildError(
            f"node '{node.id}': params.workflow_ref must be a string, "
            f"got {type(workflow_ref).__name__}"
        )

    # Resolve workflow_ref path
    if parent_workflow_path is not None:
        parent_path = Path(parent_workflow_path).expanduser().resolve()
        sub_workflow_path = (parent_path.parent / workflow_ref).resolve()
    else:
        sub_workflow_path = Path(workflow_ref).expanduser().resolve()

    if not sub_workflow_path.exists():
        raise GraphBuildError(
            f"node '{node.id}': subgraph workflow_ref not found: {sub_workflow_path}"
        )

    try:
        sub_spec = load_graph_spec_from_workflow(workflow_path=sub_workflow_path)
    except Exception as exc:
        raise GraphBuildError(
            f"node '{node.id}': failed to load subgraph '{workflow_ref}': {exc}"
        ) from exc

    return build_state_graph(
        spec=sub_spec,
        registry=registry,
        state_schema=None,
        checkpointer=checkpointer,
        workflow_path=sub_workflow_path,
    )


def _build_node_runner(
    handler: NodeHandler,
    node_params: Mapping[str, Any],
    is_cond_source: bool = False,
    retry_spec: RetrySpec | None = None,
    timeout_seconds: int | None = None,
    fallback_node_id: str | None = None,
) -> NodeHandler:
    """Returns a wrapper callable for node execution.

    Args:
        handler: Node handler callable.
        node_params: Node params dictionary.
        is_cond_source: Whether this node is the source of a conditional edge.
            If True and ``output_key`` is not specified, ``"__next__"`` is set automatically.
        retry_spec: Optional retry configuration from NodeSpec.
        timeout_seconds: Optional timeout in seconds from NodeSpec.
        fallback_node_id: Optional fallback node ID from NodeSpec.
    """
    frozen_params = _normalize_runtime_params(
        node_params, is_cond_source=is_cond_source, retry_spec=retry_spec
    )

    def _run(state: Mapping[str, Any]) -> dict[str, Any]:
        result = _invoke_handler(handler=handler, state=state, node_params=frozen_params)
        if not isinstance(result, Mapping):
            raise GraphBuildError("node handler must return a mapping state update")
        merged_state = dict(state)
        merged_state.update(dict(result))
        return merged_state

    runner = _run

    if timeout_seconds is not None:
        runner = _wrap_with_timeout(runner, timeout_seconds)

    if retry_spec is not None:
        runner = _wrap_with_retry(runner, retry_spec)

    if fallback_node_id is not None:
        runner = _wrap_with_fallback(runner, fallback_node_id)

    return runner


def _normalize_runtime_params(
    node_params: Mapping[str, Any],
    is_cond_source: bool = False,
    retry_spec: RetrySpec | None = None,
) -> dict[str, Any]:
    """Normalizes node params passed to the handler at execution time.

    For conditional edge source nodes where ``output_key`` is not specified,
    ``"__next__"`` is set automatically. The LLM handler writes this value to state,
    and the router reads ``state["__next__"]`` to determine the next branch.

    When ``retry_spec`` is provided, ``_retry_override`` is injected to suppress
    the handler's built-in retry logic (avoiding double retry).

    Args:
        node_params: Node params dictionary.
        is_cond_source: True if this node is the source of a conditional edge.
        retry_spec: If provided, overrides handler-level retry.
    """
    normalized = deepcopy(dict(node_params))
    normalized.pop("prompt_ref", None)
    if is_cond_source and "output_key" not in normalized:
        normalized["output_key"] = "__next__"
    if retry_spec is not None:
        normalized["_retry_override"] = 1
    return normalized


def _invoke_handler(
    handler: NodeHandler,
    state: Mapping[str, Any],
    node_params: Mapping[str, Any],
) -> Any:
    """Invokes a handler preferring the `handler(state, params)` signature."""
    try:
        return handler(dict(state), dict(node_params))
    except TypeError:
        try:
            return handler(dict(state))
        except TypeError as exc_without_params:
            raise GraphBuildError(
                "node handler invocation failed for both signatures: "
                "handler(state, params) and handler(state)"
            ) from exc_without_params


def _build_router(source: str, route_map: Mapping[str, str]) -> NodeHandler:
    """Returns a router that selects the conditional transition target from the `__next__` key."""
    allowed = sorted(route_map.keys())

    def _route(state: Mapping[str, Any]) -> str:
        label = state.get("__next__")
        if not isinstance(label, str):
            joined = ", ".join(allowed)
            raise GraphBuildError(
                f"conditional route for '{source}' requires string '__next__' in state (allowed: {joined})"
            )
        if label not in route_map:
            joined = ", ".join(allowed)
            raise GraphBuildError(
                f"unknown conditional route '{label}' for '{source}' (allowed: {joined})"
            )
        return label

    return _route


def _build_fallback_router(node_id: str) -> NodeHandler:
    """Returns a router for fallback-enabled nodes.

    Checks ``state["__next__"]`` for ``"__fallback__"`` to route to the fallback
    node, otherwise returns ``"__continue__"`` for normal downstream processing.

    Args:
        node_id: Node ID (for error messages).

    Returns:
        Router callable.
    """

    def _route(state: Mapping[str, Any]) -> str:
        label = state.get("__next__")
        if label == "__fallback__":
            return "__fallback__"
        return "__continue__"

    return _route


def _wrap_with_retry(runner: NodeHandler, retry_spec: RetrySpec) -> NodeHandler:
    """Wraps a node runner with retry logic.

    On failure, the runner is re-invoked up to ``retry_spec.max_attempts`` times
    with the configured backoff strategy.

    Args:
        runner: Node runner callable to wrap.
        retry_spec: Retry configuration.

    Returns:
        Wrapped runner with retry logic.
    """

    def _retrying_run(state: Mapping[str, Any]) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(retry_spec.max_attempts):
            try:
                return cast(dict[str, Any], runner(state))
            except Exception as exc:
                last_error = exc
                if attempt < retry_spec.max_attempts - 1:
                    if retry_spec.backoff == "exponential":
                        delay = retry_spec.base_delay_seconds * (2**attempt)
                    else:
                        delay = retry_spec.base_delay_seconds
                    time.sleep(delay)
        raise last_error  # type: ignore[misc]

    return _retrying_run


def _wrap_with_timeout(runner: NodeHandler, timeout_seconds: int) -> NodeHandler:
    """Wraps a node runner with a timeout.

    Uses a background thread to execute the runner. If execution exceeds
    ``timeout_seconds``, raises a ``TimeoutError``.

    Args:
        runner: Node runner callable to wrap.
        timeout_seconds: Maximum execution time in seconds.

    Returns:
        Wrapped runner with timeout enforcement.
    """

    def _timed_run(state: Mapping[str, Any]) -> dict[str, Any]:
        result_box: list[dict[str, Any]] = []
        error_box: list[Exception] = []

        def _target() -> None:
            try:
                result_box.append(runner(state))
            except Exception as exc:
                error_box.append(exc)

        thread = threading.Thread(target=_target, daemon=True)
        thread.start()
        thread.join(timeout=timeout_seconds)
        if thread.is_alive():
            raise TimeoutError(f"node execution timed out after {timeout_seconds} seconds")
        if error_box:
            raise error_box[0]
        return result_box[0]

    return _timed_run


def _wrap_with_fallback(runner: NodeHandler, fallback_node_id: str) -> NodeHandler:
    """Wraps a node runner with fallback routing on failure.

    On exception, sets ``state["__error__"]`` with the error message and
    ``state["__next__"]`` to ``"__fallback__"`` to route to the fallback node.

    Args:
        runner: Node runner callable to wrap.
        fallback_node_id: Target fallback node ID (for documentation; routing
            is handled by ``_build_fallback_router``).

    Returns:
        Wrapped runner with fallback logic.
    """

    def _fallback_run(state: Mapping[str, Any]) -> dict[str, Any]:
        try:
            result = cast(dict[str, Any], runner(state))
            # On success, mark for normal continuation
            result["__next__"] = "__continue__"
            return result
        except Exception as exc:
            merged = dict(state)
            merged["__error__"] = str(exc)
            merged["__next__"] = "__fallback__"
            return merged

    return _fallback_run
