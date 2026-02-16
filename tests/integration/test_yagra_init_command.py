"""yagra init コマンドの結合テスト。"""

import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def test_dir(tmp_path: Path) -> Path:
    """テスト用のディレクトリを作成する。

    Args:
        tmp_path: pytest の一時ディレクトリ。

    Returns:
        テスト用ディレクトリのパス。
    """
    test_dir = tmp_path / "test-workflow"
    test_dir.mkdir()
    return test_dir


def test_yagra_init_list_command() -> None:
    """Yagra init --list コマンドが正しく動作することを確認する。"""
    result = subprocess.run(
        ["uv", "run", "yagra", "init", "--list"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "branch" in result.stdout
    assert "loop" in result.stdout
    assert "rag" in result.stdout


def test_yagra_init_creates_workflow(test_dir: Path) -> None:
    """Yagra init --template コマンドでワークフローが生成されることを確認する。"""
    result = subprocess.run(
        ["uv", "run", "yagra", "init", "--template", "branch", "--output", str(test_dir)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "初期化しました" in result.stdout
    assert "valid です" in result.stdout

    # ファイルが生成されていることを確認
    assert (test_dir / "workflow.yaml").exists()
    assert (test_dir / "prompts" / "branch_prompts.yaml").exists()


def test_yagra_init_validates_generated_workflow(test_dir: Path) -> None:
    """生成されたワークフローが validate に合格することを確認する。"""
    # テンプレートから生成
    subprocess.run(
        ["uv", "run", "yagra", "init", "--template", "loop", "--output", str(test_dir)],
        capture_output=True,
        check=True,
    )

    # validate コマンドで検証
    result = subprocess.run(
        ["uv", "run", "yagra", "validate", "--workflow", str(test_dir / "workflow.yaml")],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0


def test_yagra_init_fails_without_template() -> None:
    """--template を指定せずに実行するとエラーになることを確認する。"""
    result = subprocess.run(
        ["uv", "run", "yagra", "init"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "エラー" in result.stderr or "指定してください" in result.stderr


def test_yagra_init_fails_with_invalid_template(test_dir: Path) -> None:
    """存在しないテンプレートを指定するとエラーになることを確認する。"""
    result = subprocess.run(
        ["uv", "run", "yagra", "init", "--template", "invalid", "--output", str(test_dir)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "見つかりません" in result.stderr


def test_yagra_init_prevents_overwrite_without_force(test_dir: Path) -> None:
    """既存ファイルがある場合、--force なしでは上書きされないことを確認する。"""
    # 最初の初期化
    subprocess.run(
        ["uv", "run", "yagra", "init", "--template", "branch", "--output", str(test_dir)],
        capture_output=True,
        check=True,
    )

    # 2回目の初期化（--force なし）
    result = subprocess.run(
        ["uv", "run", "yagra", "init", "--template", "branch", "--output", str(test_dir)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "ファイルが存在します" in result.stderr
    assert "--force" in result.stderr


def test_yagra_init_overwrites_with_force(test_dir: Path) -> None:
    """--force フラグで既存ファイルが上書きされることを確認する。"""
    # 最初の初期化
    subprocess.run(
        ["uv", "run", "yagra", "init", "--template", "branch", "--output", str(test_dir)],
        capture_output=True,
        check=True,
    )

    workflow_file = test_dir / "workflow.yaml"

    # ファイルを手動で変更
    workflow_file.write_text("modified content")

    # 2回目の初期化（--force あり）
    result = subprocess.run(
        [
            "uv",
            "run",
            "yagra",
            "init",
            "--template",
            "branch",
            "--output",
            str(test_dir),
            "--force",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0

    # ファイルが元のテンプレート内容に戻っていることを確認
    new_content = workflow_file.read_text()
    assert "modified content" not in new_content
    assert "version:" in new_content
