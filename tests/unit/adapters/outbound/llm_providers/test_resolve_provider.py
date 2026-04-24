"""Unit tests for :func:`resolve_provider` factory."""

from __future__ import annotations

import pytest


class TestResolveProvider:
    """Factory resolution tests."""

    def test_resolves_litellm(self) -> None:
        """Confirms 'litellm' resolves to LiteLLMProvider."""
        from yagra.adapters.outbound.llm_providers import resolve_provider
        from yagra.adapters.outbound.llm_providers.litellm_provider import LiteLLMProvider

        provider = resolve_provider("litellm")
        assert isinstance(provider, LiteLLMProvider)

    def test_resolves_claude_agent_sdk(self) -> None:
        """Confirms 'claude_agent_sdk' resolves to ClaudeAgentSDKProvider (lazy SDK import)."""
        from yagra.adapters.outbound.llm_providers import resolve_provider
        from yagra.adapters.outbound.llm_providers.claude_agent_sdk_provider import (
            ClaudeAgentSDKProvider,
        )

        # Even without the SDK installed, resolution itself must succeed;
        # only ``complete_structured`` triggers the SDK import.
        provider = resolve_provider("claude_agent_sdk")
        assert isinstance(provider, ClaudeAgentSDKProvider)

    def test_unknown_provider_raises_value_error(self) -> None:
        """Confirms unknown name raises ValueError with a helpful hint."""
        from yagra.adapters.outbound.llm_providers import resolve_provider

        with pytest.raises(ValueError) as excinfo:
            resolve_provider("mystery_provider")

        msg = str(excinfo.value)
        assert "mystery_provider" in msg
        assert "claude_agent_sdk" in msg
        assert "litellm" in msg

    def test_returns_fresh_instance_each_call(self) -> None:
        """Confirms factory returns a new instance per call (no caching)."""
        from yagra.adapters.outbound.llm_providers import resolve_provider

        a = resolve_provider("litellm")
        b = resolve_provider("litellm")
        assert a is not b
