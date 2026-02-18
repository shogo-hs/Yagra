"""ワークフロー YAML を静的解析して実行情報を返す。"""

from __future__ import annotations

import re
from typing import Any

from yagra.domain.entities.graph_schema import GraphSpec, NodeSpec


def explain_workflow(spec: GraphSpec) -> dict[str, Any]:
    """GraphSpec を静的解析して実行情報を返す。

    ワークフローを実際に実行せずに解析し、エントリポイント・終了ノード・
    実行パス・必要ハンドラー・変数フローを返す。

    Args:
        spec: 解析対象の GraphSpec。

    Returns:
        以下のキーを持つ辞書:
        - entry_point: start_at ノード名
        - exit_points: end_at ノード名リスト
        - execution_paths: 可能な実行パス一覧（各パスはノード名リスト）
        - required_handlers: 必要なハンドラー名の重複なしリスト
        - variable_flow: ノード名をキーとする入出力変数マップ
    """
    node_map = {node.id: node for node in spec.nodes}

    return {
        "entry_point": spec.start_at,
        "exit_points": list(spec.end_at),
        "execution_paths": _enumerate_paths(spec),
        "required_handlers": _collect_handlers(spec),
        "variable_flow": _build_variable_flow(spec, node_map),
    }


def _enumerate_paths(spec: GraphSpec) -> list[list[str]]:
    """グラフを DFS で辿り、可能な実行パスを列挙する。

    条件分岐がある場合はすべての分岐パスを列挙する。
    ループが検出された場合は最初の再訪問で打ち切る（無限ループ防止）。

    Args:
        spec: 解析対象の GraphSpec。

    Returns:
        各実行パス（ノード名リスト）の一覧。
    """
    end_at_set = set(spec.end_at)

    # source → [target] のマッピングを構築
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
            # エッジなしで終端でないノード（孤立ノード）はそのままパスとして記録
            paths.append(path)
            return
        for next_node in next_nodes:
            if next_node in visited:
                # ループ検出: 打ち切り
                paths.append([*path, f"...(loop:{next_node})"])
                continue
            dfs(next_node, path, visited | {current})

    dfs(spec.start_at, [], set())
    return paths


def _collect_handlers(spec: GraphSpec) -> list[str]:
    """ワークフロー内で使用されているハンドラー名を重複なしで返す。

    Args:
        spec: 解析対象の GraphSpec。

    Returns:
        使用ハンドラー名の重複なしリスト（登場順）。
    """
    seen: set[str] = set()
    handlers: list[str] = []
    for node in spec.nodes:
        if node.handler not in seen:
            seen.add(node.handler)
            handlers.append(node.handler)
    return handlers


def _build_variable_flow(
    spec: GraphSpec, node_map: dict[str, NodeSpec]
) -> dict[str, dict[str, list[str]]]:
    """各ノードの入力変数・出力変数を抽出して返す。

    入力変数はプロンプトテンプレートの {変数名} から抽出する。
    出力変数は output_key パラメータから取得し、省略時は 'output' とする。
    条件分岐ノード（conditional edges の source）は '__next__' を出力変数に追加する。

    Args:
        spec: 解析対象の GraphSpec。
        node_map: ノード ID から NodeSpec へのマッピング。

    Returns:
        ノード名をキーとする辞書。値は {"inputs": [...], "outputs": [...]} の辞書。
    """
    # conditional edges の source ノードを特定
    conditional_sources = {edge.source for edge in spec.edges if edge.condition is not None}

    flow: dict[str, dict[str, list[str]]] = {}
    for node in spec.nodes:
        inputs = _extract_input_variables(node)
        outputs = _extract_output_variables(node, conditional_sources)
        flow[node.id] = {"inputs": inputs, "outputs": outputs}
    return flow


def _extract_input_variables(node: NodeSpec) -> list[str]:
    """ノードのプロンプトから入力変数を抽出する。

    Args:
        node: 入力変数を抽出する NodeSpec。

    Returns:
        プロンプトテンプレート内の {変数名} リスト（重複なし、登場順）。
    """
    params = node.params
    prompt = params.get("prompt") or params.get("prompt_ref")
    if prompt is None:
        return []

    # prompt が文字列の場合はそのまま解析
    if isinstance(prompt, str):
        return _extract_vars_from_text(prompt)

    # prompt が dict の場合は content フィールドを解析
    if isinstance(prompt, dict):
        content = prompt.get("content", "")
        if isinstance(content, str):
            return _extract_vars_from_text(content)
        return []

    # prompt が list の場合は各メッセージの content を解析
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

    # prompt_ref はファイルパスのため静的解析では変数抽出不可
    return []


def _extract_vars_from_text(text: str) -> list[str]:
    """テキスト内の {変数名} パターンを抽出する。

    Args:
        text: 変数を抽出するテキスト。

    Returns:
        変数名リスト（重複なし、登場順）。
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
    """ノードの出力変数を抽出する。

    output_key が明示指定されていればそれを使い、なければ 'output' を使う。
    条件分岐ノードの場合は '__next__' を追加する。

    Args:
        node: 出力変数を抽出する NodeSpec。
        conditional_sources: conditional edge の source ノード ID セット。

    Returns:
        出力変数名リスト。
    """
    outputs: list[str] = []
    output_key = node.params.get("output_key")
    if output_key:
        outputs.append(output_key)
    # output_key 未指定でもハンドラーがある場合は 'output' がデフォルト
    # （ただし custom ハンドラーは不明なので組み込みのみ判定）
    builtin_handlers = {"llm", "structured_llm", "streaming_llm"}
    if not output_key and node.handler in builtin_handlers:
        outputs.append("output")

    if node.id in conditional_sources:
        outputs.append("__next__")

    return outputs
