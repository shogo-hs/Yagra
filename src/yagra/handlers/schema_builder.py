r"""Utility for dynamically generating Pydantic BaseModel from YAML schema definitions.

Converts YAML entered in the Schema Settings text area of the WebUI
into a Pydantic model for use in the structured_llm handler.

YAML format example::

    name: str
    age: int
    score: float
    tags: list[str]

Examples:
    Basic usage:

    >>> from yagra.handlers.schema_builder import build_model_from_schema_yaml
    >>> schema_yaml = "name: str\\nage: int"
    >>> Model = build_model_from_schema_yaml(schema_yaml)
    >>> instance = Model(name="Alice", age=30)
    >>> print(instance)
    name='Alice' age=30
"""

from typing import Any

import yaml
from pydantic import BaseModel, create_model

# Safe type mapping dictionary. Resolves type strings to Python types
# using a whitelist approach without eval().
TYPE_MAP: dict[str, Any] = {
    # Primitive types
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    # Collection types
    "list[str]": list[str],
    "list[int]": list[int],
    "list[float]": list[float],
    "list[bool]": list[bool],
    # Dictionary types
    "dict[str, str]": dict[str, str],
    "dict[str, int]": dict[str, int],
    "dict[str, Any]": dict[str, Any],
    # Optional types
    "str | None": str | None,
    "int | None": int | None,
    "float | None": float | None,
    "bool | None": bool | None,
}


class SchemaYamlError(ValueError):
    """Exception raised when parsing schema_yaml or generating a model fails.

    Represents all errors related to dynamic schema generation, including
    YAML syntax errors, unsupported type specifications, and invalid formats.
    """


def build_model_from_schema_yaml(
    schema_yaml: str,
    model_name: str = "DynamicSchema",
) -> type[BaseModel]:
    r"""Dynamically generates a Pydantic BaseModel subclass from a YAML string.

    Accepts flat ``key: type`` format YAML, resolves each field's type using
    the safe TYPE_MAP, and generates the model with ``pydantic.create_model()``.

    Input example::

        name: str
        age: int
        tags: list[str]
        nickname: str | None

    Args:
        schema_yaml: Schema definition string in YAML format (flat key: type format).
        model_name: Class name for the generated model. Defaults to ``"DynamicSchema"``.

    Returns:
        Dynamically generated Pydantic BaseModel subclass.

    Raises:
        SchemaYamlError: Raised on YAML parse errors, unsupported types, empty fields,
            or invalid formats.

    Examples:
        >>> Model = build_model_from_schema_yaml("name: str\\nage: int")
        >>> instance = Model.model_validate({"name": "Alice", "age": 30})
        >>> instance.name
        'Alice'
    """
    # 1. Parse YAML
    try:
        parsed = yaml.safe_load(schema_yaml)
    except yaml.YAMLError as e:
        msg = f"Invalid YAML syntax in schema_yaml: {e}"
        raise SchemaYamlError(msg) from e

    # 2. Validate parse result
    if not isinstance(parsed, dict):
        msg = "schema_yaml must be a YAML mapping of field_name: type (e.g. 'name: str')"
        raise SchemaYamlError(msg)

    if len(parsed) == 0:
        msg = "schema_yaml must define at least one field"
        raise SchemaYamlError(msg)

    # 3. Resolve each field's type and build Pydantic field definitions
    field_definitions: dict[str, Any] = {}
    supported_types = ", ".join(sorted(TYPE_MAP.keys()))

    for field_name, type_str in parsed.items():
        if not isinstance(field_name, str):
            msg = f"Field name must be a string, got {type(field_name).__name__}: {field_name}"
            raise SchemaYamlError(msg)

        if not isinstance(type_str, str):
            msg = (
                f"Type for field '{field_name}' must be a string, "
                f"got {type(type_str).__name__}: {type_str}"
            )
            raise SchemaYamlError(msg)

        type_str_normalized = type_str.strip()

        resolved_type = TYPE_MAP.get(type_str_normalized)
        if resolved_type is None:
            msg = (
                f"Unsupported type '{type_str_normalized}' for field '{field_name}'. "
                f"Supported types: {supported_types}"
            )
            raise SchemaYamlError(msg)

        # Set default value to None for Optional types
        if "| None" in type_str_normalized:
            field_definitions[field_name] = (resolved_type, None)
        else:
            field_definitions[field_name] = (resolved_type, ...)

    # 4. Generate model with pydantic.create_model()
    return create_model(model_name, **field_definitions)
