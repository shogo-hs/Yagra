"""LLM handler implementation using litellm.

This module provides a generic LLM invocation handler using litellm.
It supports over 100 LLM providers through a unified API.
"""

from typing import Any

import litellm

from yagra.handlers.errors import (
    LLMHandlerCallError,
    LLMHandlerConfigError,
    LLMHandlerError,
)
from yagra.ports.outbound.node_registry import NodeHandler


def create_llm_handler(
    retry: int = 3,
    timeout: int = 30,
) -> NodeHandler:
    """Creates an LLM invocation handler.

    Generates a handler that supports over 100 LLM providers using litellm.
    Simply specify `prompt_ref`, `model`, and `output_key` in the YAML
    definition to enable LLM invocation. Variables in the prompt template
    (e.g. ``{query}``) are automatically extracted from state.

    Args:
        retry: Number of retries on API errors (default: 3).
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
            params: Node parameters (prompt, model, output_key).

        Returns:
            dict: Response in the format {output_key: response_text}.

        Raises:
            LLMHandlerConfigError: If required parameters are missing.
            LLMHandlerCallError: If LLM invocation fails.
        """
        from yagra.handlers._llm_common import (
            build_messages,
            extract_llm_params,
            interpolate_prompt,
            llm_retry_loop,
            report_token_usage,
        )

        p = extract_llm_params(params, default_retry=retry)
        system_prompt, user_prompt = interpolate_prompt(
            p.system_prompt_template,
            p.user_prompt_template,
            state,
        )
        messages = build_messages(system_prompt, user_prompt)

        def _call() -> dict[str, Any]:
            response = litellm.completion(
                model=p.litellm_model,
                messages=messages,
                timeout=timeout,
                **p.model_kwargs,
            )

            if not response.choices:
                msg = "LLM returned empty response"
                raise LLMHandlerCallError(msg)

            content = response.choices[0].message.content
            if content is None:
                msg = "LLM returned None content"
                raise LLMHandlerCallError(msg)

            if response.usage is not None:
                report_token_usage(response.usage, p.litellm_model, p.provider)

            return {p.output_key: content}

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
