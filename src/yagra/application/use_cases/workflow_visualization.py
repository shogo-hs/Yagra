"""Generates read-only HTML for workflow visualization."""

from __future__ import annotations

import html
import json
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from os import PathLike
from pathlib import Path

from yagra.application.use_cases.workflow_validation_reporter import (
    WorkflowValidationFailedError,
    format_validation_report,
    load_validated_graph_spec,
)
from yagra.domain.entities.graph_schema import GraphSpec, NodeSpec
from yagra.domain.services.prompt_variable_validator import (
    _extract_required_vars,
    _get_output_key,
)


@dataclass(frozen=True, slots=True)
class WorkflowNodeView:
    """Node information displayed in the visualization screen."""

    id: str
    handler: str
    params_json: str
    input_vars: tuple[str, ...]
    output_vars: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class WorkflowEdgeView:
    """Edge information displayed in the visualization screen."""

    source: str
    target: str
    condition: str | None
    is_fan_out: bool = False


@dataclass(frozen=True, slots=True)
class WorkflowVisualizationView:
    """Display model for the visualization screen."""

    title: str
    workflow_path: str
    version: str
    start_at: str
    end_at: tuple[str, ...]
    nodes: tuple[WorkflowNodeView, ...]
    edges: tuple[WorkflowEdgeView, ...]


def render_workflow_visualization_html(
    workflow_path: str | PathLike[str],
    bundle_root: str | PathLike[str] | None = None,
    title: str | None = None,
) -> str:
    """Generates read-only HTML that visualizes a workflow.

    Args:
        workflow_path: Path to the workflow YAML to visualize.
        bundle_root: Base directory for split reference resolution.
        title: HTML title. Defaults to the workflow filename if not specified.

    Returns:
        HTML string for visualization.

    Raises:
        ValueError: If workflow validation fails.
    """
    try:
        view = build_workflow_visualization_view(
            workflow_path=workflow_path,
            bundle_root=bundle_root,
            title=title,
        )
    except WorkflowValidationFailedError as exc:
        raise ValueError(format_validation_report(exc.report)) from exc
    return _render_html(view)


def _has_prompt(params: dict[str, object]) -> bool:
    """Returns whether prompt (dict) or prompt_ref (str) is present in the parameters.

    Args:
        params: Node parameter dictionary.

    Returns:
        True if a prompt definition exists.
    """
    return isinstance(params.get("prompt"), dict) or isinstance(params.get("prompt_ref"), str)


def _has_explicit_output_key(params: dict[str, object]) -> bool:
    """Returns whether output_key is explicitly specified in the parameters.

    Args:
        params: Node parameter dictionary.

    Returns:
        True if output_key is explicitly specified.
    """
    return "output_key" in params


def _build_node_view(
    node: NodeSpec,
    cond_sources: frozenset[str],
    spec: GraphSpec,
) -> WorkflowNodeView:
    """Builds the IN/OUT badges for a node based on its parameters.

    IN: Extracts template variables if prompt (dict) or prompt_ref (str) is present.
    OUT: Displays the value of output_key if explicitly specified.
         Appends ``__next__`` for source nodes of conditional edges.

    Args:
        node: NodeSpec within the GraphSpec.
        cond_sources: Set of source node IDs for conditional edges.
        spec: GraphSpec (reserved for future use).

    Returns:
        Node display model for visualization.
    """
    input_vars = tuple(_extract_required_vars(node.params)) if _has_prompt(node.params) else ()

    out_parts: list[str] = []
    if _has_explicit_output_key(node.params):
        out_parts.append(_get_output_key(node.params))
    if node.id in cond_sources:
        out_parts.append("__next__")
    output_vars = tuple(out_parts)

    return WorkflowNodeView(
        id=node.id,
        handler=node.handler,
        params_json=json.dumps(node.params, ensure_ascii=False, indent=2, sort_keys=True),
        input_vars=input_vars,
        output_vars=output_vars,
    )


def build_workflow_visualization_view(
    workflow_path: str | PathLike[str],
    bundle_root: str | PathLike[str] | None = None,
    title: str | None = None,
) -> WorkflowVisualizationView:
    """Builds a visualization display model from a workflow.

    Args:
        workflow_path: Path to the workflow YAML to visualize.
        bundle_root: Base directory for split reference resolution.
        title: Screen title. Defaults to the workflow filename if not specified.

    Returns:
        Visualization display model.
    """
    workflow_abspath = Path(workflow_path).expanduser().resolve()
    spec = load_validated_graph_spec(workflow_path=workflow_abspath, bundle_root=bundle_root)
    resolved_title = title if title is not None else workflow_abspath.name

    cond_sources = frozenset(e.source for e in spec.edges if e.condition)

    nodes = tuple(_build_node_view(node, cond_sources, spec) for node in spec.nodes)
    edges = tuple(
        WorkflowEdgeView(
            source=edge.source,
            target=edge.target,
            condition=edge.condition,
            is_fan_out=edge.fan_out is not None,
        )
        for edge in spec.edges
    )

    return WorkflowVisualizationView(
        title=resolved_title,
        workflow_path=str(workflow_abspath),
        version=spec.version,
        start_at=spec.start_at,
        end_at=tuple(spec.end_at),
        nodes=nodes,
        edges=edges,
    )


