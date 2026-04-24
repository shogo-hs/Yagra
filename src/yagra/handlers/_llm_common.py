"""Shared utilities for LLM handler implementations.

Extracts common parameter validation, prompt interpolation, retry logic,
and token usage reporting used across llm, structured_llm, and streaming_llm handlers.

Token usage reporting now operates on :class:`LLMTokenUsage` dataclasses
returned by :class:`LLMProviderPort` implementations — no litellm-native
types leak into the handler layer.
"""

import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from yagra.handlers.errors import LLMHandlerCallError, LLMHandlerConfigError
from yagra.ports.outbound.llm_provider import (
    LLMProviderCallError,
    LLMProviderConfigError,
    LLMProviderPort,
    LLMTokenUsage,
)


@dataclass(frozen=True, slots=True)
class LLMParams:
    """Validated and extracted LLM handler parameters.

    Attributes:
        provider: LLM provider name (e.g. 'openai', 'anthropic').
        model_name: Model name (e.g. 'gpt-4o', 'claude-opus-4-6').
        litellm_model: Full litellm model string (e.g. 'openai/gpt-4o').
        model_kwargs: Additional kwargs for litellm.completion (copied from params).
        output_key: State key for storing the handler output.
        effective_retry: Number of retry attempts.
        system_prompt_template: Raw system prompt template before interpolation.
        user_prompt_template: Raw user prompt template before interpolation.
    """

    provider: str
    model_name: str
    litellm_model: str
    model_kwargs: dict[str, Any]
    output_key: str
    effective_retry: int
    system_prompt_template: str
    user_prompt_template: str


def extract_llm_params(params: dict[str, Any], default_retry: int) -> LLMParams:
    """Extracts and validates common LLM handler parameters.

    Validates that prompt is a dict, model has provider and name,
    and returns a frozen bundle of extracted values.

    Args:
        params: Node parameters dictionary from the workflow.
        default_retry: Default retry count from the handler factory.

    Returns:
        Validated parameter bundle.

    Raises:
        LLMHandlerConfigError: If required parameters are missing or invalid.
    """
    prompt = params.get("prompt")
    if not isinstance(prompt, dict):
        msg = "'prompt' must be a dict with 'system' and 'user' keys"
        raise LLMHandlerConfigError(msg)

    model = params.get("model")
    if not isinstance(model, dict):
        msg = "'model' must be a dict with 'provider', 'name', and optional 'kwargs'"
        raise LLMHandlerConfigError(msg)

    provider = model.get("provider")
    model_name = model.get("name")
    if not provider or not model_name:
        msg = "'model' must have 'provider' and 'name' keys"
        raise LLMHandlerConfigError(msg)

    return LLMParams(
        provider=provider,
        model_name=model_name,
        litellm_model=f"{provider}/{model_name}",
        model_kwargs=dict(model.get("kwargs", {})),
        output_key=params.get("output_key", "output"),
        effective_retry=params.get("_retry_override", default_retry),
        system_prompt_template=prompt.get("system", ""),
        user_prompt_template=prompt.get("user", ""),
    )


def interpolate_prompt(
    system_template: str,
    user_template: str,
    state: dict[str, Any],
) -> tuple[str, str]:
    """Interpolates {variable} patterns in prompt templates using state values.

    Auto-extracts variable names from {variable} patterns in both
    system and user templates, then resolves them from state.

    Args:
        system_template: System prompt template string.
        user_template: User prompt template string.
        state: Workflow state dictionary.

    Returns:
        Tuple of (interpolated_system_prompt, interpolated_user_prompt).

    Raises:
        LLMHandlerConfigError: If template variables cannot be resolved from state.
    """
    system_vars = re.findall(r"\{(\w+)\}", system_template)
    user_vars = re.findall(r"\{(\w+)\}", user_template)
    keys = list(dict.fromkeys(system_vars + user_vars))

    input_values = {key: state.get(key, "") for key in keys}

    try:
        system_prompt = system_template.format(**input_values)
        user_prompt = user_template.format(**input_values)
    except KeyError as e:
        msg = f"Missing key in state for prompt interpolation: {e}"
        raise LLMHandlerConfigError(msg) from e

    return system_prompt, user_prompt


