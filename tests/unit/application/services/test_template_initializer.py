"""template_initializer のテスト。"""

from pathlib import Path

import pytest

from yagra.application.services.template_initializer import (
    FileAlreadyExistsError,
    TemplateNotFoundError,
    initialize_from_template,
    list_templates,
)


def test_list_templates_returns_available_templates() -> None:
    """テンプレート一覧が正しく返されることを確認する。"""
    templates = list_templates()
    assert "branch" in templates
    assert "loop" in templates
    assert "rag" in templates
    assert len(templates) >= 3


def test_initialize_from_template_creates_files(tmp_path: Path) -> None:
    """テンプレートからファイルが正しく生成されることを確認する。"""
    output_dir = tmp_path / "test-workflow"

    initialize_from_template("branch", output_dir, force=False)

    assert (output_dir / "workflow.yaml").exists()
    assert (output_dir / "prompts" / "branch_prompts.yaml").exists()


def test_initialize_from_template_validates_template_name() -> None:
    """存在しないテンプレート名でエラーになることを確認する。"""
    with pytest.raises(TemplateNotFoundError) as exc_info:
        initialize_from_template("invalid", Path("/tmp/test"), force=False)

    assert "invalid" in str(exc_info.value)
    assert "branch" in str(exc_info.value)


def test_initialize_from_template_checks_existing_files(tmp_path: Path) -> None:
    """既存ファイルがある場合に force=False でエラーになることを確認する。"""
    output_dir = tmp_path / "test-workflow"
    output_dir.mkdir()
    (output_dir / "workflow.yaml").write_text("existing content")

    with pytest.raises(FileAlreadyExistsError) as exc_info:
        initialize_from_template("branch", output_dir, force=False)

    assert "workflow.yaml" in str(exc_info.value)
    assert "--force" in str(exc_info.value)


def test_initialize_from_template_overwrites_with_force(tmp_path: Path) -> None:
    """force=True の場合に既存ファイルが上書きされることを確認する。"""
    output_dir = tmp_path / "test-workflow"
    output_dir.mkdir()
    workflow_file = output_dir / "workflow.yaml"
    workflow_file.write_text("existing content")

    initialize_from_template("branch", output_dir, force=True)

    # ファイルが上書きされていることを確認
    content = workflow_file.read_text()
    assert "existing content" not in content
    assert "version:" in content


def test_loop_template_has_correct_structure(tmp_path: Path) -> None:
    """Loop テンプレートが正しい構造を持つことを確認する。"""
    output_dir = tmp_path / "loop-workflow"

    initialize_from_template("loop", output_dir, force=False)

    workflow_file = output_dir / "workflow.yaml"
    prompts_file = output_dir / "prompts" / "loop_prompts.yaml"

    assert workflow_file.exists()
    assert prompts_file.exists()

    # workflow.yaml に必要な要素が含まれることを確認
    workflow_content = workflow_file.read_text()
    assert "planner" in workflow_content
    assert "evaluator" in workflow_content
    assert "retry" in workflow_content


def test_rag_template_has_correct_structure(tmp_path: Path) -> None:
    """Rag テンプレートが正しい構造を持つことを確認する。"""
    output_dir = tmp_path / "rag-workflow"

    initialize_from_template("rag", output_dir, force=False)

    workflow_file = output_dir / "workflow.yaml"
    prompts_file = output_dir / "prompts" / "rag_prompts.yaml"

    assert workflow_file.exists()
    assert prompts_file.exists()

    # workflow.yaml に RAG パターンの要素が含まれることを確認
    workflow_content = workflow_file.read_text()
    assert "retrieve" in workflow_content
    assert "rerank" in workflow_content
    assert "generate" in workflow_content
