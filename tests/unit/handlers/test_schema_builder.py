"""Unit tests for schema_builder module.

Unit tests for the schema_builder module that dynamically generates
Pydantic models from YAML schema definitions.
"""

import pytest
from pydantic import BaseModel, ValidationError

from yagra.handlers.schema_builder import (
    TYPE_MAP,
    SchemaYamlError,
    build_model_from_schema_yaml,
)


class TestBuildModelFromSchemaYaml:
    """Tests for build_model_from_schema_yaml."""

    # --- Success cases ---

    def test_basic_str_field(self) -> None:
        """Confirms that a model with a `str` field is correctly generated."""
        model = build_model_from_schema_yaml("name: str")
        instance = model(name="Alice")
        assert instance.name == "Alice"  # type: ignore[attr-defined]

    def test_basic_int_field(self) -> None:
        """Confirms that a model with an `int` field is correctly generated."""
        model = build_model_from_schema_yaml("age: int")
        instance = model(age=30)
        assert instance.age == 30  # type: ignore[attr-defined]

    def test_basic_float_field(self) -> None:
        """Confirms that a model with a `float` field is correctly generated."""
        model = build_model_from_schema_yaml("score: float")
        instance = model(score=3.14)
        assert instance.score == pytest.approx(3.14)  # type: ignore[attr-defined]

    def test_basic_bool_field(self) -> None:
        """Confirms that a model with a `bool` field is correctly generated."""
        model = build_model_from_schema_yaml("active: bool")
        instance = model(active=True)
        assert instance.active is True  # type: ignore[attr-defined]

    def test_multiple_fields(self) -> None:
        """Confirms that a model with multiple fields is correctly generated."""
        schema_yaml = "name: str\nage: int\nscore: float"
        model = build_model_from_schema_yaml(schema_yaml)
        instance = model(name="Bob", age=25, score=4.5)
        assert instance.name == "Bob"  # type: ignore[attr-defined]
        assert instance.age == 25  # type: ignore[attr-defined]
        assert instance.score == pytest.approx(4.5)  # type: ignore[attr-defined]

    def test_list_str_field(self) -> None:
        """Confirms that a list[str] field works correctly."""
        model = build_model_from_schema_yaml("tags: list[str]")
        instance = model(tags=["python", "ai"])
        assert instance.tags == ["python", "ai"]  # type: ignore[attr-defined]

    def test_list_int_field(self) -> None:
        """Confirms that a list[int] field works correctly."""
        model = build_model_from_schema_yaml("scores: list[int]")
        instance = model(scores=[1, 2, 3])
        assert instance.scores == [1, 2, 3]  # type: ignore[attr-defined]

    def test_dict_str_str_field(self) -> None:
        """Confirms that a dict[str, str] field works correctly."""
        model = build_model_from_schema_yaml("metadata: dict[str, str]")
        instance = model(metadata={"key": "value"})
        assert instance.metadata == {"key": "value"}  # type: ignore[attr-defined]

    def test_dict_str_int_field(self) -> None:
        """Confirms that a dict[str, int] field works correctly."""
        model = build_model_from_schema_yaml("counts: dict[str, int]")
        instance = model(counts={"a": 1, "b": 2})
        assert instance.counts == {"a": 1, "b": 2}  # type: ignore[attr-defined]

    def test_optional_str_field(self) -> None:
        """Confirms that a `str | None` field defaults to None."""
        model = build_model_from_schema_yaml("nickname: str | None")
        # Can be instantiated with default value
        instance = model()
        assert instance.nickname is None  # type: ignore[attr-defined]
        # Can be instantiated with a value
        instance2 = model(nickname="Bob")
        assert instance2.nickname == "Bob"  # type: ignore[attr-defined]

    def test_optional_int_field(self) -> None:
        """Confirms that an `int | None` field defaults to None."""
        model = build_model_from_schema_yaml("count: int | None")
        instance = model()
        assert instance.count is None  # type: ignore[attr-defined]

    def test_all_supported_types(self) -> None:
        """Confirms that a model can be generated for all supported types."""
        for type_str in TYPE_MAP:
            schema_yaml = f"field: {type_str}"
            model = build_model_from_schema_yaml(schema_yaml)
            assert issubclass(model, BaseModel)

    def test_model_validate_works(self) -> None:
        """Confirms that model_validate works correctly."""
        model = build_model_from_schema_yaml("name: str\nage: int")
        instance = model.model_validate({"name": "Alice", "age": 30})
        assert instance.name == "Alice"  # type: ignore[attr-defined]
        assert instance.age == 30  # type: ignore[attr-defined]

    def test_model_json_schema_returns_valid_schema(self) -> None:
        """Confirms that model_json_schema() returns a valid JSON Schema."""
        model = build_model_from_schema_yaml("name: str\nage: int")
        json_schema = model.model_json_schema()
        assert json_schema["type"] == "object"
        assert "name" in json_schema["properties"]
        assert "age" in json_schema["properties"]
        assert "name" in json_schema["required"]
        assert "age" in json_schema["required"]

    def test_custom_model_name(self) -> None:
        """Confirms that specifying model_name is reflected in the class name."""
        model = build_model_from_schema_yaml("name: str", model_name="PersonInfo")
        assert model.__name__ == "PersonInfo"

    def test_default_model_name(self) -> None:
        """Confirms that the default model name is DynamicSchema."""
        model = build_model_from_schema_yaml("name: str")
        assert model.__name__ == "DynamicSchema"

    def test_whitespace_in_type_is_trimmed(self) -> None:
        """Confirms that leading/trailing whitespace in type strings is trimmed."""
        model = build_model_from_schema_yaml("name:  str ")
        instance = model(name="Alice")
        assert instance.name == "Alice"  # type: ignore[attr-defined]

    # --- Error cases ---

    def test_invalid_yaml_syntax(self) -> None:
        """Confirms that SchemaYamlError is raised for invalid YAML syntax."""
        with pytest.raises(SchemaYamlError, match="Invalid YAML syntax"):
            build_model_from_schema_yaml(":\ninvalid: [yaml")

    def test_non_dict_yaml(self) -> None:
        """Confirms that SchemaYamlError is raised when YAML parse result is not a dict."""
        with pytest.raises(SchemaYamlError, match="must be a YAML mapping"):
            build_model_from_schema_yaml("- item1\n- item2")

    def test_scalar_yaml(self) -> None:
        """Confirms that SchemaYamlError is raised when YAML is a scalar value."""
        with pytest.raises(SchemaYamlError, match="must be a YAML mapping"):
            build_model_from_schema_yaml("just a string")

    def test_empty_dict(self) -> None:
        """Confirms that SchemaYamlError is raised for an empty dict."""
        with pytest.raises(SchemaYamlError, match="at least one field"):
            build_model_from_schema_yaml("{}")

    def test_unsupported_type(self) -> None:
        """Confirms that SchemaYamlError is raised for an unsupported type string."""
        with pytest.raises(SchemaYamlError, match="Unsupported type 'CustomClass'"):
            build_model_from_schema_yaml("field: CustomClass")

    def test_non_string_type_value(self) -> None:
        """Confirms that SchemaYamlError is raised when the type value is not a string."""
        with pytest.raises(SchemaYamlError, match="must be a string"):
            build_model_from_schema_yaml("field: 123")

    def test_non_string_field_name(self) -> None:
        """Confirms that SchemaYamlError is raised when the field name is not a string."""
        with pytest.raises(SchemaYamlError, match="Field name must be a string"):
            build_model_from_schema_yaml("123: str")

    def test_empty_string_input(self) -> None:
        """Confirms that SchemaYamlError is raised for empty string input."""
        with pytest.raises(SchemaYamlError, match="must be a YAML mapping"):
            build_model_from_schema_yaml("")

    def test_model_validate_rejects_invalid_data(self) -> None:
        """Confirms that model_validate on the generated model rejects invalid data."""
        model = build_model_from_schema_yaml("name: str\nage: int")
        with pytest.raises(ValidationError):
            model.model_validate({"name": "Alice", "age": "not_an_int"})

    def test_required_field_missing(self) -> None:
        """Confirms that ValidationError is raised when a required field is missing."""
        model = build_model_from_schema_yaml("name: str\nage: int")
        with pytest.raises(ValidationError):
            model.model_validate({"name": "Alice"})
