"""Claude Agent SDK-based implementation of :class:`LLMProviderPort`.

Uses ``claude_agent_sdk.query`` with the ``output_format={"type":
"json_schema", "schema": ...}`` option so Claude returns a response that
conforms to the provided JSON Schema. Authentication relies on a logged-in
Claude subscription (``claude login``); no API key is required.

The SDK's ``query`` function is async-only, so this adapter wraps it with
:func:`asyncio.run` when invoked from a synchronous context and with a
``ThreadPoolExecutor`` when a running event loop is detected (to avoid the
``RuntimeError: asyncio.run() cannot be called from a running event loop``
failure mode).
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from typing import Any, cast

from yagra.ports.outbound.llm_provider import (
    LLMCompletion,
    LLMProviderCallError,
    LLMProviderConfigError,
    LLMProviderPort,
    LLMStreamChunk,
)

_DEFAULT_MODEL = "sonnet"


_IMPORT_ERROR_PAYLOAD: dict[str, Any] = {
    "error": "claude_agent_sdk_not_installed",
    "message": "claude-agent-sdk is required for ClaudeAgentSDKProvider",
    "summary": {"provider": "claude_agent_sdk"},
    "hint": 'Run `uv add "yagra[judge]"` to enable Claude Agent SDK provider',
}

_COMPLETE_UNSUPPORTED_PAYLOAD: dict[str, Any] = {
    "error": "claude_agent_sdk_complete_unsupported",
    "message": "ClaudeAgentSDKProvider does not support plain text completion",
    "summary": {"provider": "claude_agent_sdk", "method": "complete"},
    "hint": (
        "Use LiteLLMProvider for complete/complete_streaming; "
        "claude_agent_sdk is subset-only (complete_structured)"
    ),
}

_STREAMING_UNSUPPORTED_PAYLOAD: dict[str, Any] = {
    "error": "claude_agent_sdk_streaming_unsupported",
    "message": "ClaudeAgentSDKProvider does not support streaming completion",
    "summary": {"provider": "claude_agent_sdk", "method": "complete_streaming"},
    "hint": (
        "Use LiteLLMProvider for complete_streaming; "
        "claude_agent_sdk is subset-only (complete_structured)"
    ),
}


class ClaudeAgentSDKProvider(LLMProviderPort):
    """LLM provider backed by Claude Agent SDK subscription auth.

    Instantiation is lazy in the sense that :func:`ClaudeAgentSDKProvider.__init__`
    does not import the SDK; only calls to :meth:`complete_structured` do.
    This allows ``resolve_provider('claude_agent_sdk')`` to succeed even if
    the SDK is not installed — callers only pay the import cost when they
    actually invoke the provider.
    """

    def __init__(self, *, default_model: str = _DEFAULT_MODEL) -> None:
        """Initializes the provider with a default model identifier.

        Args:
            default_model: Model alias to use when callers omit ``model``
                at call time. Defaults to ``"sonnet"`` per product decision
                (cost/quality balance for judge workloads).
        """
        self._default_model = default_model

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
        """Calls Claude Agent SDK and returns the structured output.

        Args:
            system_prompt: Rendered system prompt.
            user_prompt: Rendered user prompt.
            schema: JSON Schema passed to ``ClaudeAgentOptions(output_format=...)``.
            model: Model alias (defaults to the instance default when empty).
            timeout: Timeout in seconds (reserved for future use; the SDK
                does not accept a timeout option directly).
            **kwargs: Forwarded to ``ClaudeAgentOptions`` where applicable.

        Returns:
            Parsed structured output dict returned by the SDK.

        Raises:
            LLMProviderConfigError: If ``claude_agent_sdk`` is not installed.
            LLMProviderCallError: If the SDK invocation fails or no
                structured output is produced before the stream ends.
        """
        try:
            from claude_agent_sdk import (
                ClaudeAgentOptions,
                ResultMessage,
                query,
            )
        except ImportError as exc:
            raise LLMProviderConfigError(_IMPORT_ERROR_PAYLOAD) from exc

        effective_model = model or self._default_model

        # Combine prompts for the SDK which accepts a single ``prompt`` input.
        combined_prompt_parts = [system_prompt.strip(), user_prompt.strip()]
        combined_prompt = "\n\n".join(part for part in combined_prompt_parts if part)

        async def _invoke() -> dict[str, Any]:
            options = ClaudeAgentOptions(
                output_format={"type": "json_schema", "schema": schema},
                model=effective_model,
                **kwargs,
            )
            async for msg in query(prompt=combined_prompt, options=options):
                if isinstance(msg, ResultMessage) and msg.structured_output is not None:
                    output = msg.structured_output
                    if isinstance(output, dict):
                        return output
                    raise LLMProviderCallError(
                        "Claude Agent SDK structured_output is not a JSON object "
                        f"(got {type(output).__name__})"
                    )
            raise LLMProviderCallError(
                "Claude Agent SDK returned no structured output before end of stream"
            )

        try:
            result = _run_async(_invoke())
        except LLMProviderCallError:
            raise
        except Exception as exc:  # noqa: BLE001 - SDK 例外はここで変換
            raise LLMProviderCallError(f"Claude Agent SDK call failed: {exc}") from exc
        return cast("dict[str, Any]", result)

    def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str,
        timeout: int = 30,
        **kwargs: Any,
    ) -> LLMCompletion:
        """Raises because claude_agent_sdk does not support plain completion.

        The adapter is intentionally subset-only: it supports structured
        output via :meth:`complete_structured` but not free-form text
        completion. Callers that need ``complete`` should use
        :class:`LiteLLMProvider` instead.

        Args:
            system_prompt: Ignored.
            user_prompt: Ignored.
            model: Ignored.
            timeout: Ignored.
            **kwargs: Ignored.

        Raises:
            LLMProviderConfigError: Always, with a 4-field structured payload
                explaining the subset constraint.
        """
        raise LLMProviderConfigError(_COMPLETE_UNSUPPORTED_PAYLOAD)

    def complete_streaming(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str,
        timeout: int = 30,
        **kwargs: Any,
    ) -> Iterator[LLMStreamChunk]:
        """Raises because claude_agent_sdk does not support streaming completion.

        Args:
            system_prompt: Ignored.
            user_prompt: Ignored.
            model: Ignored.
            timeout: Ignored.
            **kwargs: Ignored.

        Yields:
            Never yields — raises before the first ``yield`` statement. The
            ``yield`` below is unreachable but ensures the method is typed
            as a generator function.

        Raises:
            LLMProviderConfigError: Always, with a 4-field structured payload
                explaining the subset constraint.
        """
        raise LLMProviderConfigError(_STREAMING_UNSUPPORTED_PAYLOAD)
        yield  # unreachable: marks this as a generator for type-checkers


def _run_async(coro: Any) -> Any:
    """Runs an async coroutine safely from a sync caller.

    When a running event loop is detected (e.g. inside a Jupyter kernel or
    an async test harness), delegates execution to a dedicated worker thread
    so the coroutine runs on its own fresh loop. Otherwise uses
    :func:`asyncio.run` directly.

    Args:
        coro: The coroutine to await.

    Returns:
        Whatever the coroutine returns.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(asyncio.run, coro).result()
