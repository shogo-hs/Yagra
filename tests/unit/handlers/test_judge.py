"""Unit tests for :func:`create_judge_handler`."""

from __future__ import annotations

import sys
import textwrap
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from yagra.ports.outbound.llm_provider import (
    LLMCompletion,
    LLMProviderCallError,
    LLMProviderConfigError,
    LLMProviderPort,
    LLMStreamChunk,
)


class _FakeProvider(LLMProviderPort):
    """Test double implementing :class:`LLMProviderPort`."""

    def __init__(
        self,
        *,
        response: dict[str, Any] | None = None,
        raise_error: Exception | None = None,
    ) -> None:
        self.response = response or {}
        self.raise_error = raise_error
        self.calls: list[dict[str, Any]] = []

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
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "schema": schema,
                "model": model,
                "timeout": timeout,
                "kwargs": kwargs,
            }
        )
        if self.raise_error is not None:
            raise self.raise_error
        return self.response

    def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str,
        timeout: int = 30,
        **kwargs: Any,
    ) -> LLMCompletion:
        """Not used by judge tests; implemented for Protocol conformance."""
        raise NotImplementedError("judge handler only uses complete_structured")

    def complete_streaming(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str,
        timeout: int = 30,
        **kwargs: Any,
    ) -> Iterator[LLMStreamChunk]:
        """Not used by judge tests; implemented for Protocol conformance."""

        def _gen() -> Iterator[LLMStreamChunk]:
            raise NotImplementedError("judge handler only uses complete_structured")
            yield  # pragma: no cover

        return _gen()


_BASIC_RUBRIC = {
    "description": "Answer quality",
    "criteria": [
        {
            "name": "relevance",
            "description": "How well the answer matches the question",
            "scale": {"min": 1, "max": 5},
        },
        {
            "name": "accuracy",
            "scale": {"min": 1, "max": 5},
        },
    ],
    "require_reasoning": True,
}


class TestJudgeHandlerHappyPath:
    """Core success paths."""

    def test_returns_structured_judge_result(self) -> None:
        """Confirms happy-path call returns score/reasoning/rubric_items with _overall."""
        from yagra.handlers.judge import create_judge_handler

        provider_response = {
            "score": {"relevance": 4, "accuracy": 5},
            "reasoning": "Accurate and relevant",
            "rubric_items": [
                {"name": "relevance", "score": 4, "reasoning": "matches"},
                {"name": "accuracy", "score": 5, "reasoning": "verified"},
            ],
        }
        provider = _FakeProvider(response=provider_response)

        handler = create_judge_handler(provider=provider, retry=1)
        result = handler(
            state={"query": "What is 2+2?"},
            params={
                "rubric": _BASIC_RUBRIC,
                "prompt": {"system": "Judge this", "user": "Q: {query}"},
            },
        )

        assert "judge_result" in result
        jr = result["judge_result"]
        assert jr["score"]["relevance"] == 4
        assert jr["score"]["accuracy"] == 5
        assert jr["score"]["_overall"] == pytest.approx(4.5)
        assert jr["reasoning"] == "Accurate and relevant"
        assert len(jr["rubric_items"]) == 2

    def test_custom_output_key(self) -> None:
        """Confirms params.output_key is respected."""
        from yagra.handlers.judge import create_judge_handler

        provider = _FakeProvider(
            response={
                "score": {"relevance": 3, "accuracy": 3},
                "reasoning": "ok",
                "rubric_items": [],
            }
        )
        handler = create_judge_handler(provider=provider, retry=1)
        result = handler(
            state={"query": "x"},
            params={
                "rubric": _BASIC_RUBRIC,
                "prompt": {"system": "Judge", "user": "{query}"},
                "output_key": "my_grade",
            },
        )

        assert "my_grade" in result
        assert "judge_result" not in result

    def test_schema_contains_integer_bounds(self) -> None:
        """Confirms JSON schema passed to provider matches rubric scale."""
        from yagra.handlers.judge import create_judge_handler

        provider = _FakeProvider(
            response={
                "score": {"relevance": 5, "accuracy": 5},
                "reasoning": "great",
                "rubric_items": [],
            }
        )
        handler = create_judge_handler(provider=provider, retry=1)
        handler(
            state={"query": "x"},
            params={
                "rubric": _BASIC_RUBRIC,
                "prompt": {"system": "Judge", "user": "{query}"},
            },
        )

        schema = provider.calls[0]["schema"]
        assert schema["properties"]["score"]["properties"]["relevance"] == {
            "type": "integer",
            "minimum": 1,
            "maximum": 5,
        }
        assert "reasoning" in schema["required"]

    def test_rubric_ref_loading_from_file(self, tmp_path: Path) -> None:
        """Confirms rubric_ref with #key loads from a YAML file."""
        rubric_file = tmp_path / "rubrics" / "quality.yaml"
        rubric_file.parent.mkdir()
        rubric_file.write_text(
            textwrap.dedent(
                """\
                default:
                  description: Answer quality
                  criteria:
                    - name: relevance
                      scale: {min: 1, max: 5}
                  require_reasoning: true
                """
            ),
            encoding="utf-8",
        )

        from yagra.handlers.judge import create_judge_handler

        provider = _FakeProvider(
            response={
                "score": {"relevance": 4},
                "reasoning": "r",
                "rubric_items": [],
            }
        )
        handler = create_judge_handler(provider=provider, retry=1)
        result = handler(
            state={"query": "x"},
            params={
                "rubric_ref": "rubrics/quality.yaml#default",
                "_workflow_dir": str(tmp_path),
                "prompt": {"system": "Judge", "user": "{query}"},
            },
        )
        assert result["judge_result"]["score"]["relevance"] == 4

    def test_default_provider_is_claude_agent_sdk(self) -> None:
        """Confirms absent provider arg + absent params.provider resolves to claude_agent_sdk."""
        from yagra.handlers.judge import (
            JudgeHandlerConfigError,
            create_judge_handler,
        )

        handler = create_judge_handler(retry=1)

        # Simulate claude_agent_sdk not installed to confirm default resolution
        # actually routes to the Claude provider (which will then fail at call time).
        real_import = __import__

        def _fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
            if name == "claude_agent_sdk":
                raise ImportError("no module")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=_fake_import):
            sys.modules.pop("claude_agent_sdk", None)
            with pytest.raises(JudgeHandlerConfigError) as excinfo:
                handler(
                    state={"query": "x"},
                    params={
                        "rubric": _BASIC_RUBRIC,
                        "prompt": {"system": "Judge", "user": "{query}"},
                    },
                )

        payload = excinfo.value.payload
        assert payload["error"] == "claude_agent_sdk_not_installed"
        assert 'uv add "yagra[judge]"' in payload["hint"]


