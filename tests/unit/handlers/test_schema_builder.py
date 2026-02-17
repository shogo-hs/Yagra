"""Unit tests for schema_builder module.

YAML スキーマ定義から Pydantic モデルを動的生成する
schema_builder モジュールの単体テスト。
"""

import pytest
from pydantic import BaseModel, ValidationError

from yagra.handlers.schema_builder import (
    TYPE_MAP,
    SchemaYamlError,
    build_model_from_schema_yaml,
)


class TestBuildModelFromSchemaYaml:
    """build_model_from_schema_yaml のテスト."""

    # --- 正常系 ---

    def test_basic_str_field(self) -> None:
        """`str` フィールドのモデルが正しく生成されること."""
        model = build_model_from_schema_yaml("name: str")
        instance = model(name="Alice")
        assert instance.name == "Alice"  # type: ignore[attr-defined]

    def test_basic_int_field(self) -> None:
        """`int` フィールドのモデルが正しく生成されること."""
        model = build_model_from_schema_yaml("age: int")
        instance = model(age=30)
        assert instance.age == 30  # type: ignore[attr-defined]

    def test_basic_float_field(self) -> None:
        """`float` フィールドのモデルが正しく生成されること."""
        model = build_model_from_schema_yaml("score: float")
        instance = model(score=3.14)
        assert instance.score == pytest.approx(3.14)  # type: ignore[attr-defined]

    def test_basic_bool_field(self) -> None:
        """`bool` フィールドのモデルが正しく生成されること."""
        model = build_model_from_schema_yaml("active: bool")
        instance = model(active=True)
        assert instance.active is True  # type: ignore[attr-defined]

    def test_multiple_fields(self) -> None:
        """複数フィールドのモデルが正しく生成されること."""
        schema_yaml = "name: str\nage: int\nscore: float"
        model = build_model_from_schema_yaml(schema_yaml)
        instance = model(name="Bob", age=25, score=4.5)
        assert instance.name == "Bob"  # type: ignore[attr-defined]
        assert instance.age == 25  # type: ignore[attr-defined]
        assert instance.score == pytest.approx(4.5)  # type: ignore[attr-defined]

    def test_list_str_field(self) -> None:
        """list[str] フィールドが正しく動作すること."""
        model = build_model_from_schema_yaml("tags: list[str]")
        instance = model(tags=["python", "ai"])
        assert instance.tags == ["python", "ai"]  # type: ignore[attr-defined]

    def test_list_int_field(self) -> None:
        """list[int] フィールドが正しく動作すること."""
        model = build_model_from_schema_yaml("scores: list[int]")
        instance = model(scores=[1, 2, 3])
        assert instance.scores == [1, 2, 3]  # type: ignore[attr-defined]

    def test_dict_str_str_field(self) -> None:
        """dict[str, str] フィールドが正しく動作すること."""
        model = build_model_from_schema_yaml("metadata: dict[str, str]")
        instance = model(metadata={"key": "value"})
        assert instance.metadata == {"key": "value"}  # type: ignore[attr-defined]

    def test_dict_str_int_field(self) -> None:
        """dict[str, int] フィールドが正しく動作すること."""
        model = build_model_from_schema_yaml("counts: dict[str, int]")
        instance = model(counts={"a": 1, "b": 2})
        assert instance.counts == {"a": 1, "b": 2}  # type: ignore[attr-defined]

    def test_optional_str_field(self) -> None:
        """`str | None` フィールドがデフォルト None になること."""
        model = build_model_from_schema_yaml("nickname: str | None")
        # デフォルト値で生成可能
        instance = model()
        assert instance.nickname is None  # type: ignore[attr-defined]
        # 値を指定して生成
        instance2 = model(nickname="Bob")
        assert instance2.nickname == "Bob"  # type: ignore[attr-defined]

    def test_optional_int_field(self) -> None:
        """`int | None` フィールドがデフォルト None になること."""
        model = build_model_from_schema_yaml("count: int | None")
        instance = model()
        assert instance.count is None  # type: ignore[attr-defined]

    def test_all_supported_types(self) -> None:
        """全サポート型でモデルが生成できること."""
        for type_str in TYPE_MAP:
            schema_yaml = f"field: {type_str}"
            model = build_model_from_schema_yaml(schema_yaml)
            assert issubclass(model, BaseModel)

    def test_model_validate_works(self) -> None:
        """model_validate が正しく動作すること."""
        model = build_model_from_schema_yaml("name: str\nage: int")
        instance = model.model_validate({"name": "Alice", "age": 30})
        assert instance.name == "Alice"  # type: ignore[attr-defined]
        assert instance.age == 30  # type: ignore[attr-defined]

    def test_model_json_schema_returns_valid_schema(self) -> None:
        """model_json_schema() が妥当な JSON Schema を返すこと."""
        model = build_model_from_schema_yaml("name: str\nage: int")
        json_schema = model.model_json_schema()
        assert json_schema["type"] == "object"
        assert "name" in json_schema["properties"]
        assert "age" in json_schema["properties"]
        assert "name" in json_schema["required"]
        assert "age" in json_schema["required"]

    def test_custom_model_name(self) -> None:
        """model_name を指定するとクラス名に反映されること."""
        model = build_model_from_schema_yaml("name: str", model_name="PersonInfo")
        assert model.__name__ == "PersonInfo"

    def test_default_model_name(self) -> None:
        """デフォルトのモデル名が DynamicSchema であること."""
        model = build_model_from_schema_yaml("name: str")
        assert model.__name__ == "DynamicSchema"

    def test_whitespace_in_type_is_trimmed(self) -> None:
        """型文字列の前後の空白がトリムされること."""
        model = build_model_from_schema_yaml("name:  str ")
        instance = model(name="Alice")
        assert instance.name == "Alice"  # type: ignore[attr-defined]

    # --- 異常系 ---

    def test_invalid_yaml_syntax(self) -> None:
        """不正な YAML 構文で SchemaYamlError が送出されること."""
        with pytest.raises(SchemaYamlError, match="Invalid YAML syntax"):
            build_model_from_schema_yaml(":\ninvalid: [yaml")

    def test_non_dict_yaml(self) -> None:
        """YAML のパース結果が dict でない場合に SchemaYamlError が送出されること."""
        with pytest.raises(SchemaYamlError, match="must be a YAML mapping"):
            build_model_from_schema_yaml("- item1\n- item2")

    def test_scalar_yaml(self) -> None:
        """YAML がスカラー値の場合に SchemaYamlError が送出されること."""
        with pytest.raises(SchemaYamlError, match="must be a YAML mapping"):
            build_model_from_schema_yaml("just a string")

    def test_empty_dict(self) -> None:
        """空の dict で SchemaYamlError が送出されること."""
        with pytest.raises(SchemaYamlError, match="at least one field"):
            build_model_from_schema_yaml("{}")

    def test_unsupported_type(self) -> None:
        """未サポートの型文字列で SchemaYamlError が送出されること."""
        with pytest.raises(SchemaYamlError, match="Unsupported type 'CustomClass'"):
            build_model_from_schema_yaml("field: CustomClass")

    def test_non_string_type_value(self) -> None:
        """型の値が文字列でない場合に SchemaYamlError が送出されること."""
        with pytest.raises(SchemaYamlError, match="must be a string"):
            build_model_from_schema_yaml("field: 123")

    def test_non_string_field_name(self) -> None:
        """フィールド名が文字列でない場合に SchemaYamlError が送出されること."""
        with pytest.raises(SchemaYamlError, match="Field name must be a string"):
            build_model_from_schema_yaml("123: str")

    def test_empty_string_input(self) -> None:
        """空文字列入力で SchemaYamlError が送出されること."""
        with pytest.raises(SchemaYamlError, match="must be a YAML mapping"):
            build_model_from_schema_yaml("")

    def test_model_validate_rejects_invalid_data(self) -> None:
        """生成モデルの model_validate が不正データを拒否すること."""
        model = build_model_from_schema_yaml("name: str\nage: int")
        with pytest.raises(ValidationError):
            model.model_validate({"name": "Alice", "age": "not_an_int"})

    def test_required_field_missing(self) -> None:
        """必須フィールドが欠けている場合に ValidationError が出ること."""
        model = build_model_from_schema_yaml("name: str\nage: int")
        with pytest.raises(ValidationError):
            model.model_validate({"name": "Alice"})
