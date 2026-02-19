"""LLM handler implementation using litellm.

This module provides a generic LLM invocation handler using litellm.
It supports over 100 LLM providers through a unified API.
"""

import re
import time
from typing import TYPE_CHECKING, Any

from yagra.ports.outbound.node_registry import NodeHandler

if TYPE_CHECKING:
    import litellm  # type: ignore[import-not-found]
else:
    litellm = None  # type: ignore[assignment]


class LLMHandlerError(Exception):
    """Base exception class for LLM handler execution errors."""

    pass


class LLMHandlerConfigError(LLMHandlerError):
    """Configuration error for LLM handler."""

    pass


class LLMHandlerCallError(LLMHandlerError):
    """Error during LLM invocation."""

    pass


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

    Raises:
        ImportError: If litellm is not installed.

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
    # Import litellm (stored as global variable)
    global litellm
    if litellm is None:
        try:
            import litellm
        except ImportError as e:
            msg = (
                "litellm is not installed. "
                "Install with: pip install 'yagra[llm]' or uv add --optional llm yagra"
            )
            raise ImportError(msg) from e

    def handler(state: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
        """Invokes the LLM and returns the response.

        Args:
            state: Workflow state dictionary.
            params: Node parameters (prompt, model, input_keys, output_key).

        Returns:
            dict: Response in the format {output_key: response_text}.

        Raises:
            LLMHandlerConfigError: If required parameters are missing.
            LLMHandlerCallError: If LLM invocation fails.
        """
        # 1. Extract and validate parameters
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

        output_key = params.get("output_key", "output")

        # 2. Interpolate variables into the prompt
        system_prompt = prompt.get("system", "")
        user_prompt_template = prompt.get("user", "")

        # If input_keys is explicitly specified, use it (backward compatibility);
        # otherwise auto-extract {variable} patterns from the prompt template
        explicit_keys = params.get("input_keys")
        keys = (
            explicit_keys
            if explicit_keys is not None
            else re.findall(r"\{(\w+)\}", user_prompt_template)
        )

        # Retrieve input values from state
        input_values = {key: state.get(key, "") for key in keys}

        # Replace {variable} format variables
        try:
            user_prompt = user_prompt_template.format(**input_values)
        except KeyError as e:
            msg = f"Missing key in state for prompt interpolation: {e}"
            raise LLMHandlerConfigError(msg) from e

        # 3. LLM invocation (with retry)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        model_kwargs = model.get("kwargs", {})
        litellm_model = f"{provider}/{model_name}"

        last_error = None
        for attempt in range(retry):
            try:
                response = litellm.completion(
                    model=litellm_model,
                    messages=messages,
                    timeout=timeout,
                    **model_kwargs,
                )

                if not response.choices:
                    msg = "LLM returned empty response"
                    raise LLMHandlerCallError(msg)

                content = response.choices[0].message.content
                if content is None:
                    msg = "LLM returned None content"
                    raise LLMHandlerCallError(msg)

                return {output_key: content}

            except LLMHandlerCallError:
                # LLM response errors are raised immediately without retry
                raise
            except Exception as e:
                last_error = e
                if attempt < retry - 1:
                    wait_time = 2**attempt
                    time.sleep(wait_time)
                    continue
                break

        msg = f"LLM call failed after {retry} attempts: {last_error}"
        raise LLMHandlerCallError(msg) from last_error

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
            "description": "Path to the prompt file (relative or absolute path from the workflow YAML). Mutually exclusive with prompt",
            "examples": ["prompts/translate.txt", "./prompts/summarize.md"],
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
        "input_keys": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Explicit state keys to pass to the prompt. Auto-extracted from {variable_name} in the prompt template if omitted",
            "examples": [["text"], ["input", "context"]],
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