def _render_html(view: WorkflowVisualizationView) -> str:
    """Converts the visualization display model to HTML."""
    mermaid_graph = _build_mermaid_graph(view)
    mermaid_bundle = _load_mermaid_bundle_source()
    node_cards = "\n".join(_render_node_card(node) for node in view.nodes)
    edge_rows = "\n".join(_render_edge_row(edge) for edge in view.edges)

    return f"""<!doctype html>
<html lang=\"ja\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>{html.escape(view.title)} - Yagra Workflow Viewer</title>
  <style>
    :root {{
      --bg: #f6f8fb;
      --panel: #ffffff;
      --line: #dbe3ef;
      --text: #1c2430;
      --muted: #5f6d82;
      --accent: #0b74de;
      --accent-soft: #e6f1fd;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: var(--bg); color: var(--text); font-family: "Noto Sans JP", "Hiragino Kaku Gothic ProN", sans-serif; }}
    .page {{ max-width: 1280px; margin: 0 auto; padding: 20px; }}
    .header {{ background: linear-gradient(140deg, #ffffff 10%, #edf4ff 100%); border: 1px solid var(--line); border-radius: 14px; padding: 20px; margin-bottom: 16px; }}
    .tag {{ display: inline-block; background: var(--accent-soft); color: var(--accent); padding: 4px 10px; border-radius: 999px; font-size: 12px; font-weight: 700; letter-spacing: .02em; }}
    h1 {{ margin: 10px 0 8px; font-size: clamp(22px, 3vw, 30px); }}
    .meta {{ color: var(--muted); font-size: 13px; }}
    .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; margin-top: 14px; }}
    .summary-card {{ background: var(--panel); border: 1px solid var(--line); border-radius: 10px; padding: 10px 12px; }}
    .summary-label {{ color: var(--muted); font-size: 12px; }}
    .summary-value {{ margin-top: 4px; font-weight: 700; }}
    .layout {{ display: grid; grid-template-columns: 1.2fr .8fr; gap: 16px; align-items: start; }}
    .panel {{ background: var(--panel); border: 1px solid var(--line); border-radius: 14px; padding: 14px; }}
    .panel h2 {{ margin: 0 0 10px; font-size: 18px; }}
    .mermaid-wrap {{ overflow-x: auto; border: 1px dashed var(--line); border-radius: 10px; padding: 8px; background: #fcfdff; }}
    .node-card {{ border: 1px solid var(--line); border-radius: 10px; padding: 10px; margin-bottom: 10px; }}
    .node-title {{ margin: 0 0 6px; font-weight: 700; }}
    .node-sub {{ color: var(--muted); font-size: 12px; margin-bottom: 8px; }}
    pre {{ margin: 0; padding: 10px; border-radius: 8px; background: #0f1722; color: #e5edf9; font-size: 12px; line-height: 1.45; overflow-x: auto; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th, td {{ border-bottom: 1px solid var(--line); text-align: left; padding: 8px 6px; }}
    th {{ color: var(--muted); font-weight: 700; }}
    .cond {{ color: var(--accent); font-weight: 700; }}
    .node-vars-section {{ display: flex; align-items: flex-start; flex-wrap: wrap; gap: 3px; margin-bottom: 8px; max-width: 100%; }}
    .node-vars-label {{ font-size: 10px; font-weight: 700; letter-spacing: .06em; color: var(--muted); min-width: 24px; flex-shrink: 0; padding-top: 3px; }}
    .var-pill {{ display: inline-flex; align-items: center; border-radius: 999px; font-size: 11px; font-weight: 700; line-height: 1; padding: 2px 7px; border: 1px solid transparent; max-width: 160px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    .var-pill-in {{ background: #e8f1ff; color: #0a4a92; border-color: #afc9ec; }}
    .var-pill-out {{ background: #e8f5ee; color: #0a6e3a; border-color: #8fcdb0; }}
    @media (max-width: 980px) {{
      .layout {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div class=\"page\">
    <section class=\"header\">
      <span class=\"tag\">Read Only</span>
      <h1>{html.escape(view.title)}</h1>
      <div class=\"meta\">{html.escape(view.workflow_path)}</div>
      <div class=\"summary\">
        <div class=\"summary-card\"><div class=\"summary-label\">Version</div><div class=\"summary-value\">{html.escape(view.version)}</div></div>
        <div class=\"summary-card\"><div class=\"summary-label\">Start</div><div class=\"summary-value\">{html.escape(view.start_at)}</div></div>
        <div class=\"summary-card\"><div class=\"summary-label\">End</div><div class=\"summary-value\">{html.escape(", ".join(view.end_at))}</div></div>
        <div class=\"summary-card\"><div class=\"summary-label\">Nodes / Edges</div><div class=\"summary-value\">{len(view.nodes)} / {len(view.edges)}</div></div>
      </div>
    </section>

    <section class=\"layout\">
      <article class=\"panel\">
        <h2>Graph</h2>
        <div class=\"mermaid-wrap\">
          <div class=\"mermaid\">{html.escape(mermaid_graph)}</div>
        </div>
        <h2 style=\"margin-top: 14px;\">Edges</h2>
        <table>
          <thead><tr><th>Source</th><th>Target</th><th>Condition</th></tr></thead>
          <tbody>{edge_rows}</tbody>
        </table>
      </article>

      <aside class=\"panel\">
        <h2>Nodes</h2>
        {node_cards}
      </aside>
    </section>
  </div>
  <script>
{mermaid_bundle}
  </script>
  <script>
    const mermaidApi = window.mermaid
      || (window.__esbuild_esm_mermaid_nm && window.__esbuild_esm_mermaid_nm.mermaid);
    if (mermaidApi) {{
      mermaidApi.initialize({{ startOnLoad: true, securityLevel: "loose" }});
    }}
  </script>
</body>
</html>
"""


