"""Adapters implementing :class:`LLMProviderPort`.

Provides the :func:`resolve_provider` factory that maps string identifiers to
concrete provider instances. Sub-modules in this package contain the actual
SDK integrations (``litellm_provider`` / ``claude_agent_sdk_provider``) and
are imported lazily to keep optional dependencies (e.g. ``claude-agent-sdk``)
truly optional for users that do not need them.
"""

from __future__ import annotations

from yagra.ports.outbound.llm_provider import LLMProviderPort

_SUPPORTED_PROVIDERS: tuple[str, ...] = ("claude_agent_sdk", "litellm")


def resolve_provider(name: str) -> LLMProviderPort:
    """Resolves a provider name into an :class:`LLMProviderPort` instance.

    Used by handlers (e.g. ``create_judge_handler``) that receive a provider
    identifier via workflow YAML ``params``. The factory lives in the
    adapters package so the ports layer remains free of concrete imports.

    Args:
        name: Provider identifier. Supported values: ``"claude_agent_sdk"``,
            ``"litellm"``.

    Returns:
        Fresh provider instance implementing :class:`LLMProviderPort`.

    Raises:
        ValueError: If ``name`` is not a supported provider identifier.
    """
    if name == "claude_agent_sdk":
        from yagra.adapters.outbound.llm_providers.claude_agent_sdk_provider import (
            ClaudeAgentSDKProvider,
        )

        return ClaudeAgentSDKProvider()
    if name == "litellm":
        from yagra.adapters.outbound.llm_providers.litellm_provider import LiteLLMProvider

        return LiteLLMProvider()
    supported = ", ".join(repr(n) for n in _SUPPORTED_PROVIDERS)
    raise ValueError(
        f"Unknown LLM provider {name!r}. "
        f"Expected one of: {supported}. "
        f"Hint: pass params.provider='claude_agent_sdk' or 'litellm' in your workflow YAML."
    )


__all__ = ["resolve_provider"]
