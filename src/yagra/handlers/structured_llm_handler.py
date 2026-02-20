"""Structured output LLM handler using litellm and Pydantic.

This module provides an LLM handler that returns type-safe structured data
by parsing LLM responses with a Pydantic model.
"""

import json
import re
import time
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ValidationError

from yagra.handlers.llm_handler import LLMHandlerCallError, LLMHandlerConfigError
from yagra.handlers.schema_builder import build_model_from_schema_yaml
from yagra.ports.outbound.node_registry import NodeHandler

if TYPE_CHECKING:
    import litellm  # type: ignore[import-not-found]
else:
    litellm = None  # type: ignore[assignment]


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

    Raises:
        ImportError: If litellm is not installed.

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
        system_prompt_template = prompt.get("system", "")
        user_prompt_template = prompt.get("user", "")

        # If input_keys is explicitly specified, use it (backward compatibility);
        # otherwise auto-extract {variable} patterns from both system and user templates
        explicit_keys = params.get("input_keys")
        if explicit_keys is not None:
            keys = explicit_keys
        else:
            system_vars = re.findall(r"\{(\w+)\}", system_prompt_template)
            user_vars = re.findall(r"\{(\w+)\}", user_prompt_template)
            keys = list(dict.fromkeys(system_vars + user_vars))

        # Retrieve input values from state
        input_values = {key: state.get(key, "") for key in keys}

        # Replace {variable} format variables in both system and user prompts
        try:
            system_prompt = system_prompt_template.format(**input_values)
            user_prompt = user_prompt_template.format(**input_values)
        except KeyError as e:
            msg = f"Missing key in state for prompt interpolation: {e}"
            raise LLMHandlerConfigError(msg) from e

        # 3. Append a system prompt that encourages JSON output
        json_system_prompt = (
            f"{system_prompt}\n\nRespond with valid JSON only. "
            f"The JSON must conform to the following schema:\n"
            f"{json.dumps(resolved_schema.model_json_schema(), ensure_ascii=False)}"
        ).strip()

        messages = [
            {"role": "system", "content": json_system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        # 4. Retrieve model.kwargs (response_format defaults to json_object)
        model_kwargs = dict(model.get("kwargs", {}))
        if "response_format" not in model_kwargs:
            model_kwargs["response_format"] = {"type": "json_object"}

        litellm_model = f"{provider}/{model_name}"

        # 5. LLM invocation (with retry)
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

                # 6. JSON parse and Pydantic validation
                try:
                    instance = resolved_schema.model_validate_json(content)
                except (ValidationError, ValueError) as e:
                    msg = f"Failed to parse LLM response as {resolved_schema.__name__}: {e}"
                    raise LLMHandlerCallError(msg) from e

                return {output_key: instance}

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
        "input_keys": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Explicit state keys to pass to the prompt. Auto-extracted from {variable_name} in the prompt template if omitted",
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
