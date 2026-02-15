"""Workflow 可視化用の Read Only HTML を生成する。"""

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


@dataclass(frozen=True, slots=True)
class WorkflowNodeView:
    """可視化画面で表示するノード情報。"""

    id: str
    handler: str
    params_json: str


@dataclass(frozen=True, slots=True)
class WorkflowEdgeView:
    """可視化画面で表示するエッジ情報。"""

    source: str
    target: str
    condition: str | None


@dataclass(frozen=True, slots=True)
class WorkflowVisualizationView:
    """可視化画面の表示モデル。"""

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
    """Workflow を可視化する Read Only HTML を生成する。

    Args:
        workflow_path: 可視化対象の workflow YAML パス。
        bundle_root: 分割参照解決の基準ディレクトリ。
        title: HTML タイトル。未指定時は workflow ファイル名を使用。

    Returns:
        可視化用 HTML 文字列。

    Raises:
        ValueError: workflow 検証に失敗した場合。
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


def build_workflow_visualization_view(
    workflow_path: str | PathLike[str],
    bundle_root: str | PathLike[str] | None = None,
    title: str | None = None,
) -> WorkflowVisualizationView:
    """Workflow から可視化表示モデルを構築する。

    Args:
        workflow_path: 可視化対象の workflow YAML パス。
        bundle_root: 分割参照解決の基準ディレクトリ。
        title: 画面タイトル。未指定時は workflow ファイル名を使用。

    Returns:
        可視化表示モデル。
    """
    workflow_abspath = Path(workflow_path).expanduser().resolve()
    spec = load_validated_graph_spec(workflow_path=workflow_abspath, bundle_root=bundle_root)
    resolved_title = title if title is not None else workflow_abspath.name

    nodes = tuple(
        WorkflowNodeView(
            id=node.id,
            handler=node.handler,
            params_json=json.dumps(node.params, ensure_ascii=False, indent=2, sort_keys=True),
        )
        for node in spec.nodes
    )
    edges = tuple(
        WorkflowEdgeView(source=edge.source, target=edge.target, condition=edge.condition)
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
    """可視化表示モデルを HTML へ変換する。"""
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
    """同梱 Mermaid バンドルを読み込む。"""
    bundle = resources.files("yagra.web_assets").joinpath("vendor/mermaid/11.12.2/mermaid.min.js")
    return bundle.read_text(encoding="utf-8").replace("</script>", "<\\/script>")


def _build_mermaid_graph(view: WorkflowVisualizationView) -> str:
    """Mermaid 形式のグラフ文字列を生成する。"""
    lines = ["flowchart LR"]
    for node in view.nodes:
        safe_id = _safe_mermaid_id(node.id)
        label = node.id.replace('"', '\\"')
        lines.append(f'  {safe_id}["{label}"]')

    for edge in view.edges:
        source = _safe_mermaid_id(edge.source)
        target = _safe_mermaid_id(edge.target)
        if edge.condition is None:
            lines.append(f"  {source} --> {target}")
        else:
            condition = edge.condition.replace('"', '\\"')
            lines.append(f'  {source} -- "{condition}" --> {target}')

    return "\n".join(lines)


def _safe_mermaid_id(node_id: str) -> str:
    """Mermaid ノードIDとして安全な識別子へ変換する。"""
    normalized = [ch if ch.isalnum() else "_" for ch in node_id]
    if not normalized:
        return "node"
    candidate = "".join(normalized)
    if candidate[0].isdigit():
        return f"n_{candidate}"
    return candidate


def _render_node_card(node: WorkflowNodeView) -> str:
    """ノード詳細カードを HTML へ変換する。"""
    return f"""
    <section class=\"node-card\">
      <div class=\"node-title\">{html.escape(node.id)}</div>
      <div class=\"node-sub\">handler: <code>{html.escape(node.handler)}</code></div>
      <pre>{html.escape(node.params_json)}</pre>
    </section>
    """


def _render_edge_row(edge: WorkflowEdgeView) -> str:
    """エッジ行を HTML へ変換する。"""
    condition = "-" if edge.condition is None else html.escape(edge.condition)
    cond_class = "" if edge.condition is None else ' class="cond"'
    return (
        "<tr>"
        f"<td>{html.escape(edge.source)}</td>"
        f"<td>{html.escape(edge.target)}</td>"
        f"<td{cond_class}>{condition}</td>"
        "</tr>"
    )
