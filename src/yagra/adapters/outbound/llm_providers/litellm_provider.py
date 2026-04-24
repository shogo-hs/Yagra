"""litellm-based implementation of :class:`LLMProviderPort`.

Uses ``litellm.completion`` with ``response_format={"type": "json_object"}``
and injects the expected JSON Schema into the system prompt so that most
provider/model combinations return a parseable JSON response.
"""

from __future__ import annotations

import json
from typing import Any

import litellm

from yagra.ports.outbound.llm_provider import (
    LLMProviderCallError,
    LLMProviderPort,
)


class LiteLLMProvider(LLMProviderPort):
    """LLM provider backed by `litellm` for structured JSON output.

    litellm routes requests to 100+ upstream providers using a unified API.
    The provider identifier is embedded directly in the ``model`` string
    (e.g. ``"openai/gpt-4o"``, ``"anthropic/claude-opus-4-6"``) that callers
    pass through ``complete_structured``.

    The implementation mirrors ``create_structured_llm_handler``'s approach
    of forcing ``response_format=json_object`` and appending the JSON Schema
    to the system prompt, but returns a raw dict (no Pydantic coupling) so
    downstream handlers can apply their own validation.
    """

    def complete_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: dict[str, Any],
        model: str,
        timeout: int = 30,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Calls litellm and returns the parsed JSON response.

        Args:
            system_prompt: Rendered system prompt.
            user_prompt: Rendered user prompt.
            schema: JSON Schema to embed in the system prompt.
            model: litellm model string (e.g. ``"openai/gpt-4o"``).
            timeout: Timeout in seconds.
            **kwargs: Forwarded to ``litellm.completion``.

        Returns:
            Parsed JSON response as a dict.

        Raises:
            LLMProviderCallError: If litellm returns an empty response,
                ``None`` content, or content that cannot be parsed as JSON.
        """
        schema_hint = json.dumps(schema, ensure_ascii=False)
        json_system_prompt = (
            f"{system_prompt}\n\n"
            f"Respond with valid JSON only. "
            f"The JSON must conform to the following schema:\n{schema_hint}"
        ).strip()

        messages = [
            {"role": "system", "content": json_system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        call_kwargs: dict[str, Any] = dict(kwargs)
        call_kwargs.setdefault("response_format", {"type": "json_object"})

        try:
            response = litellm.completion(
                model=model,
                messages=messages,
                timeout=timeout,
                **call_kwargs,
            )
        except Exception as exc:  # noqa: BLE001 - 外部 SDK は広く捕捉して境界で変換
            raise LLMProviderCallError(f"litellm.completion failed: {exc}") from exc

        if not response.choices:
            raise LLMProviderCallError("litellm returned empty choices")

        content = response.choices[0].message.content
        if content is None:
            raise LLMProviderCallError("litellm returned None content")

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise LLMProviderCallError(f"litellm response is not valid JSON: {exc.msg}") from exc

        if not isinstance(parsed, dict):
            raise LLMProviderCallError(
                f"litellm response is not a JSON object (got {type(parsed).__name__})"
            )

        return parsed
