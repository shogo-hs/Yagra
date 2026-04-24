"""Output port contract for LLM providers (LLM-as-a-Judge and future handlers).

Defines the Protocol that LLM provider adapters must satisfy. Adapters in
``yagra.adapters.outbound.llm_providers`` implement this port with concrete
clients (``litellm``, ``claude_agent_sdk``). The ``ports`` layer must not
import any concrete SDK in order to preserve hexagonal boundaries.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


class LLMProviderError(RuntimeError):
    """Base exception for LLM provider adapter failures.

    Subclasses distinguish configuration errors from runtime call errors so
    callers can react with the appropriate recovery strategy (retry, surface
    hint, abort).
    """


class LLMProviderConfigError(LLMProviderError):
    """設定不備で provider を初期化・呼出せない場合に送出する例外."""


class LLMProviderCallError(LLMProviderError):
    """Provider 呼出中の通信エラー・応答不備で送出する例外."""


@runtime_checkable
class LLMProviderPort(Protocol):
    """Structured JSON 出力を返す LLM provider の抽象契約.

    Adapters promise to take a system/user prompt pair together with a JSON
    Schema describing the expected response shape, invoke the underlying
    provider, and return a ``dict`` conforming to the schema. Handlers (e.g.
    ``create_judge_handler``) build domain-specific logic on top of this
    single operation and remain decoupled from any particular SDK.

    Implementations must not raise SDK-native exceptions outside of the
    provider module boundary; instead translate them to
    :class:`LLMProviderCallError` so downstream handlers can treat them
    uniformly.
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
        """Invokes the LLM and returns a structured dict matching ``schema``.

        Args:
            system_prompt: Rendered system prompt (already interpolated).
            user_prompt: Rendered user prompt (already interpolated).
            schema: JSON Schema describing the expected response shape.
            model: Provider-dependent model identifier (e.g. ``"sonnet"``
                for Claude Agent SDK, ``"openai/gpt-4o"`` for litellm).
            timeout: Timeout in seconds.
            **kwargs: Additional provider-specific keyword arguments.

        Returns:
            Parsed response as a dict. Callers validate that required
            fields exist.

        Raises:
            LLMProviderConfigError: If the provider cannot be initialized
                or configured (e.g. missing dependency, invalid schema).
            LLMProviderCallError: If the provider call fails, returns an
                empty response, or produces unparsable output.
        """
        ...
