"""Provides utilities for extracting prompt template variables."""

from __future__ import annotations

import re
from typing import Any

_LLM_HANDLERS = frozenset({"llm", "streaming_llm", "structured_llm"})


def _extract_required_vars(params: dict[str, Any]) -> list[str]:
    """Returns a list of variable names required by the prompt from the node params.

    Uses ``input_keys`` if explicitly specified; otherwise auto-extracts ``{variable}``
    patterns from the user prompt template. Uses the same logic as the handler.

    Args:
        params: Node params dictionary.

    Returns:
        List of required variable names.
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
    """Returns the output_key from node params. Defaults to ``"output"`` if not specified.

    Args:
        params: Node params dictionary.

    Returns:
        output_key string.
    """
    key = params.get("output_key", "output")
    return str(key) if key else "output"
