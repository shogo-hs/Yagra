"""Structured output LLM handler using litellm and Pydantic.

This module provides an LLM handler that returns type-safe structured data
by parsing LLM responses with a Pydantic model.
"""

import json
from typing import Any

import litellm
from pydantic import BaseModel, ValidationError

from yagra.handlers.errors import LLMHandlerCallError, LLMHandlerConfigError
from yagra.handlers.schema_builder import build_model_from_schema_yaml
from yagra.ports.outbound.node_registry import NodeHandler


def create_structured_llm_handler(
    schema: type[BaseModel] | None = None,
    retry: int = 3,
    timeout: int = 30,
) -> NodeHandler:
    r"""Creates a structured output LLM handler with Pydantic model validation.

    Generates a handler that calls LLM via litellm and parses the response
    into a Pydantic model instance. Instructs the LLM to return JSON and
    validates with the specified schema.

    Two ways to specify the schema:

    1. **Static schema**: Pass a Pydantic BaseModel subclass to the ``schema`` argument.
    2. **Dynamic schema**: Omit ``schema`` and define in flat ``key: type`` format
       in ``params.schema_yaml`` of the workflow YAML.

    Dynamic schema YAML example::

        name: str
        age: int
        tags: list[str]

    Args:
        schema: Pydantic BaseModel subclass. If omitted, dynamically generates
            the model from ``params["schema_yaml"]`` at runtime.
        retry: Number of retries on API errors (default: 3).
        timeout: Timeout in seconds (default: 30).

    Returns:
        NodeHandler: Handler function that takes (state, params) and returns a dict.
            The value of output_key will be a Pydantic model instance.

    Examples:
        Static schema specification:

        >>> from pydantic import BaseModel
        >>> class UserInfo(BaseModel):
        ...     name: str
        ...     age: int
        >>> handler = create_structured_llm_handler(schema=UserInfo, retry=3, timeout=30)

        Dynamic schema (schema_yaml specified in params):

        >>> handler = create_structured_llm_handler()  # schema=None
        >>> # Resolved at runtime with params["schema_yaml"] = "name: str\\nage: int"

        YAML definition example:

        .. code-block:: yaml

            nodes:
              - id: "extract"
                handler: "structured_llm"
                params:
                  schema_yaml: |
                    name: str
                    age: int
                  prompt:
                    system: "Extract user info as JSON"
                    user: "{text}"
                  model:
                    provider: "openai"
                    name: "gpt-4o"
                  output_key: "user_info"
    """

    def handler(state: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
        """Calls the LLM and returns a validated Pydantic model instance.

        Calls the LLM in JSON output mode and parses the response using
        the schema specified in create_structured_llm_handler or
        dynamically generated from params["schema_yaml"].

        Args:
            state: Workflow state dictionary.
            params: Node parameters (prompt, model, schema_yaml, output_key, etc.).

        Returns:
            Dictionary in the format {output_key: schema_instance}.
            The value is a validated Pydantic model instance.

        Raises:
            LLMHandlerConfigError: If required parameters are missing or invalid.
            LLMHandlerCallError: If LLM invocation or JSON parse/validation fails.
            SchemaYamlError: If parsing schema_yaml or generating the model fails.
        """
        from yagra.handlers._llm_common import (
            build_messages,
            extract_llm_params,
            interpolate_prompt,
            llm_retry_loop,
            report_token_usage,
        )

        # 0. Resolve schema (static > dynamic)
        resolved_schema: type[BaseModel]
        if schema is not None:
            resolved_schema = schema
        else:
            schema_yaml = params.get("schema_yaml")
            if not schema_yaml:
                msg = "Either 'schema' argument or 'schema_yaml' param is required"
                raise LLMHandlerConfigError(msg)
            resolved_schema = build_model_from_schema_yaml(schema_yaml)

        p = extract_llm_params(params, default_retry=retry)
        system_prompt, user_prompt = interpolate_prompt(
            p.system_prompt_template,
            p.user_prompt_template,
            state,
        )

        # Append JSON schema instruction to system prompt
        json_system_prompt = (
            f"{system_prompt}\n\nRespond with valid JSON only. "
            f"The JSON must conform to the following schema:\n"
            f"{json.dumps(resolved_schema.model_json_schema(), ensure_ascii=False)}"
        ).strip()

        messages = build_messages(json_system_prompt, user_prompt)

        # Force response_format=json_object unless explicitly overridden
        model_kwargs = dict(p.model_kwargs)
        if "response_format" not in model_kwargs:
            model_kwargs["response_format"] = {"type": "json_object"}

        def _call() -> dict[str, Any]:
            response = litellm.completion(
                model=p.litellm_model,
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

            # JSON parse and Pydantic validation
            try:
                instance = resolved_schema.model_validate_json(content)
            except (ValidationError, ValueError) as e:
                msg = f"Failed to parse LLM response as {resolved_schema.__name__}: {e}"
                raise LLMHandlerCallError(msg) from e

            if response.usage is not None:
                report_token_usage(response.usage, p.litellm_model, p.provider)

            return {p.output_key: instance}

        return llm_retry_loop(_call, p.effective_retry)

    return handler


STRUCTURED_LLM_HANDLER_PARAMS_SCHEMA: dict = {
    "type": "object",
    "description": "Parameters for the Pydantic structured output handler created by create_structured_llm_handler",
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
            "description": "LLM model configuration. provider and name are required. Additional parameters can be passed via kwargs",
            "properties": {
                "provider": {"type": "string", "examples": ["openai", "anthropic"]},
                "name": {"type": "string", "examples": ["gpt-4o-mini", "claude-opus-4-6"]},
                "kwargs": {"type": "object"},
            },
            "required": ["provider", "name"],
        },
        "output_key": {
            "type": "string",
            "description": "State key name to store the structured output. Defaults to 'output'",
            "default": "output",
        },
        "schema_yaml": {
            "type": "string",
            "description": "Field definitions for the Pydantic model. Write 'field_name: type' separated by newlines. Supported types: str, int, float, bool, list, dict",
            "examples": ["name: str\nage: int\ncity: str", "title: str\nsummary: str\ntags: list"],
        },
    },
    "required": ["model"],
    "oneOf": [
        {"required": ["prompt"]},
        {"required": ["prompt_ref"]},
    ],
}
