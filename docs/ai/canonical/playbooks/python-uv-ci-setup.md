---
name: python-uv-ci-setup
description: uv を使う Python プロジェクトで、format/lint/静的型チェック/テスト/docstring ルールをローカルと GitHub Actions で一貫運用するためのセットアップPlaybook。`pyproject.toml` の `[dependency-groups]`、`.pre-commit-config.yaml`、`.github/workflows/ci.yml` を新規作成または更新し、`uv run pre-commit install` まで完了させる依頼で使う。
---

# Python uv CIセットアップ

このPlaybookでは、`uv + ruff + mypy + pytest + pre-commit + GitHub Actions` を最小差分で導入し、ローカルとCIの品質ゲートをそろえる。

## 実行フロー

1. 前提を確認する。
- ルートに `pyproject.toml` があるか確認する。なければ `uv init` を提案する。
- `uv --version` と `python --version` を確認する。
- Git管理下か確認する。未初期化なら `git init` を実行してから進む。

2. 既存設定を監査する。
- `pyproject.toml` の `[dependency-groups]`、`[tool.ruff]`、`[tool.mypy]`、`[tool.pytest.*]` を確認する。
- `.pre-commit-config.yaml` と `.github/workflows/*.yml` を確認する。
- 既存設定がある場合は上書きせず、重複を避けて統合する。

3. `pyproject.toml` を `uv` 前提で整備する。
- 開発依存を `dependency-groups.dev` に集約する。
- 最低限の開発依存をそろえる: `ruff`, `mypy`, `pytest`, `pre-commit`。
- ルールは `docs/ai/playbook-assets/python-uv-ci-setup/references/templates.md` の `pyproject.toml` テンプレートを基準にし、既存プロジェクトに合わせて微調整する。

4. pre-commit を設定する。
- `.pre-commit-config.yaml` を作成または更新する。
- `uv-pre-commit` の `uv-lock` を入れてロックファイル整合を強制する。
- `uv run` 経由で `ruff format --check`、`ruff check`、`mypy` を実行する。
- `pytest` は既定で `pre-push` に配置して開発体験を維持する。全コミットで必須にしたい場合は `stages` を `pre-commit` に変更する。

5. GitHub Actions を設定する。
- `.github/workflows/ci.yml` を作成または更新する。
- `actions/setup-python` と `astral-sh/setup-uv` を使い、`uv sync --locked --dev` の後に同等チェックを実行する。
- キャッシュは `setup-uv` の `enable-cache: true` を基本にする。

6. ローカルセットアップを完了する。
- `uv lock`
- `uv sync --locked --dev`
- `uv run pre-commit install --hook-type pre-commit --hook-type pre-push`
- `uv run pre-commit run --all-files`

7. 最終検証を実行する。
- `uv run ruff format --check .`
- `uv run ruff check .`
- `uv run mypy .`
- `uv run pytest -q`

8. 結果を報告する。
- 追加・更新したファイル
- 実行コマンドと結果
- 残課題（既存コード由来のlint/type/test失敗など）

## 運用ルール

- 型チェックは `mypy` に固定し、`ty` は使わない。
- docstring は Google style を採用し、短文 1 行のみの記述を避ける。
- docstring の先頭では「何をする処理か」「どの条件で使うか」を日本語で具体的に説明する。
- 引数がある処理は `Args`、戻り値がある処理は `Returns`、例外を送出しうる処理は `Raises` を記載する。
- `pydocstyle` の `convention = "google"` を有効化し、必要に応じて日本語運用に不要なルールのみ最小限で除外する。
- `project.requires-python` を定義し、Ruff のバージョン推論と整合させる。
- CI とローカルで実行コマンドを一致させる。

## 参照ファイル

- 設定方針と採用理由: `docs/ai/playbook-assets/python-uv-ci-setup/references/tooling-best-practices.md`
- そのまま適用できる雛形: `docs/ai/playbook-assets/python-uv-ci-setup/references/templates.md`
