# ツール設定ベストプラクティス（uv前提）

## 1. uv

- `dependency-groups` を使い、開発依存は `dev` グループにまとめる。
- `uv sync` は既定で `dev` を同期するため、ローカル開発時の追加オプションを最小化できる。
- CI では `uv sync --locked --dev` を使い、`uv.lock` と整合する決定論的インストールに固定する。

参考:
- [uv dependencies](https://docs.astral.sh/uv/concepts/projects/dependencies/)
- [Using uv in GitHub Actions](https://docs.astral.sh/uv/guides/integration/github/)

## 2. Ruff（format/lint/docstring）

- formatter と linter を Ruff に統一してツール数を減らす。
- `pydocstyle` は `convention = "google"` を指定する。
- docstring は短文 1 行のみで終わらせず、処理概要と利用条件が分かる説明を入れる。
- `Args` / `Returns` / `Raises` は、該当する要素がある場合に記載して入出力と失敗条件を明示する。
- 日本語 docstring の運用では、英語前提になりやすいルール（例: `D400`, `D401`, `D415`）を必要に応じて除外する。
- `docstring-code-format = true` を有効化し、docstring 内コード例も整形対象にする。

参考:
- [Ruff settings](https://docs.astral.sh/ruff/settings/)

## 3. mypy（静的型チェック）

- 型チェッカーは `mypy` に固定する。
- 最初から `strict = true` を強制せず、`warn_unused_ignores` や `check_untyped_defs` などを段階的に有効化する。
- 出力可読性のため `show_error_codes = true` を有効化する。
- 設定は `pyproject.toml` に集約する。

参考:
- [mypy config file](https://mypy.readthedocs.io/en/stable/config_file.html)

## 4. pytest

- 互換性重視で `[tool.pytest.ini_options]` を使う。
- `--strict-markers` と `--strict-config` を既定化し、設定ミスを早期検知する。
- 実行コマンドは `uv run pytest -q` を標準化する。

参考:
- [pytest configuration](https://docs.pytest.org/en/stable/reference/customize.html)

## 5. pre-commit

- `uv-pre-commit` の `uv-lock` を有効化し、依存追加時のロック更新漏れを防ぐ。
- ツール実行は `uv run` で統一し、ローカル/CIで同じ依存を使う。
- 実行時間を抑えるため、既定は以下を推奨する。
  - `pre-commit`: `ruff format --check`, `ruff check`, `mypy`
  - `pre-push`: `pytest`
- インストール時は hook type を明示する。
  - `uv run pre-commit install --hook-type pre-commit --hook-type pre-push`

参考:
- [pre-commit](https://pre-commit.com/)
- [uv pre-commit integration](https://docs.astral.sh/uv/guides/integration/pre-commit/)

## 6. GitHub Actions

- `actions/setup-python` と `astral-sh/setup-uv` を組み合わせる。
- `setup-uv` では `enable-cache: true` を使う。
- `uv sync --locked --dev` の後、`ruff format --check`、`ruff check`、`mypy`、`pytest` を順番に実行する。
- 失敗時に原因を分離しやすいよう、ステップを分割する。

参考:
- [setup-uv action](https://github.com/astral-sh/setup-uv)
- [Using uv in GitHub Actions](https://docs.astral.sh/uv/guides/integration/github/)

## 7. 推奨実行順序

1. `uv lock`
2. `uv sync --locked --dev`
3. `uv run pre-commit install --hook-type pre-commit --hook-type pre-push`
4. `uv run pre-commit run --all-files`
5. `uv run pytest -q`

## 8. 改善案（標準より強化する場合）

- 型安全性を強化する場合:
  - `mypy` で `disallow_untyped_defs = true` を段階導入する。
- CI速度を改善する場合:
  - ジョブ分割（lint/type/test）を行い並列化する。
- テスト品質を強化する場合:
  - `pytest-cov` を導入し、最低カバレッジ閾値を設定する。
