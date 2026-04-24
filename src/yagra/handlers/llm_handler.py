"""LLM handler implementation routed through :class:`LLMProviderPort`.

This module provides a generic LLM invocation handler that delegates all
LLM calls to an :class:`LLMProviderPort` implementation. Callers may
inject a concrete provider (dependency injection) or let the workflow YAML
select one by name via ``params.provider``. No litellm import lives here
anymore — the adapter layer owns that boundary.
"""

from typing import Any

from yagra.handlers.errors import (
    LLMHandlerCallError,
    LLMHandlerConfigError,
    LLMHandlerError,
)
from yagra.ports.outbound.llm_provider import LLMProviderPort
from yagra.ports.outbound.node_registry import NodeHandler


def create_llm_handler(
    provider: LLMProviderPort | None = None,
    retry: int = 3,
    timeout: int = 30,
) -> NodeHandler:
    """Creates an LLM invocation handler routed through :class:`LLMProviderPort`.

    Generates a handler that delegates text completion to any
    :class:`LLMProviderPort` implementation — typically
    :class:`~yagra.adapters.outbound.llm_providers.litellm_provider.LiteLLMProvider`
    which supports 100+ upstream providers. Simply specify ``prompt_ref``,
    ``model``, and ``output_key`` in the YAML definition to enable LLM
    invocation. Variables in the prompt template (e.g. ``{query}``) are
    automatically extracted from state.

    Hybrid signature: pass an explicit ``provider`` for dependency
    injection (e.g. tests), or omit it and let the handler resolve one
    from ``params["provider"]`` (default ``"litellm"``).

    Args:
        provider: Explicit provider instance. When ``None``, resolved from
            ``params["provider"]`` (default ``"litellm"``).
        retry: Number of retries on transient errors (default: 3).
        timeout: Timeout in seconds (default: 30).

    Returns:
        NodeHandler: Handler function that takes (state, params) and returns a dict.

    Examples:
        Basic usage:

        >>> handler = create_llm_handler(retry=3, timeout=30)
        >>> state = {"query": "Hello"}
        >>> params = {
        ...     "prompt": {"system": "You are a helpful assistant", "user": "{query}"},
        ...     "model": {"provider": "openai", "name": "gpt-4", "kwargs": {"temperature": 0.7}},
        ...     "output_key": "response",
        ... }
        >>> result = handler(state, params)
        >>> print(result["response"])  # LLM response

        YAML definition example:

        .. code-block:: yaml

            nodes:
              - id: "chat"
                handler: "llm"
                params:
                  prompt_ref: "prompts/chat.yaml#system"
                  model:
                    provider: "openai"
                    name: "gpt-4"
                    kwargs:
                      temperature: 0.7
                  output_key: "response"
    """

    def handler(state: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
        """Invokes the LLM and returns the response.

        Args:
            state: Workflow state dictionary.
            params: Node parameters (prompt, model, provider, output_key).

        Returns:
            dict: Response in the format {output_key: response_text}.

        Raises:
            LLMHandlerConfigError: If required parameters are missing or
                if ``params["provider"]`` is unknown.
            LLMHandlerCallError: If LLM invocation fails.
        """
        from yagra.handlers._llm_common import (
            extract_llm_params,
            interpolate_prompt,
            llm_retry_loop,
            report_completion_usage,
            resolve_handler_provider,
        )

        p = extract_llm_params(params, default_retry=retry)
        system_prompt, user_prompt = interpolate_prompt(
            p.system_prompt_template,
            p.user_prompt_template,
            state,
        )

        resolved_provider = resolve_handler_provider(provider, params.get("provider"))

        def _call() -> dict[str, Any]:
            completion = resolved_provider.complete(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=p.litellm_model,
                timeout=timeout,
                **p.model_kwargs,
            )
            report_completion_usage(completion.usage, p.litellm_model, p.provider)
            return {p.output_key: completion.content}

        return llm_retry_loop(_call, p.effective_retry)

    return handler


LLM_HANDLER_PARAMS_SCHEMA: dict = {
    "type": "object",
    "description": "Parameters for the LLM text output handler created by create_llm_handler",
    "properties": {
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
            "description": "LLM model configuration. provider (litellm provider name) and name (model name) are required. Additional litellm parameters can be passed via kwargs",
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
            "description": "State key name to store the LLM output. Defaults to 'output'",
            "default": "output",
            "examples": ["translation", "summary", "result"],
        },
        "provider": {
            "type": "string",
            "description": (
                "LLMProviderPort adapter to route calls through. Defaults to 'litellm'. "
                "Use 'claude_agent_sdk' for the Claude Agent SDK (requires yagra[judge])."
            ),
            "enum": ["litellm", "claude_agent_sdk"],
            "default": "litellm",
        },
    },
    "required": ["model"],
    "oneOf": [
        {"required": ["prompt"]},
        {"required": ["prompt_ref"]},
    ],
}


__all__ = [
    "LLM_HANDLER_PARAMS_SCHEMA",
    "LLMHandlerCallError",
    "LLMHandlerConfigError",
    "LLMHandlerError",
    "create_llm_handler",
]