@lru_cache(maxsize=1)
def _load_mermaid_bundle_source() -> str:
    """Loads the bundled Mermaid bundle."""
    bundle = resources.files("yagra.web_assets").joinpath("vendor/mermaid/11.12.2/mermaid.min.js")
    return bundle.read_text(encoding="utf-8").replace("</script>", "<\\/script>")


def _build_mermaid_graph(view: WorkflowVisualizationView) -> str:
    """Generates a graph string in Mermaid format."""
    lines = ["flowchart LR"]
    for node in view.nodes:
        safe_id = _safe_mermaid_id(node.id)
        label = node.id.replace('"', '\\"')
        lines.append(f'  {safe_id}["{label}"]')

    for edge in view.edges:
        source = _safe_mermaid_id(edge.source)
        target = _safe_mermaid_id(edge.target)
        if edge.is_fan_out:
            lines.append(f'  {source} -- "fan-out" --> {target}')
        elif edge.condition is None:
            lines.append(f"  {source} --> {target}")
        else:
            condition = edge.condition.replace('"', '\\"')
            lines.append(f'  {source} -- "{condition}" --> {target}')

    return "\n".join(lines)


def _safe_mermaid_id(node_id: str) -> str:
    """Converts a node ID to a safe identifier for use in Mermaid."""
    normalized = [ch if ch.isalnum() else "_" for ch in node_id]
    if not normalized:
        return "node"
    candidate = "".join(normalized)
    if candidate[0].isdigit():
        return f"n_{candidate}"
    return candidate


def _render_node_card(node: WorkflowNodeView) -> str:
    """Converts node detail cards to HTML."""
    in_html = ""
    if node.input_vars:
        pills = "".join(
            f'<span class="var-pill var-pill-in">{html.escape(v)}</span>' for v in node.input_vars
        )
        in_html = (
            f'<div class="node-vars-section"><span class="node-vars-label">IN</span>{pills}</div>'
        )
    out_html = ""
    if node.output_vars:
        out_pills = "".join(
            f'<span class="var-pill var-pill-out">{html.escape(v)}</span>' for v in node.output_vars
        )
        out_html = (
            f'<div class="node-vars-section"><span class="node-vars-label">OUT</span>'
            f"{out_pills}</div>"
        )
    return f"""
    <section class=\"node-card\">
      <div class=\"node-title\">{html.escape(node.id)}</div>
      <div class=\"node-sub\">handler: <code>{html.escape(node.handler)}</code></div>
      {in_html}{out_html}<pre>{html.escape(node.params_json)}</pre>
    </section>
    """


def _render_edge_row(edge: WorkflowEdgeView) -> str:
    """Converts edge rows to HTML."""
    if edge.is_fan_out:
        condition = "fan-out"
        cond_class = ' class="cond"'
    elif edge.condition is None:
        condition = "-"
        cond_class = ""
    else:
        condition = html.escape(edge.condition)
        cond_class = ' class="cond"'
    return (
        "<tr>"
        f"<td>{html.escape(edge.source)}</td>"
        f"<td>{html.escape(edge.target)}</td>"
        f"<td{cond_class}>{condition}</td>"
        "</tr>"
    )