def build_messages(system_prompt: str, user_prompt: str) -> list[dict[str, str]]:
    """Builds the standard messages list for litellm.completion.

    Args:
        system_prompt: Interpolated system prompt.
        user_prompt: Interpolated user prompt.

    Returns:
        List of message dicts with 'role' and 'content' keys.
    """
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def report_completion_usage(
    usage: LLMTokenUsage | None,
    litellm_model: str,
    provider: str,
) -> None:
    """Reports port-level :class:`LLMTokenUsage` to TraceContext if active.

    Args:
        usage: Structured token usage returned by :class:`LLMProviderPort`.
            ``None`` is allowed and results in a no-op.
        litellm_model: Full litellm model string (e.g. ``"openai/gpt-4o"``).
        provider: Provider name (e.g. ``"openai"``).
    """
    if usage is None:
        return
    from yagra.application.use_cases.trace_collector import (
        TraceContext,  # noqa: PLC0415
    )

    ctx = TraceContext.current()
    if ctx is not None:
        ctx.record_llm_call(
            model=litellm_model,
            provider=provider,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens,
        )


def report_streaming_usage(
    usage: LLMTokenUsage | None,
    litellm_model: str,
    provider: str,
) -> None:
    """Best-effort streaming token usage reporting from port-level dataclass.

    The port contract places ``usage`` on the terminal
    :class:`LLMStreamChunk`. Callers accumulate it across the stream and
    invoke this function once when the generator exits.

    Args:
        usage: Structured token usage from the terminal chunk (``None`` if
            the provider did not expose it).
        litellm_model: Full litellm model string.
        provider: Provider name.
    """
    try:
        if usage is None:
            return
        from yagra.application.use_cases.trace_collector import (
            TraceContext,  # noqa: PLC0415
        )

        ctx = TraceContext.current()
        if ctx is not None:
            ctx.record_llm_call(
                model=litellm_model,
                provider=provider,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                total_tokens=usage.total_tokens,
            )
    except Exception:  # noqa: BLE001
        pass  # token reporting is best-effort; never break the stream


def resolve_handler_provider(
    provider_arg: LLMProviderPort | None,
    params_provider: Any,
) -> LLMProviderPort:
    """Resolves the provider instance following the judge handler pattern.

    1. If ``provider_arg`` is a port instance, use it as-is (DI / test).
    2. Else take ``params_provider`` string or default to ``"litellm"`` and
       delegate to :func:`resolve_provider`.

    Args:
        provider_arg: Explicit port instance or ``None``.
        params_provider: Provider name from workflow YAML ``params``.

    Returns:
        A concrete :class:`LLMProviderPort` implementation.

    Raises:
        LLMHandlerConfigError: If ``provider_arg`` is not a port instance,
            if ``params_provider`` is not a string, or if the name is
            unknown. The error payload follows the 4-field structured
            format ``{error, message, summary, hint}``.
    """
    if provider_arg is not None:
        if not isinstance(provider_arg, LLMProviderPort):
            raise LLMHandlerConfigError(
                {
                    "error": "invalid_provider_instance",
                    "message": "provider argument does not implement LLMProviderPort",
                    "summary": {"type": type(provider_arg).__name__},
                    "hint": "Pass an LLMProviderPort implementation or omit the argument",
                }
            )
        return provider_arg

    if params_provider is None:
        name = "litellm"
    elif isinstance(params_provider, str):
        name = params_provider
    else:
        raise LLMHandlerConfigError(
            {
                "error": "invalid_provider_param",
                "message": "'provider' param must be a string",
                "summary": {"type": type(params_provider).__name__},
                "hint": "Set params.provider to 'litellm' or 'claude_agent_sdk'",
            }
        )

    # Lazy import keeps adapter modules out of the import graph until actually needed.
    from yagra.adapters.outbound.llm_providers import resolve_provider

    try:
        return resolve_provider(name)
    except ValueError as exc:
        raise LLMHandlerConfigError(
            {
                "error": "unknown_provider",
                "message": (
                    f"Unknown provider '{name}'. Available: litellm, claude_agent_sdk. "
                    "Install 'yagra[judge]' for claude_agent_sdk."
                ),
                "summary": {"provider": name},
                "hint": "Use 'litellm' or 'claude_agent_sdk'",
            }
        ) from exc


