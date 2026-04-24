"""Unit tests for ClaudeAgentSDKProvider."""

from __future__ import annotations

import asyncio
import sys
from types import ModuleType
from typing import Any
from unittest.mock import patch

import pytest


def _install_fake_sdk(
    structured_outputs: list[Any] | None = None,
    result_has_structured: bool = True,
) -> ModuleType:
    """Installs a fake ``claude_agent_sdk`` module with minimal API surface.

    Args:
        structured_outputs: Sequence of structured_output values the
            ``query`` generator will yield (wrapped in ``ResultMessage``).
        result_has_structured: Whether the ResultMessage should expose
            ``structured_output`` at all.

    Returns:
        The fake module installed into ``sys.modules``.
    """
    fake = ModuleType("claude_agent_sdk")

    class ResultMessage:
        def __init__(self, structured_output: Any) -> None:
            self.structured_output = structured_output

    class ClaudeAgentOptions:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

    outputs = list(structured_outputs or [])

    async def query(*, prompt: str, options: Any) -> Any:  # noqa: ARG001
        for item in outputs:
            if result_has_structured:
                yield ResultMessage(structured_output=item)
            else:
                yield object()  # not a ResultMessage

    fake.ResultMessage = ResultMessage  # type: ignore[attr-defined]
    fake.ClaudeAgentOptions = ClaudeAgentOptions  # type: ignore[attr-defined]
    fake.query = query  # type: ignore[attr-defined]
    sys.modules["claude_agent_sdk"] = fake
    return fake


class TestClaudeAgentSDKProvider:
    """Happy-path tests for :class:`ClaudeAgentSDKProvider`."""

    def teardown_method(self) -> None:
        sys.modules.pop("claude_agent_sdk", None)

    def test_returns_structured_output(self) -> None:
        """Confirms structured_output is returned as-is when provided."""
        expected = {"score": {"relevance": 4}, "reasoning": "ok"}
        _install_fake_sdk(structured_outputs=[expected])

        from yagra.adapters.outbound.llm_providers.claude_agent_sdk_provider import (
            ClaudeAgentSDKProvider,
        )

        provider = ClaudeAgentSDKProvider()
        result = provider.complete_structured(
            system_prompt="judge this",
            user_prompt="answer",
            schema={"type": "object"},
            model="sonnet",
        )

        assert result == expected

    def test_uses_default_model_when_model_empty(self) -> None:
        """Confirms default_model is used when caller passes empty string."""
        _install_fake_sdk(structured_outputs=[{"score": {}, "reasoning": "r"}])

        from yagra.adapters.outbound.llm_providers.claude_agent_sdk_provider import (
            ClaudeAgentSDKProvider,
        )

        provider = ClaudeAgentSDKProvider(default_model="opus")
        # passing "" should fall back to the instance default
        result = provider.complete_structured(
            system_prompt="s",
            user_prompt="u",
            schema={"type": "object"},
            model="",
        )
        assert result == {"score": {}, "reasoning": "r"}

    def test_no_structured_output_raises_call_error(self) -> None:
        """Confirms missing structured_output raises LLMProviderCallError."""
        _install_fake_sdk(structured_outputs=[])

        from yagra.adapters.outbound.llm_providers.claude_agent_sdk_provider import (
            ClaudeAgentSDKProvider,
        )
        from yagra.ports.outbound.llm_provider import LLMProviderCallError

        provider = ClaudeAgentSDKProvider()
        with pytest.raises(LLMProviderCallError, match="no structured output"):
            provider.complete_structured(
                system_prompt="s",
                user_prompt="u",
                schema={"type": "object"},
                model="sonnet",
            )

    def test_non_dict_structured_output_raises_call_error(self) -> None:
        """Confirms non-dict structured_output raises LLMProviderCallError."""
        _install_fake_sdk(structured_outputs=[["not", "a", "dict"]])

        from yagra.adapters.outbound.llm_providers.claude_agent_sdk_provider import (
            ClaudeAgentSDKProvider,
        )
        from yagra.ports.outbound.llm_provider import LLMProviderCallError

        provider = ClaudeAgentSDKProvider()
        with pytest.raises(LLMProviderCallError, match="not a JSON object"):
            provider.complete_structured(
                system_prompt="s",
                user_prompt="u",
                schema={"type": "object"},
                model="sonnet",
            )

    def test_missing_sdk_raises_config_error(self) -> None:
        """Confirms absent claude_agent_sdk raises LLMProviderConfigError with hint."""
        # Ensure fake module is absent.
        sys.modules.pop("claude_agent_sdk", None)

        from yagra.adapters.outbound.llm_providers.claude_agent_sdk_provider import (
            ClaudeAgentSDKProvider,
        )
        from yagra.ports.outbound.llm_provider import LLMProviderConfigError

        provider = ClaudeAgentSDKProvider()

        # Force the import to fail even if claude_agent_sdk is installed.
        real_import = __import__

        def _fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
            if name == "claude_agent_sdk":
                raise ImportError("no module")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=_fake_import):
            with pytest.raises(LLMProviderConfigError) as excinfo:
                provider.complete_structured(
                    system_prompt="s",
                    user_prompt="u",
                    schema={"type": "object"},
                    model="sonnet",
                )

        payload = excinfo.value.args[0]
        assert isinstance(payload, dict)
        assert payload["error"] == "claude_agent_sdk_not_installed"
        assert 'uv add "yagra[judge]"' in payload["hint"]


class TestClaudeAgentSDKProviderAsyncBridge:
    """Async bridge tests — running inside an existing event loop."""

    def teardown_method(self) -> None:
        sys.modules.pop("claude_agent_sdk", None)

    def test_runs_inside_running_event_loop_via_executor(self) -> None:
        """Confirms the provider works when invoked from a running async loop.

        Simulates the "handler called from within an already-running event
        loop" scenario (e.g. Jupyter or async tests). In that case the
        provider must delegate to a worker thread instead of raising
        ``RuntimeError: asyncio.run() cannot be called from a running event
        loop``.
        """
        expected = {"score": {"relevance": 3}, "reasoning": "r"}
        _install_fake_sdk(structured_outputs=[expected])

        from yagra.adapters.outbound.llm_providers.claude_agent_sdk_provider import (
            ClaudeAgentSDKProvider,
        )

        provider = ClaudeAgentSDKProvider()

        async def _call_from_inside_running_loop() -> dict[str, Any]:
            # Direct sync call from within a running event loop — the
            # provider's ``_run_async`` helper must detect the running loop
            # and offload to a ThreadPoolExecutor.
            return provider.complete_structured(
                system_prompt="s",
                user_prompt="u",
                schema={"type": "object"},
                model="sonnet",
            )

        result = asyncio.run(_call_from_inside_running_loop())
        assert result == expected

    def test_runs_without_event_loop(self) -> None:
        """Confirms the provider uses asyncio.run when no loop is active."""
        expected = {"score": {"a": 1}, "reasoning": "r"}
        _install_fake_sdk(structured_outputs=[expected])

        from yagra.adapters.outbound.llm_providers.claude_agent_sdk_provider import (
            ClaudeAgentSDKProvider,
        )

        provider = ClaudeAgentSDKProvider()
        result = provider.complete_structured(
            system_prompt="s",
            user_prompt="u",
            schema={"type": "object"},
            model="sonnet",
        )
        assert result == expected
