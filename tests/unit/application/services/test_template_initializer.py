"""Tests for template_initializer."""

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
    """Confirms that the template list is returned correctly."""
    templates = list_templates()
    assert "branch" in templates
    assert "loop" in templates
    assert "rag" in templates
    assert "multi-agent" in templates
    assert "tool-use" in templates
    assert len(templates) >= 5


def test_list_templates_with_info_returns_metadata() -> None:
    """Confirms that list_templates_with_info returns metadata."""
    infos = list_templates_with_info()
    names = [info.name for info in infos]
    assert "branch" in names
    assert "multi-agent" in names
    assert "tool-use" in names

    # Confirm that metadata for multi-agent is included
    multi_agent_info = next(info for info in infos if info.name == "multi-agent")
    assert multi_agent_info.use_case != ""
    assert multi_agent_info.description != ""

    # Confirm that metadata for tool-use is included
    tool_use_info = next(info for info in infos if info.name == "tool-use")
    assert tool_use_info.use_case != ""
    assert tool_use_info.description != ""


def test_initialize_from_template_creates_files(tmp_path: Path) -> None:
    """Confirms that files are correctly generated from a template."""
    output_dir = tmp_path / "test-workflow"

    initialize_from_template("branch", output_dir, force=False)

    assert (output_dir / "workflow.yaml").exists()
    assert (output_dir / "prompts" / "branch_prompts.yaml").exists()


def test_initialize_from_template_validates_template_name() -> None:
    """Confirms that an error is raised for a nonexistent template name."""
    with pytest.raises(TemplateNotFoundError) as exc_info:
        initialize_from_template("invalid", Path("/tmp/test"), force=False)

    assert "invalid" in str(exc_info.value)
    assert "branch" in str(exc_info.value)


def test_initialize_from_template_checks_existing_files(tmp_path: Path) -> None:
    """Confirms that an error is raised with force=False when existing files are present."""
    output_dir = tmp_path / "test-workflow"
    output_dir.mkdir()
    (output_dir / "workflow.yaml").write_text("existing content")

    with pytest.raises(FileAlreadyExistsError) as exc_info:
        initialize_from_template("branch", output_dir, force=False)

    assert "workflow.yaml" in str(exc_info.value)
    assert "--force" in str(exc_info.value)


def test_initialize_from_template_overwrites_with_force(tmp_path: Path) -> None:
    """Confirms that existing files are overwritten when force=True."""
    output_dir = tmp_path / "test-workflow"
    output_dir.mkdir()
    workflow_file = output_dir / "workflow.yaml"
    workflow_file.write_text("existing content")

    initialize_from_template("branch", output_dir, force=True)

    # Confirm that the file has been overwritten
    content = workflow_file.read_text()
    assert "existing content" not in content
    assert "version:" in content


def test_loop_template_has_correct_structure(tmp_path: Path) -> None:
    """Confirms that the loop template has the correct structure."""
    output_dir = tmp_path / "loop-workflow"

    initialize_from_template("loop", output_dir, force=False)

    workflow_file = output_dir / "workflow.yaml"
    prompts_file = output_dir / "prompts" / "loop_prompts.yaml"

    assert workflow_file.exists()
    assert prompts_file.exists()

    # Confirm that workflow.yaml contains the required elements
    workflow_content = workflow_file.read_text()
    assert "planner" in workflow_content
    assert "evaluator" in workflow_content
    assert "retry" in workflow_content


def test_rag_template_has_correct_structure(tmp_path: Path) -> None:
    """Confirms that the rag template has the correct structure."""
    output_dir = tmp_path / "rag-workflow"

    initialize_from_template("rag", output_dir, force=False)

    workflow_file = output_dir / "workflow.yaml"
    prompts_file = output_dir / "prompts" / "rag_prompts.yaml"

    assert workflow_file.exists()
    assert prompts_file.exists()

    # Confirm that workflow.yaml contains RAG pattern elements
    workflow_content = workflow_file.read_text()
    assert "retrieve" in workflow_content
    assert "rerank" in workflow_content
    assert "generate" in workflow_content


def test_multi_agent_template_has_correct_structure(tmp_path: Path) -> None:
    """Confirms that the multi-agent template has the correct structure."""
    output_dir = tmp_path / "multi-agent-workflow"

    initialize_from_template("multi-agent", output_dir, force=False)

    workflow_file = output_dir / "workflow.yaml"
    prompts_file = output_dir / "prompts" / "multi_agent_prompts.yaml"

    assert workflow_file.exists()
    assert prompts_file.exists()

    # Confirm that template.yaml is not copied
    assert not (output_dir / "template.yaml").exists()

    # Confirm that workflow.yaml contains multi-agent pattern elements
    workflow_content = workflow_file.read_text()
    assert "orchestrator" in workflow_content
    assert "researcher" in workflow_content
    assert "writer" in workflow_content
    assert "retry" in workflow_content
    assert "done" in workflow_content


def test_tool_use_template_has_correct_structure(tmp_path: Path) -> None:
    """Confirms that the tool-use template has the correct structure."""
    output_dir = tmp_path / "tool-use-workflow"

    initialize_from_template("tool-use", output_dir, force=False)

    workflow_file = output_dir / "workflow.yaml"
    prompts_file = output_dir / "prompts" / "tool_use_prompts.yaml"

    assert workflow_file.exists()
    assert prompts_file.exists()

    # Confirm that template.yaml is not copied
    assert not (output_dir / "template.yaml").exists()

    # Confirm that workflow.yaml contains tool-use pattern elements
    workflow_content = workflow_file.read_text()
    assert "planner" in workflow_content
    assert "tool_executor" in workflow_content
    assert "synthesizer" in workflow_content
    assert "use_tool" in workflow_content
    assert "direct" in workflow_content