class TestJudgeHandlerRubricValidation:
    """Silent-success prevention via fail-fast rubric validation."""

    def test_scale_min_ge_max_raises(self) -> None:
        """Confirms scale.min >= scale.max raises rubric_invalid_scale."""
        from yagra.handlers.judge import (
            JudgeHandlerConfigError,
            create_judge_handler,
        )

        handler = create_judge_handler(provider=_FakeProvider(), retry=1)
        with pytest.raises(JudgeHandlerConfigError) as excinfo:
            handler(
                state={"query": "x"},
                params={
                    "rubric": {
                        "criteria": [{"name": "bad", "scale": {"min": 5, "max": 3}}],
                    },
                    "prompt": {"system": "j", "user": "{query}"},
                },
            )
        assert excinfo.value.payload["error"] == "rubric_invalid_scale"

    def test_empty_criteria_raises(self) -> None:
        """Confirms empty criteria list raises rubric_empty."""
        from yagra.handlers.judge import (
            JudgeHandlerConfigError,
            create_judge_handler,
        )

        handler = create_judge_handler(provider=_FakeProvider(), retry=1)
        with pytest.raises(JudgeHandlerConfigError) as excinfo:
            handler(
                state={"query": "x"},
                params={
                    "rubric": {"criteria": []},
                    "prompt": {"system": "j", "user": "{query}"},
                },
            )
        assert excinfo.value.payload["error"] == "rubric_empty"

    def test_missing_criterion_name_raises(self) -> None:
        """Confirms criterion without name raises rubric_missing_name."""
        from yagra.handlers.judge import (
            JudgeHandlerConfigError,
            create_judge_handler,
        )

        handler = create_judge_handler(provider=_FakeProvider(), retry=1)
        with pytest.raises(JudgeHandlerConfigError) as excinfo:
            handler(
                state={"query": "x"},
                params={
                    "rubric": {
                        "criteria": [{"scale": {"min": 1, "max": 5}}],
                    },
                    "prompt": {"system": "j", "user": "{query}"},
                },
            )
        assert excinfo.value.payload["error"] == "rubric_missing_name"

    def test_duplicate_criterion_names_raise(self) -> None:
        """Confirms duplicate criterion names raise rubric_duplicate_name."""
        from yagra.handlers.judge import (
            JudgeHandlerConfigError,
            create_judge_handler,
        )

        handler = create_judge_handler(provider=_FakeProvider(), retry=1)
        with pytest.raises(JudgeHandlerConfigError) as excinfo:
            handler(
                state={"query": "x"},
                params={
                    "rubric": {
                        "criteria": [
                            {"name": "a", "scale": {"min": 1, "max": 5}},
                            {"name": "a", "scale": {"min": 1, "max": 5}},
                        ],
                    },
                    "prompt": {"system": "j", "user": "{query}"},
                },
            )
        assert excinfo.value.payload["error"] == "rubric_duplicate_name"

    def test_rubric_and_rubric_ref_both_raises(self) -> None:
        """Confirms specifying both rubric and rubric_ref raises rubric_conflict."""
        from yagra.handlers.judge import (
            JudgeHandlerConfigError,
            create_judge_handler,
        )

        handler = create_judge_handler(provider=_FakeProvider(), retry=1)
        with pytest.raises(JudgeHandlerConfigError) as excinfo:
            handler(
                state={"query": "x"},
                params={
                    "rubric": _BASIC_RUBRIC,
                    "rubric_ref": "file.yaml",
                    "prompt": {"system": "j", "user": "{query}"},
                },
            )
        assert excinfo.value.payload["error"] == "rubric_conflict"

    def test_rubric_ref_not_found_raises(self, tmp_path: Path) -> None:
        """Confirms missing rubric_ref file raises rubric_not_found."""
        from yagra.handlers.judge import (
            JudgeHandlerConfigError,
            create_judge_handler,
        )

        handler = create_judge_handler(provider=_FakeProvider(), retry=1)
        with pytest.raises(JudgeHandlerConfigError) as excinfo:
            handler(
                state={"query": "x"},
                params={
                    "rubric_ref": "missing.yaml#default",
                    "_workflow_dir": str(tmp_path),
                    "prompt": {"system": "j", "user": "{query}"},
                },
            )
        assert excinfo.value.payload["error"] == "rubric_not_found"

    def test_rubric_missing_raises(self) -> None:
        """Confirms omitting both rubric and rubric_ref raises rubric_missing."""
        from yagra.handlers.judge import (
            JudgeHandlerConfigError,
            create_judge_handler,
        )

        handler = create_judge_handler(provider=_FakeProvider(), retry=1)
        with pytest.raises(JudgeHandlerConfigError) as excinfo:
            handler(
                state={"query": "x"},
                params={
                    "prompt": {"system": "j", "user": "{query}"},
                },
            )
        assert excinfo.value.payload["error"] == "rubric_missing"


