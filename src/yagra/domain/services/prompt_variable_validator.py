"""プロンプトテンプレート変数抽出ユーティリティを提供する。"""

from __future__ import annotations

import re
from typing import Any

_LLM_HANDLERS = frozenset({"llm", "streaming_llm", "structured_llm"})


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
