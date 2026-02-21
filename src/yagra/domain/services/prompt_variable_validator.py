"""Provides utilities for extracting prompt template variables."""

from __future__ import annotations

import re
from typing import Any


def _extract_required_vars(params: dict[str, Any]) -> list[str]:
    """Returns a list of variable names required by the prompt from the node params.

    Uses ``input_keys`` if explicitly specified; otherwise auto-extracts ``{variable}``
    patterns from both the system and user prompt templates. Uses the same logic as
    the handler.

    Args:
        params: Node params dictionary.

    Returns:
        List of required variable names (deduplicated, preserving order).
    """
    explicit_keys = params.get("input_keys")
    if explicit_keys is not None:
        if isinstance(explicit_keys, list):
            return [str(k) for k in explicit_keys]
        return []

    prompt = params.get("prompt")
    if not isinstance(prompt, dict):
        return []

    system_template = prompt.get("system", "")
    user_template = prompt.get("user", "")

    system_vars: list[str] = (
        re.findall(r"\{(\w+)\}", system_template) if isinstance(system_template, str) else []
    )
    user_vars: list[str] = (
        re.findall(r"\{(\w+)\}", user_template) if isinstance(user_template, str) else []
    )

    return list(dict.fromkeys(system_vars + user_vars))


def _get_output_key(params: dict[str, Any]) -> str:
    """Returns the output_key from node params. Defaults to ``"output"`` if not specified.

    Args:
        params: Node params dictionary.

    Returns:
        output_key string.
    """
    key = params.get("output_key", "output")
    return str(key) if key else "output"