class TestJudgeHandlerProviderErrors:
    """Provider runtime failure propagation."""

    def test_provider_call_error_wrapped(self) -> None:
        """Confirms LLMProviderCallError wrapped into JudgeHandlerCallError."""
        from yagra.handlers.judge import (
            JudgeHandlerCallError,
            create_judge_handler,
        )

        provider = _FakeProvider(raise_error=LLMProviderCallError("boom"))
        handler = create_judge_handler(provider=provider, retry=1)
        with pytest.raises(JudgeHandlerCallError) as excinfo:
            handler(
                state={"query": "x"},
                params={
                    "rubric": _BASIC_RUBRIC,
                    "prompt": {"system": "j", "user": "{query}"},
                },
            )
        assert excinfo.value.payload["error"] == "provider_call_failed"

    def test_provider_config_error_wrapped(self) -> None:
        """Confirms LLMProviderConfigError wrapped into JudgeHandlerConfigError."""
        from yagra.handlers.judge import (
            JudgeHandlerConfigError,
            create_judge_handler,
        )

        payload = {
            "error": "claude_agent_sdk_not_installed",
            "message": "missing",
            "summary": {},
            "hint": "install",
        }
        provider = _FakeProvider(raise_error=LLMProviderConfigError(payload))
        handler = create_judge_handler(provider=provider, retry=1)
        with pytest.raises(JudgeHandlerConfigError) as excinfo:
            handler(
                state={"query": "x"},
                params={
                    "rubric": _BASIC_RUBRIC,
                    "prompt": {"system": "j", "user": "{query}"},
                },
            )
        assert excinfo.value.payload["error"] == "claude_agent_sdk_not_installed"