def llm_retry_loop[T](
    fn: Callable[[], T],
    effective_retry: int,
) -> T:
    """Executes fn with retry and exponential backoff.

    Retries on general exceptions and :class:`LLMProviderCallError` but
    immediately re-raises :class:`LLMHandlerCallError` (handler-layer
    errors are deterministic). :class:`LLMProviderConfigError` is converted
    to :class:`LLMHandlerConfigError` without retry (deterministic setup
    failures such as missing SDKs).

    After exhausting all retries, raises :class:`LLMHandlerCallError`.

    Args:
        fn: Callable to execute (typically wraps an LLMProviderPort call).
        effective_retry: Number of attempts (minimum 1).

    Returns:
        The return value of fn on success.

    Raises:
        LLMHandlerConfigError: If the underlying provider reports a config
            error (no retry).
        LLMHandlerCallError: If all retries are exhausted or fn raises
            LLMHandlerCallError directly.
    """
    last_error: Exception | None = None
    for attempt in range(effective_retry):
        try:
            return fn()
        except LLMHandlerCallError:
            raise
        except LLMProviderConfigError as exc:
            payload = (
                exc.args[0]
                if exc.args and isinstance(exc.args[0], dict)
                else {
                    "error": "provider_config_error",
                    "message": str(exc),
                    "summary": {},
                    "hint": "Inspect provider initialization",
                }
            )
            raise LLMHandlerConfigError(payload) from exc
        except LLMProviderCallError as exc:
            last_error = exc
            if attempt < effective_retry - 1:
                time.sleep(2**attempt)
                continue
            break
        except Exception as e:  # noqa: BLE001
            last_error = e
            if attempt < effective_retry - 1:
                time.sleep(2**attempt)
                continue
            break

    msg = f"LLM call failed after {effective_retry} attempts: {last_error}"
    raise LLMHandlerCallError(msg) from last_error


# ---------------------------------------------------------------------------
# Shared PARAMS_SCHEMA building blocks
# ---------------------------------------------------------------------------

BASE_PARAMS_SCHEMA_PROPERTIES: dict[str, Any] = {
    "prompt": {
        "oneOf": [
            {
                "type": "string",
                "description": "Prompt text. State values can be expanded using {variable_name}",
            },
            {"type": "object", "description": "Prompt dictionary in role/content format"},
            {"type": "array", "description": "List of multiple messages"},
        ],
        "description": "Prompt definition. Mutually exclusive with prompt_ref",
    },
    "prompt_ref": {
        "type": "string",
        "description": (
            "Path to the prompt file (relative to the workflow YAML). "
            "Use '#key' to select a section from a multi-prompt YAML "
            "(e.g. 'prompts/all.yaml#greet'). "
            "Nested keys use dot notation (e.g. 'prompts/all.yaml#chat.default'). "
            "Mutually exclusive with prompt"
        ),
        "examples": [
            "prompts/translate.yaml#default",
            "./prompts/summarize.md",
            "prompts/multi.yaml#chat.system",
        ],
    },
    "model": {
        "type": "object",
        "description": (
            "LLM model configuration. provider (litellm provider name) and name "
            "(model name) are required. Additional litellm parameters can be "
            "passed via kwargs"
        ),
        "properties": {
            "provider": {
                "type": "string",
                "description": "litellm provider name",
                "examples": ["openai", "anthropic", "google"],
            },
            "name": {
                "type": "string",
                "description": "Model name",
                "examples": ["gpt-4o-mini", "claude-opus-4-6", "gemini-pro"],
            },
            "kwargs": {
                "type": "object",
                "description": "Additional parameters to pass to litellm (e.g. temperature)",
            },
        },
        "required": ["provider", "name"],
    },
    "output_key": {
        "type": "string",
        "description": "State key name to store the output. Defaults to 'output'",
        "default": "output",
    },
}


def build_params_schema(
    description: str,
    extra_properties: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Builds a PARAMS_SCHEMA dict by merging base properties with handler-specific additions.

    Args:
        description: Description for the top-level schema object.
        extra_properties: Handler-specific properties to merge into the base.

    Returns:
        Complete JSON Schema dict for handler params.
    """
    properties = dict(BASE_PARAMS_SCHEMA_PROPERTIES)
    if extra_properties:
        properties.update(extra_properties)
    return {
        "type": "object",
        "description": description,
        "properties": properties,
        "required": ["model"],
        "oneOf": [
            {"required": ["prompt"]},
            {"required": ["prompt_ref"]},
        ],
    }
