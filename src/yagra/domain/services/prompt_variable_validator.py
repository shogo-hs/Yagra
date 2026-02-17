"""プロンプトテンプレート変数と前ノード output_key の整合性検証を提供する。"""

from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass
from typing import Any

from yagra.domain.entities.graph_schema import GraphSpec

type Location = tuple[str | int, ...]

_LLM_HANDLERS = frozenset({"llm", "streaming_llm", "structured_llm"})


@dataclass(frozen=True, slots=True)
class PromptVariableIssue:
    """プロンプト変数整合性検証で検知した単一問題。"""

    message: str
    location: Location


def collect_prompt_variable_issues(spec: GraphSpec) -> list[PromptVariableIssue]:
    """全ノードのプロンプト変数と到達可能な state キーを照合する。

    あるノードのプロンプトテンプレートが要求する変数（例: ``{aaa}``）が、
    そのノードに到達しうる **全パス** で state に存在することを保証する。
    いずれか1つのパスでも欠落していればエラーとして報告する。

    バリデーション対象は組み込み LLM ハンドラー（``llm``, ``streaming_llm``,
    ``structured_llm``）のみ。カスタムハンドラーは output_key の仕様が不明な
    ため対象外とする。

    初期 state キーは ``spec.params`` のキーとして宣言された値を使用する。
    invoke 時に外部から渡すキーは ``params`` セクションで宣言すること。

    Args:
        spec: 検証対象の workflow 定義（``prompt`` フィールドは参照解決済みのもの）。

    Returns:
        検知した問題一覧。問題がなければ空リスト。
    """
    node_index_by_id = {node.id: i for i, node in enumerate(spec.nodes)}

    # エッジから predecessor リストを構築
    predecessors: dict[str, list[str]] = {node.id: [] for node in spec.nodes}
    for edge in spec.edges:
        if edge.target in predecessors:
            predecessors[edge.target].append(edge.source)

    # トポロジカルソート（Kahn's algorithm）
    # 循環がある場合はソートが完了せずスキップ
    in_degree = {node.id: len(predecessors[node.id]) for node in spec.nodes}
    queue: deque[str] = deque()
    for node_id, degree in in_degree.items():
        if degree == 0:
            queue.append(node_id)

    topo_order: list[str] = []
    while queue:
        node_id = queue.popleft()
        topo_order.append(node_id)
        for edge in spec.edges:
            if edge.source == node_id:
                if edge.target not in in_degree:
                    # 未定義ノードへのエッジ（構造エラー）→ スキップ
                    continue
                in_degree[edge.target] -= 1
                if in_degree[edge.target] == 0:
                    queue.append(edge.target)

    if len(topo_order) != len(spec.nodes):
        # 循環グラフ: このバリデーションはスキップ（構造エラーは別チェックで検出）
        return []

    # 各ノード実行「後」の guaranteed_keys を計算
    # guaranteed_keys[node_id] = そのノード実行後に全パスで保証されるキーのセット
    initial_keys: frozenset[str] = frozenset(spec.params.keys())
    guaranteed_after: dict[str, frozenset[str]] = {}

    issues: list[PromptVariableIssue] = []

    for node_id in topo_order:
        node_idx = node_index_by_id[node_id]
        node = spec.nodes[node_idx]

        # このノード実行前に保証されているキーを計算
        preds = predecessors[node_id]
        if not preds:
            # 開始ノード: 初期 state キーのみ
            keys_before = initial_keys
        else:
            # 全 predecessors の guaranteed_after の積集合（intersection）
            keys_before = guaranteed_after[preds[0]]
            for pred_id in preds[1:]:
                keys_before = keys_before & guaranteed_after[pred_id]

        # start_at ノードは invoke 時の外部入力を直接受け取るため変数チェックを除外
        is_start_node = node_id == spec.start_at

        # LLM ハンドラーのみ変数チェック（start_at ノードは除外）
        if node.handler in _LLM_HANDLERS and not is_start_node:
            required_vars = _extract_required_vars(node.params)
            for var in required_vars:
                if var not in keys_before:
                    issues.append(
                        PromptVariableIssue(
                            message=(
                                f"Variable '{{{var}}}' referenced in node '{node_id}' prompt"
                                f" is not guaranteed on all paths leading to this node."
                                f" Declare it in workflow params or ensure an upstream node"
                                f" produces it via output_key."
                            ),
                            location=("nodes", node_idx, "params", "prompt", "user"),
                        )
                    )

        # このノード実行後の guaranteed_keys を計算
        output_key = _get_output_key(node.params)
        guaranteed_after[node_id] = keys_before | {output_key}

    return issues


def _extract_required_vars(params: dict[str, Any]) -> list[str]:
    """ノード params からプロンプトが要求する変数名リストを返す。

    ``input_keys`` が明示指定されていればそれを優先し、
    未指定の場合はユーザープロンプトテンプレートから ``{variable}`` を自動抽出する。
    ハンドラーと同一のロジックを使用する。

    Args:
        params: ノードの params 辞書。

    Returns:
        要求する変数名のリスト。
    """
    explicit_keys = params.get("input_keys")
    if explicit_keys is not None:
        if isinstance(explicit_keys, list):
            return [str(k) for k in explicit_keys]
        return []

    prompt = params.get("prompt")
    if not isinstance(prompt, dict):
        return []
    user_template = prompt.get("user", "")
    if not isinstance(user_template, str):
        return []
    return re.findall(r"\{(\w+)\}", user_template)


def _get_output_key(params: dict[str, Any]) -> str:
    """ノード params から output_key を返す。未指定時はデフォルト ``"output"``。

    Args:
        params: ノードの params 辞書。

    Returns:
        output_key 文字列。
    """
    key = params.get("output_key", "output")
    return str(key) if key else "output"
