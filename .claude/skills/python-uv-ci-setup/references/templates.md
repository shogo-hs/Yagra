# テンプレート集（uv + ruff + mypy + pytest + pre-commit + GitHub Actions）

## 目次

- [1. pyproject.toml（推奨テンプレート）](#1-pyprojecttoml推奨テンプレート)
- [2. .pre-commit-config.yaml（推奨テンプレート）](#2-pre-commit-configyaml推奨テンプレート)
- [3. .github/workflows/ci.yml（推奨テンプレート）](#3-githubworkflowsciyml推奨テンプレート)
- [4. セットアップ実行コマンド](#4-セットアップ実行コマンド)

## 1. pyproject.toml（推奨テンプレート）

```toml
[project]
name = "your-project"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = []

[dependency-groups]
dev = [
  "mypy>=1.11",
  "pre-commit>=3.8",
  "pytest>=8.3",
  "pytest-cov>=5.0",
  "ruff>=0.8",
]

[tool.ruff]
line-length = 100

[tool.ruff.format]
docstring-code-format = true

[tool.ruff.lint]
select = ["E4", "E7", "E9", "F", "I", "UP", "B", "D"]
ignore = ["D203", "D213", "D400", "D401", "D415"]

[tool.ruff.lint.pydocstyle]
convention = "google"

[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = ["D100", "D101", "D102", "D103", "D104"]

[tool.mypy]
python_version = "3.12"
warn_unused_configs = true
warn_return_any = true
warn_unused_ignores = true
no_implicit_optional = true
check_untyped_defs = true
show_error_codes = true
pretty = true

[tool.pytest.ini_options]
minversion = "8.0"
addopts = "-ra --strict-markers --strict-config"
testpaths = ["tests"]
```

適用メモ:
- `requires-python` を更新したら `tool.mypy.python_version` も合わせる。
- Ruff は `project.requires-python` から推論可能なため、`target-version` は必要時のみ明示する。
- 既存プロジェクトで docstring 違反が多い場合は、`D` ルールを段階導入する。
- docstring は短文 1 行で終わらせず、概要と入出力が分かる情報を含める。
- `Args` / `Returns` / `Raises` は、該当する要素がある場合に必ず記載する。

docstring 記載例（Google style）:

```python
def publish_report(title: str, dry_run: bool = False) -> str:
    """レポートを公開し、公開済みまたは公開予定の URL を返す。

    指定されたタイトルでレポートを作成する。`dry_run` が `True` の場合は
    永続化を行わず、生成予定の URL のみを返す。

    Args:
        title: 公開するレポートのタイトル。
        dry_run: `True` の場合は保存処理を実行しない。

    Returns:
        公開済み、または公開予定のレポート URL。

    Raises:
        ValueError: `title` が空文字の場合。
    """
```

## 2. .pre-commit-config.yaml（推奨テンプレート）

```yaml
minimum_pre_commit_version: "3.7.0"
default_install_hook_types: [pre-commit, pre-push]

repos:
  - repo: https://github.com/astral-sh/uv-pre-commit
    rev: 0.10.0
    hooks:
      - id: uv-lock

  - repo: local
    hooks:
      - id: ruff-format
        name: ruff format --check
        entry: uv run ruff format --check .
        language: system
        pass_filenames: false

      - id: ruff-lint
        name: ruff check
        entry: uv run ruff check .
        language: system
        pass_filenames: false

      - id: mypy
        name: mypy
        entry: uv run mypy .
        language: system
        pass_filenames: false

      - id: pytest
        name: pytest
        entry: uv run pytest -q
        language: system
        pass_filenames: false
        stages: [pre-push]
```

適用メモ:
- すべてのコミットで `pytest` を必須にする場合は `stages` を削除する。
- フックの実行対象を絞る場合は `files` を追加する。

## 3. .github/workflows/ci.yml（推奨テンプレート）

```yaml
name: CI

on:
  pull_request:
  push:
    branches: [main]

jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v5

      - name: Set up Python
        uses: actions/setup-python@v6
        with:
          python-version-file: pyproject.toml

      - name: Set up uv
        uses: astral-sh/setup-uv@v7
        with:
          enable-cache: true

      - name: Sync dependencies
        run: uv sync --locked --dev

      - name: Ruff format check
        run: uv run ruff format --check .

      - name: Ruff lint
        run: uv run ruff check .

      - name: Mypy
        run: uv run mypy .

      - name: Pytest
        run: uv run pytest -q
```

適用メモ:
- `uv.lock` がない場合は先に `uv lock` を実行してコミットする。
- Python複数バージョン検証が必要なら `matrix` を追加する。

## 4. セットアップ実行コマンド

```bash
uv add --dev ruff mypy pytest pytest-cov pre-commit
uv lock
uv sync --locked --dev
uv run pre-commit install --hook-type pre-commit --hook-type pre-push
uv run pre-commit run --all-files
```

最終確認:

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy .
uv run pytest -q
```
