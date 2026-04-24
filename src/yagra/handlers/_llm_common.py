"""Shared utilities for LLM handler implementations.

Extracts common parameter validation, prompt interpolation, retry logic,
and token usage reporting used across llm, structured_llm, and streaming_llm handlers.
"""

import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from yagra.handlers.errors import LLMHandlerCallError, LLMHandlerConfigError


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


def report_token_usage(usage: Any, litellm_model: str, provider: str) -> None:
    """Reports token usage to TraceContext if tracing is active.

    Args:
        usage: Response usage object with prompt_tokens, completion_tokens,
            and total_tokens attributes.
        litellm_model: Full litellm model string (e.g. 'openai/gpt-4o').
        provider: Provider name (e.g. 'openai').
    """
    from yagra.application.use_cases.trace_collector import (
        TraceContext,  # noqa: PLC0415
    )

    ctx = TraceContext.current()
    if ctx is not None:
        ctx.record_llm_call(
            model=litellm_model,
            provider=provider,
            prompt_tokens=usage.prompt_tokens or 0,
            completion_tokens=usage.completion_tokens or 0,
            total_tokens=usage.total_tokens or 0,
        )


def report_streaming_token_usage(response: Any, litellm_model: str, provider: str) -> None:
    """Best-effort token usage reporting for streaming responses.

    Attempts to extract usage from the streaming response object after
    the stream is fully consumed. Never raises exceptions.

    Args:
        response: Litellm streaming response object.
        litellm_model: Full litellm model string.
        provider: Provider name.
    """
    try:
        usage = getattr(response, "usage", None) or getattr(response, "_usage", None)
        if usage is not None:
            from yagra.application.use_cases.trace_collector import (
                TraceContext,  # noqa: PLC0415
            )

            ctx = TraceContext.current()
            if ctx is not None:
                ctx.record_llm_call(
                    model=litellm_model,
                    provider=provider,
                    prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                    completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
                    total_tokens=getattr(usage, "total_tokens", 0) or 0,
                )
    except Exception:  # noqa: BLE001
        pass  # token reporting is best-effort; never break the stream


def llm_retry_loop[T](
    fn: Callable[[], T],
    effective_retry: int,
) -> T:
    """Executes fn with retry and exponential backoff.

    Retries on general exceptions but immediately re-raises LLMHandlerCallError.
    After exhausting all retries, raises LLMHandlerCallError.

    Args:
        fn: Callable to execute (typically wraps litellm.completion and response handling).
        effective_retry: Number of attempts.

    Returns:
        The return value of fn on success.

    Raises:
        LLMHandlerCallError: If all retries are exhausted or fn raises LLMHandlerCallError.
    """
    last_error = None
    for attempt in range(effective_retry):
        try:
            return fn()
        except LLMHandlerCallError:
            raise
        except Exception as e:  # noqa: BLE001
            last_error = e
            if attempt < effective_retry - 1:
                wait_time = 2**attempt
                time.sleep(wait_time)
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
