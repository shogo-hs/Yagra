"""litellm-based implementation of :class:`LLMProviderPort`.

Provides three operations that together expose the litellm client through
the port contract without leaking SDK types to handlers:

- :meth:`complete_structured` forces JSON output and injects the expected
  JSON Schema into the system prompt.
- :meth:`complete` performs a plain text completion and returns
  :class:`LLMCompletion` with optional token usage.
- :meth:`complete_streaming` performs a streaming completion and yields
  :class:`LLMStreamChunk` values, with the terminal chunk carrying usage
  when litellm exposes it.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import litellm

from yagra.ports.outbound.llm_provider import (
    LLMCompletion,
    LLMProviderCallError,
    LLMProviderPort,
    LLMStreamChunk,
    LLMTokenUsage,
)


class LiteLLMProvider(LLMProviderPort):
    """LLM provider backed by ``litellm`` for unified multi-provider access.

    litellm routes requests to 100+ upstream providers using a unified API.
    The provider identifier is embedded directly in the ``model`` string
    (e.g. ``"openai/gpt-4o"``, ``"anthropic/claude-opus-4-6"``) that callers
    pass through each operation.
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

    def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str,
        timeout: int = 30,
        **kwargs: Any,
    ) -> LLMCompletion:
        """Calls litellm and returns a free-form text completion.

        Args:
            system_prompt: Rendered system prompt.
            user_prompt: Rendered user prompt.
            model: litellm model string (e.g. ``"openai/gpt-4o"``).
            timeout: Timeout in seconds.
            **kwargs: Forwarded to ``litellm.completion``.

        Returns:
            :class:`LLMCompletion` with generated text, optional
            :class:`LLMTokenUsage`, and the raw response dump when available.

        Raises:
            LLMProviderCallError: If litellm returns an empty response or
                ``None`` content, or if the underlying call raises.
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
            response = litellm.completion(
                model=model,
                messages=messages,
                timeout=timeout,
                **kwargs,
            )
        except Exception as exc:  # noqa: BLE001
            raise LLMProviderCallError(f"litellm.completion failed: {exc}") from exc

        if not response.choices:
            raise LLMProviderCallError("litellm returned empty choices")

        content = response.choices[0].message.content
        if content is None:
            raise LLMProviderCallError("litellm returned None content")

        return LLMCompletion(
            content=content,
            usage=_extract_usage(response),
            raw=_dump_response(response),
        )

    def complete_streaming(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str,
        timeout: int = 30,
        **kwargs: Any,
    ) -> Iterator[LLMStreamChunk]:
        """Calls litellm with streaming and yields chunks as they arrive.

        The terminal chunk is always emitted with ``done=True``. If litellm
        exposes a ``usage`` attribute on the streaming response (best-effort),
        the terminal chunk also carries an :class:`LLMTokenUsage`.

        Args:
            system_prompt: Rendered system prompt.
            user_prompt: Rendered user prompt.
            model: litellm model string.
            timeout: Timeout in seconds.
            **kwargs: Forwarded to ``litellm.completion``. ``stream`` is
                forced to ``True`` regardless of caller input.

        Yields:
            :class:`LLMStreamChunk` values.

        Raises:
            LLMProviderCallError: If litellm fails to open the stream.
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        call_kwargs: dict[str, Any] = dict(kwargs)
        call_kwargs["stream"] = True

        try:
            response = litellm.completion(
                model=model,
                messages=messages,
                timeout=timeout,
                **call_kwargs,
            )
        except Exception as exc:  # noqa: BLE001
            raise LLMProviderCallError(f"litellm.completion (stream) failed: {exc}") from exc

        yield from _iterate_stream(response)


def _iterate_stream(response: Any) -> Iterator[LLMStreamChunk]:
    """Iterates a litellm streaming response into port-level chunks.

    Emits one :class:`LLMStreamChunk` per non-empty delta, then a terminal
    chunk with ``done=True`` and best-effort token usage.

    Args:
        response: litellm streaming response (iterable of chunk objects).

    Yields:
        :class:`LLMStreamChunk` values.
    """
    for chunk in response:
        if not getattr(chunk, "choices", None):
            continue
        delta = chunk.choices[0].delta
        if delta is None:
            continue
        content = getattr(delta, "content", None)
        if content:
            yield LLMStreamChunk(delta=content, done=False)

    yield LLMStreamChunk(delta="", done=True, usage=_extract_usage(response))


def _extract_usage(response_or_stream: Any) -> LLMTokenUsage | None:
    """Extracts :class:`LLMTokenUsage` from a litellm response or stream.

    Handles both direct ``.usage`` attributes (completion) and internal
    ``._usage`` attributes (streaming) that some litellm versions expose.

    Args:
        response_or_stream: litellm response object or its streaming wrapper.

    Returns:
        :class:`LLMTokenUsage` when available, otherwise ``None``.
    """
    raw_usage = getattr(response_or_stream, "usage", None) or getattr(
        response_or_stream, "_usage", None
    )
    if raw_usage is None:
        return None
    return LLMTokenUsage(
        prompt_tokens=int(getattr(raw_usage, "prompt_tokens", 0) or 0),
        completion_tokens=int(getattr(raw_usage, "completion_tokens", 0) or 0),
        total_tokens=int(getattr(raw_usage, "total_tokens", 0) or 0),
    )


def _dump_response(response: Any) -> dict[str, Any] | None:
    """Best-effort dump of a litellm response to a plain dict.

    Args:
        response: litellm response object (usually a Pydantic-ish model).

    Returns:
        Dict representation when ``model_dump`` is available, else ``None``.
    """
    dumper = getattr(response, "model_dump", None)
    if callable(dumper):
        try:
            dumped = dumper()
        except Exception:  # noqa: BLE001 - dump は observability 用途で best-effort
            return None
        if isinstance(dumped, dict):
            return dumped
    return None
