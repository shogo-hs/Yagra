"""Integration tests for structured LLM handler with dynamic schema_yaml.

schema_yaml による動的スキーマ生成を使った structured_llm ハンドラーが
YAML ワークフローと統合して正しく動作することを検証する。
"""

import json
import tempfile
from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import yagra.handlers.structured_llm_handler as slm_module


class TestDynamicSchemaIntegration:
    """動的スキーマ（schema_yaml）を使ったワークフロー結合テスト."""

    @pytest.fixture(autouse=True)
    def _reset_litellm_global(self) -> Generator[None, None, None]:
        """各テスト前後に structured_llm_handler のグローバル litellm を管理する."""
        original = slm_module.litellm
        slm_module.litellm = None
        yield
        # テスト後は元の値に戻す
        slm_module.litellm = original

    def test_workflow_with_schema_yaml_basic(self) -> None:
        """schema_yaml を YAML に定義して動的モデルで実行できること."""
        prompts_yaml = """\
extract:
  system: "Extract person info as JSON"
  user: "Extract person from: {text}"
"""

        workflow_yaml = """\
version: "1.0"
start_at: "extract"
end_at:
  - "extract"

nodes:
  - id: "extract"
    handler: "structured_llm"
    params:
      schema_yaml: |
        name: str
        age: int
      prompt_ref: "prompts.yaml#extract"
      model:
        provider: "openai"
        name: "gpt-4o"
      output_key: "person"

edges: []
params:
  text: ""
"""

        with tempfile.TemporaryDirectory() as tmpdir:
            workflow_path = Path(tmpdir) / "workflow.yaml"
            prompts_path = Path(tmpdir) / "prompts.yaml"
            workflow_path.write_text(workflow_yaml)
            prompts_path.write_text(prompts_yaml)

            with patch.object(slm_module, "litellm") as mock_litellm:
                mock_response = MagicMock()
                mock_response.choices = [
                    MagicMock(message=MagicMock(content=json.dumps({"name": "Alice", "age": 30})))
                ]
                mock_litellm.completion.return_value = mock_response

                from yagra import Yagra
                from yagra.handlers import create_structured_llm_handler

                # schema 引数なし → params.schema_yaml から動的生成
                handler = create_structured_llm_handler(retry=1, timeout=10)
                registry = {"structured_llm": handler}

                yagra = Yagra.from_workflow(workflow_path, registry)
                result = yagra.invoke({"text": "Alice is 30 years old."})

            assert "person" in result
            assert result["person"].name == "Alice"
            assert result["person"].age == 30

    def test_workflow_with_schema_yaml_list_type(self) -> None:
        """schema_yaml でコレクション型を使ったワークフローが動作すること."""
        prompts_yaml = """\
extract_entities:
  system: "Extract entities as JSON"
  user: "{text}"
"""

        workflow_yaml = """\
version: "1.0"
start_at: "extract"
end_at:
  - "extract"

nodes:
  - id: "extract"
    handler: "structured_llm"
    params:
      schema_yaml: |
        names: list[str]
        locations: list[str]
      prompt_ref: "prompts.yaml#extract_entities"
      model:
        provider: "openai"
        name: "gpt-4o"
      output_key: "entities"

edges: []
params:
  text: ""
"""

        with tempfile.TemporaryDirectory() as tmpdir:
            workflow_path = Path(tmpdir) / "workflow.yaml"
            prompts_path = Path(tmpdir) / "prompts.yaml"
            workflow_path.write_text(workflow_yaml)
            prompts_path.write_text(prompts_yaml)

            with patch.object(slm_module, "litellm") as mock_litellm:
                mock_response = MagicMock()
                mock_response.choices = [
                    MagicMock(
                        message=MagicMock(
                            content=json.dumps(
                                {
                                    "names": ["Alice", "Bob"],
                                    "locations": ["Tokyo", "Osaka"],
                                }
                            )
                        )
                    )
                ]
                mock_litellm.completion.return_value = mock_response

                from yagra import Yagra
                from yagra.handlers import create_structured_llm_handler

                handler = create_structured_llm_handler(retry=1, timeout=10)
                registry = {"structured_llm": handler}

                yagra = Yagra.from_workflow(workflow_path, registry)
                result = yagra.invoke({"text": "Alice and Bob visited Tokyo and Osaka."})

            assert "entities" in result
            assert result["entities"].names == ["Alice", "Bob"]
            assert result["entities"].locations == ["Tokyo", "Osaka"]

    def test_workflow_with_schema_yaml_mixed_types(self) -> None:
        """schema_yaml で複合型（プリミティブ + コレクション）が動作すること."""
        prompts_yaml = """\
extract:
  system: "Extract person info as JSON"
  user: "Extract from: {text}"
"""

        workflow_yaml = """\
version: "1.0"
start_at: "extract"
end_at:
  - "extract"

nodes:
  - id: "extract"
    handler: "structured_llm"
    params:
      schema_yaml: |
        name: str
        age: int
        hobbies: list[str]
      prompt_ref: "prompts.yaml#extract"
      model:
        provider: "openai"
        name: "gpt-4o"
      output_key: "person"

edges: []
params:
  text: ""
"""

        with tempfile.TemporaryDirectory() as tmpdir:
            workflow_path = Path(tmpdir) / "workflow.yaml"
            prompts_path = Path(tmpdir) / "prompts.yaml"
            workflow_path.write_text(workflow_yaml)
            prompts_path.write_text(prompts_yaml)

            with patch.object(slm_module, "litellm") as mock_litellm:
                mock_response = MagicMock()
                mock_response.choices = [
                    MagicMock(
                        message=MagicMock(
                            content=json.dumps(
                                {
                                    "name": "Charlie",
                                    "age": 28,
                                    "hobbies": ["reading", "gaming"],
                                }
                            )
                        )
                    )
                ]
                mock_litellm.completion.return_value = mock_response

                from yagra import Yagra
                from yagra.handlers import create_structured_llm_handler

                handler = create_structured_llm_handler(retry=1, timeout=10)
                registry = {"structured_llm": handler}

                yagra = Yagra.from_workflow(workflow_path, registry)
                result = yagra.invoke({"text": "Charlie, 28, likes reading and gaming."})

            assert result["person"].name == "Charlie"
            assert result["person"].age == 28
            assert result["person"].hobbies == ["reading", "gaming"]