class TestJudgeHandlerOutputValidation:
    """Output validation (silent-success prevention)."""

    def test_missing_score_field_raises(self) -> None:
        """Confirms output missing one criterion score raises invalid_judge_output."""
        from yagra.handlers.judge import (
            JudgeHandlerCallError,
            create_judge_handler,
        )

        # Provider returns score only for 'relevance', omitting 'accuracy'.
        provider = _FakeProvider(
            response={
                "score": {"relevance": 4},
                "reasoning": "r",
                "rubric_items": [],
            }
        )
        handler = create_judge_handler(provider=provider, retry=1)
        with pytest.raises(JudgeHandlerCallError) as excinfo:
            handler(
                state={"query": "x"},
                params={
                    "rubric": _BASIC_RUBRIC,
                    "prompt": {"system": "j", "user": "{query}"},
                },
            )
        assert excinfo.value.payload["error"] == "invalid_judge_output"

    def test_missing_reasoning_when_required_raises(self) -> None:
        """Confirms missing reasoning raises when require_reasoning is true."""
        from yagra.handlers.judge import (
            JudgeHandlerCallError,
            create_judge_handler,
        )

        provider = _FakeProvider(
            response={
                "score": {"relevance": 4, "accuracy": 5},
                # reasoning intentionally missing
                "rubric_items": [],
                "reasoning": None,
            }
        )
        handler = create_judge_handler(provider=provider, retry=1)
        with pytest.raises(JudgeHandlerCallError) as excinfo:
            handler(
                state={"query": "x"},
                params={
                    "rubric": _BASIC_RUBRIC,
                    "prompt": {"system": "j", "user": "{query}"},
                },
            )
        assert excinfo.value.payload["error"] == "invalid_judge_output"


class TestJudgeHandlerProviderResolution:
    """Tests for provider argument vs params hybrid resolution."""

    def test_params_provider_litellm_resolves(self) -> None:
        """Confirms params.provider='litellm' selects LiteLLMProvider via factory."""
        # Patch litellm.completion so LiteLLMProvider can run without a real API call.
        import json
        from unittest.mock import MagicMock

        from yagra.handlers.judge import create_judge_handler

        fake_response = MagicMock()
        fake_response.choices = [
            MagicMock(
                message=MagicMock(
                    content=json.dumps(
                        {
                            "score": {"relevance": 3, "accuracy": 4},
                            "reasoning": "mid",
                            "rubric_items": [],
                        }
                    )
                )
            )
        ]
        mock_litellm = MagicMock()
        mock_litellm.completion.return_value = fake_response

        with patch(
            "yagra.adapters.outbound.llm_providers.litellm_provider.litellm",
            mock_litellm,
        ):
            handler = create_judge_handler(retry=1)
            result = handler(
                state={"query": "x"},
                params={
                    "provider": "litellm",
                    "model": "openai/gpt-4o",
                    "rubric": _BASIC_RUBRIC,
                    "prompt": {"system": "j", "user": "{query}"},
                },
            )

        assert result["judge_result"]["score"]["relevance"] == 3

    def test_unknown_params_provider_raises(self) -> None:
        """Confirms unknown provider string raises unknown_provider."""
        from yagra.handlers.judge import (
            JudgeHandlerConfigError,
            create_judge_handler,
        )

        handler = create_judge_handler(retry=1)
        with pytest.raises(JudgeHandlerConfigError) as excinfo:
            handler(
                state={"query": "x"},
                params={
                    "provider": "mystery",
                    "rubric": _BASIC_RUBRIC,
                    "prompt": {"system": "j", "user": "{query}"},
                },
            )
        assert excinfo.value.payload["error"] == "unknown_provider"

    def test_non_string_provider_param_raises(self) -> None:
        """Confirms non-string provider param raises invalid_provider_param."""
        from yagra.handlers.judge import (
            JudgeHandlerConfigError,
            create_judge_handler,
        )

        handler = create_judge_handler(retry=1)
        with pytest.raises(JudgeHandlerConfigError) as excinfo:
            handler(
                state={"query": "x"},
                params={
                    "provider": 123,
                    "rubric": _BASIC_RUBRIC,
                    "prompt": {"system": "j", "user": "{query}"},
                },
            )
        assert excinfo.value.payload["error"] == "invalid_provider_param"
