"""Statically analyzes workflow YAML and returns execution information."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from yagra.domain.entities.graph_schema import GraphSpec, NodeSpec


def explain_workflow(spec: GraphSpec, workflow_dir: Path | None = None) -> dict[str, Any]:
    """Statically analyzes a GraphSpec and returns execution information.

    Analyzes the workflow without actually executing it, returning the entry point,
    exit nodes, execution paths, required handlers, and variable flow.

    Args:
        spec: GraphSpec to analyze.
        workflow_dir: Directory of the workflow file, used to resolve relative
            prompt_ref paths. If None, prompt_ref file reading is skipped.

    Returns:
        Dictionary with the following keys:
        - entry_point: start_at node name
        - exit_points: list of end_at node names
        - execution_paths: list of possible execution paths (each path is a list of node names)
        - required_handlers: deduplicated list of required handler names
        - variable_flow: map of node names to input/output variables
    """
    node_map = {node.id: node for node in spec.nodes}

    return {
        "entry_point": spec.start_at,
        "exit_points": list(spec.end_at),
        "execution_paths": _enumerate_paths(spec),
        "required_handlers": _collect_handlers(spec),
        "variable_flow": _build_variable_flow(spec, node_map, workflow_dir=workflow_dir),
    }


def _enumerate_paths(spec: GraphSpec) -> list[list[str]]:
    """Traverses the graph with DFS and enumerates possible execution paths.

    Enumerates all branch paths when conditional edges exist.
    Terminates at the first revisit when a loop is detected (to prevent infinite loops).

    Args:
        spec: GraphSpec to analyze.

    Returns:
        List of execution paths (each path is a list of node names).
    """
    end_at_set = set(spec.end_at)

    # Build source → [target] mapping
    adjacency: dict[str, list[str]] = {}
    for edge in spec.edges:
        adjacency.setdefault(edge.source, []).append(edge.target)

    paths: list[list[str]] = []

    def dfs(current: str, path: list[str], visited: set[str]) -> None:
        path = [*path, current]
        if current in end_at_set:
            paths.append(path)
            return
        next_nodes = adjacency.get(current, [])
        if not next_nodes:
            # Nodes with no outgoing edges that are not end nodes (isolated nodes) are recorded as paths
            paths.append(path)
            return
        for next_node in next_nodes:
            if next_node in visited:
                # Loop detected: terminate
                paths.append([*path, f"...(loop:{next_node})"])
                continue
            dfs(next_node, path, visited | {current})

    dfs(spec.start_at, [], set())
    return paths


def _collect_handlers(spec: GraphSpec) -> list[str]:
    """Returns deduplicated handler names used in the workflow.

    Args:
        spec: GraphSpec to analyze.

    Returns:
        Deduplicated list of handler names in order of appearance.
    """
    seen: set[str] = set()
    handlers: list[str] = []
    for node in spec.nodes:
        if node.handler not in seen:
            seen.add(node.handler)
            handlers.append(node.handler)
    return handlers


def _build_variable_flow(
    spec: GraphSpec,
    node_map: dict[str, NodeSpec],
    workflow_dir: Path | None = None,
) -> dict[str, dict[str, list[str]]]:
    """Extracts and returns input/output variables for each node.

    Input variables are extracted from {variable} patterns in prompt templates.
    Output variables are obtained from the output_key parameter, defaulting to 'output'.
    Conditional branch nodes (sources of conditional edges) have '__next__' added to their outputs.
    Fan-out source nodes have the items_key added to their outputs, and fan-out target nodes
    have the item_key added to their inputs.

    Args:
        spec: GraphSpec to analyze.
        node_map: Mapping from node ID to NodeSpec.
        workflow_dir: Directory of the workflow file, used to resolve relative
            prompt_ref paths. If None, prompt_ref file reading is skipped.

    Returns:
        Dictionary keyed by node name. Values are dicts with {"inputs": [...], "outputs": [...]}.
    """
    # Identify source nodes of conditional edges
    conditional_sources = {edge.source for edge in spec.edges if edge.condition is not None}

    # Collect fan_out edge info: source → items_key, target → item_key
    fanout_source_keys: dict[str, str] = {}
    fanout_target_keys: dict[str, str] = {}
    for edge in spec.edges:
        if edge.fan_out is not None:
            fanout_source_keys[edge.source] = edge.fan_out.items_key
            fanout_target_keys[edge.target] = edge.fan_out.item_key

    flow: dict[str, dict[str, list[str]]] = {}
    for node in spec.nodes:
        inputs = _extract_input_variables(node, workflow_dir=workflow_dir)
        outputs = _extract_output_variables(node, conditional_sources)

        # fan_out source: the node populates state[items_key]
        if node.id in fanout_source_keys:
            items_key = fanout_source_keys[node.id]
            if items_key not in outputs:
                outputs = [*outputs, items_key]

        # fan_out target: the node receives state[item_key] injected per item
        if node.id in fanout_target_keys:
            item_key = fanout_target_keys[node.id]
            if item_key not in inputs:
                inputs = [*inputs, item_key]

        flow[node.id] = {"inputs": inputs, "outputs": outputs}
    return flow


def _extract_input_variables(node: NodeSpec, workflow_dir: Path | None = None) -> list[str]:
    """Extracts input variables from a node's prompt.

    Args:
        node: NodeSpec to extract input variables from.
        workflow_dir: Directory of the workflow file, used to resolve relative
            prompt_ref paths. If None, prompt_ref file reading is skipped.

    Returns:
        List of {variable} names in the prompt template (deduplicated, in order of appearance).
    """
    params = node.params
    prompt_ref_value = params.get("prompt_ref")
    prompt = params.get("prompt") or prompt_ref_value
    if prompt is None:
        return []

    # If prompt is a string, analyze it directly
    if isinstance(prompt, str):
        # When the value came from prompt_ref, treat it as a file path
        if prompt_ref_value is not None and prompt is prompt_ref_value:
            return _extract_vars_from_prompt_ref(prompt, workflow_dir)
        return _extract_vars_from_text(prompt)

    # If prompt is a dict, analyze known text fields.
    # Handles both inline prompt dicts (content key) and resolved prompt_ref dicts
    # (system/user keys, as produced by resolve_workflow_references).
    if isinstance(prompt, dict):
        return _extract_vars_from_value(prompt)

    # If prompt is a list, analyze the content of each message
    if isinstance(prompt, list):
        vars_seen: set[str] = set()
        vars_list: list[str] = []
        for msg in prompt:
            if isinstance(msg, dict):
                content = msg.get("content", "")
                if isinstance(content, str):
                    for var in _extract_vars_from_text(content):
                        if var not in vars_seen:
                            vars_seen.add(var)
                            vars_list.append(var)
        return vars_list

    return []


def _extract_vars_from_prompt_ref(prompt_ref: str, workflow_dir: Path | None) -> list[str]:
    """Reads a prompt_ref file and extracts {variable} patterns from it.

    Supports an anchor syntax: ``path/to/file.yaml#section_name`` where
    ``#section_name`` selects a specific key from the top-level mapping.
    When no anchor is given the entire file content is searched.

    Args:
        prompt_ref: Relative (or absolute) file path, optionally with a
            ``#section`` anchor.
        workflow_dir: Base directory used to resolve relative paths.
            If None the function returns an empty list immediately.

    Returns:
        List of variable names found (deduplicated, in order of appearance).
        Returns an empty list when the file cannot be read or parsed.
    """
    if workflow_dir is None:
        return []

    # Split off optional anchor (e.g. "prompts/foo.yaml#default")
    if "#" in prompt_ref:
        file_part, section = prompt_ref.split("#", 1)
    else:
        file_part, section = prompt_ref, None

    file_path = Path(file_part)
    if not file_path.is_absolute():
        file_path = workflow_dir / file_path

    try:
        import yaml as yaml_lib

        raw = file_path.read_text(encoding="utf-8")
        data = yaml_lib.safe_load(raw)
    except Exception:
        return []

    if section is not None:
        if isinstance(data, dict):
            data = data.get(section)
        else:
            return []

    return _extract_vars_from_value(data)


def _extract_vars_from_value(value: Any) -> list[str]:
    """Recursively walks *value* and collects {variable} patterns from all strings.

    Args:
        value: Arbitrary Python value (str, dict, list, or other).

    Returns:
        Deduplicated list of variable names in order of first appearance.
    """
    seen: set[str] = set()
    result: list[str] = []

    def _walk(v: Any) -> None:
        if isinstance(v, str):
            for var in _extract_vars_from_text(v):
                if var not in seen:
                    seen.add(var)
                    result.append(var)
        elif isinstance(v, dict):
            for item in v.values():
                _walk(item)
        elif isinstance(v, list):
            for item in v:
                _walk(item)

    _walk(value)
    return result


def _extract_vars_from_text(text: str) -> list[str]:
    """Extracts {variable} patterns from text.

    Args:
        text: Text to extract variables from.

    Returns:
        List of variable names (deduplicated, in order of appearance).
    """
    seen: set[str] = set()
    result: list[str] = []
    for match in re.finditer(r"\{(\w+)\}", text):
        var = match.group(1)
        if var not in seen:
            seen.add(var)
            result.append(var)
    return result


def _extract_output_variables(node: NodeSpec, conditional_sources: set[str]) -> list[str]:
    """Extracts output variables for a node.

    Uses output_key if explicitly specified; otherwise defaults to 'output'.
    Appends '__next__' for conditional branch nodes.

    Args:
        node: NodeSpec to extract output variables from.
        conditional_sources: Set of source node IDs for conditional edges.

    Returns:
        List of output variable names.
    """
    outputs: list[str] = []
    output_key = node.params.get("output_key")
    if output_key:
        outputs.append(output_key)
    # If output_key is not specified but the handler is a builtin, 'output' is the default
    # (custom handlers are unknown, so only builtin handlers are checked)
    builtin_handlers = {"llm", "structured_llm", "streaming_llm"}
    if not output_key and node.handler in builtin_handlers:
        outputs.append("output")

    if node.id in conditional_sources:
        outputs.append("__next__")

    return outputs
