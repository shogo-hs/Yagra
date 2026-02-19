"""template_initializer のテスト。"""

from pathlib import Path

import pytest

from yagra.application.services.template_initializer import (
    FileAlreadyExistsError,
    TemplateNotFoundError,
    initialize_from_template,
    list_templates,
    list_templates_with_info,
)


def test_list_templates_returns_available_templates() -> None:
    """テンプレート一覧が正しく返されることを確認する。"""
    templates = list_templates()
    assert "branch" in templates
    assert "loop" in templates
    assert "rag" in templates
    assert "multi-agent" in templates
    assert "tool-use" in templates
    assert len(templates) >= 5


def test_list_templates_with_info_returns_metadata() -> None:
    """list_templates_with_info がメタ情報を返すことを確認する。"""
    infos = list_templates_with_info()
    names = [info.name for info in infos]
    assert "branch" in names
    assert "multi-agent" in names
    assert "tool-use" in names

    # multi-agent のメタ情報が含まれることを確認
    multi_agent_info = next(info for info in infos if info.name == "multi-agent")
    assert multi_agent_info.use_case != ""
    assert multi_agent_info.description != ""

    # tool-use のメタ情報が含まれることを確認
    tool_use_info = next(info for info in infos if info.name == "tool-use")
    assert tool_use_info.use_case != ""
    assert tool_use_info.description != ""


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


def test_multi_agent_template_has_correct_structure(tmp_path: Path) -> None:
    """multi-agent テンプレートが正しい構造を持つことを確認する。"""
    output_dir = tmp_path / "multi-agent-workflow"

    initialize_from_template("multi-agent", output_dir, force=False)

    workflow_file = output_dir / "workflow.yaml"
    prompts_file = output_dir / "prompts" / "multi_agent_prompts.yaml"

    assert workflow_file.exists()
    assert prompts_file.exists()

    # template.yaml がコピーされないことを確認
    assert not (output_dir / "template.yaml").exists()

    # workflow.yaml にマルチエージェントパターンの要素が含まれることを確認
    workflow_content = workflow_file.read_text()
    assert "orchestrator" in workflow_content
    assert "researcher" in workflow_content
    assert "writer" in workflow_content
    assert "retry" in workflow_content
    assert "done" in workflow_content


def test_tool_use_template_has_correct_structure(tmp_path: Path) -> None:
    """tool-use テンプレートが正しい構造を持つことを確認する。"""
    output_dir = tmp_path / "tool-use-workflow"

    initialize_from_template("tool-use", output_dir, force=False)

    workflow_file = output_dir / "workflow.yaml"
    prompts_file = output_dir / "prompts" / "tool_use_prompts.yaml"

    assert workflow_file.exists()
    assert prompts_file.exists()

    # template.yaml がコピーされないことを確認
    assert not (output_dir / "template.yaml").exists()

    # workflow.yaml にツール使用パターンの要素が含まれることを確認
    workflow_content = workflow_file.read_text()
    assert "planner" in workflow_content
    assert "tool_executor" in workflow_content
    assert "synthesizer" in workflow_content
    assert "use_tool" in workflow_content
    assert "direct" in workflow_content
