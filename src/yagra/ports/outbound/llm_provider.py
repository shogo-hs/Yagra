"""Output port contract for LLM providers (LLM-as-a-Judge and future handlers).

Defines the Protocol that LLM provider adapters must satisfy. Adapters in
``yagra.adapters.outbound.llm_providers`` implement this port with concrete
clients (``litellm``, ``claude_agent_sdk``). The ``ports`` layer must not
import any concrete SDK in order to preserve hexagonal boundaries.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class LLMTokenUsage:
    """LLM provider が返した token 消費量（pure Python / SDK 非依存）.

    Attributes:
        prompt_tokens: 入力として消費された token 数.
        completion_tokens: 生成として出力された token 数.
        total_tokens: 両者の合計 token 数.
    """

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass(frozen=True, slots=True)
class LLMCompletion:
    """``LLMProviderPort.complete`` の戻り値.

    Attributes:
        content: LLM が生成したテキスト.
        usage: 使用 token 情報. provider が返さない場合 ``None``.
        raw: provider-native なレスポンスダンプ. 観測可能性目的の optional.
    """

    content: str
    usage: LLMTokenUsage | None = None
    raw: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class LLMStreamChunk:
    """``LLMProviderPort.complete_streaming`` が yield する 1 chunk.

    Attributes:
        delta: このチャンクで追加された文字列差分.
        done: ストリーム終端チャンクなら ``True``.
        usage: terminal chunk に乗せる token usage. それ以外は ``None``.
    """

    delta: str
    done: bool = False
    usage: LLMTokenUsage | None = None


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
    """LLM provider の抽象契約.

    Adapters provide three operations:

    - :meth:`complete_structured`: JSON Schema に適合する構造化出力 (``dict``) を返す.
    - :meth:`complete`: 自由記述のテキスト応答を :class:`LLMCompletion` で返す.
    - :meth:`complete_streaming`: 逐次的に :class:`LLMStreamChunk` を yield する.

    Handlers (e.g. ``create_judge_handler`` / ``create_llm_handler``) depend
    only on this port and remain decoupled from any particular SDK.

    Implementations must not raise SDK-native exceptions outside of the
    provider module boundary; instead translate them to
    :class:`LLMProviderCallError` or :class:`LLMProviderConfigError` so
    downstream handlers can treat them uniformly.
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

    def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str,
        timeout: int = 30,
        **kwargs: Any,
    ) -> LLMCompletion:
        """Invokes the LLM and returns a free-form text completion.

        Args:
            system_prompt: Rendered system prompt.
            user_prompt: Rendered user prompt.
            model: Provider-dependent model identifier.
            timeout: Timeout in seconds.
            **kwargs: Additional provider-specific keyword arguments.

        Returns:
            :class:`LLMCompletion` containing the generated text, optional
            token usage, and optional provider-native raw response.

        Raises:
            LLMProviderConfigError: If the provider is not configured for
                plain text completion (e.g. subset adapter).
            LLMProviderCallError: If the provider call fails or returns an
                unusable response.
        """
        ...

    def complete_streaming(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str,
        timeout: int = 30,
        **kwargs: Any,
    ) -> Iterator[LLMStreamChunk]:
        """Invokes the LLM with streaming and yields chunks as they arrive.

        Args:
            system_prompt: Rendered system prompt.
            user_prompt: Rendered user prompt.
            model: Provider-dependent model identifier.
            timeout: Timeout in seconds.
            **kwargs: Additional provider-specific keyword arguments.

        Yields:
            :class:`LLMStreamChunk` instances. The terminal chunk has
            ``done=True`` and MAY carry aggregated ``usage``. Intermediate
            chunks only carry ``delta`` text.

        Raises:
            LLMProviderConfigError: If the provider does not support
                streaming (e.g. subset adapter).
            LLMProviderCallError: If the underlying stream fails.
        """
        ...


__all__ = [
    "LLMCompletion",
    "LLMProviderCallError",
    "LLMProviderConfigError",
    "LLMProviderError",
    "LLMProviderPort",
    "LLMStreamChunk",
    "LLMTokenUsage",
]
