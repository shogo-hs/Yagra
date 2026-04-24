# Task Intent: `.github/workflows/validate-example.yml` 実在化 (Backlog #3)

**layer:** PM Intent
**created:** 2026-04-24
**task size:** S
**parent contract:** `tasks/20260424085623_contract-po-pm-add-validate-example-workflow.md`

---

## Why（プロダクトビジョンへの貢献）

`docs/product/vision.md` の Phase 4「Approve & Update / CI Integration」では、`yagra validate` を GitHub Actions に組み込んで PR ごとにワークフロー変更を自動検証できることを提供価値として掲げている。

ビジョン整合性監査で検出した **Critical C3**（`docs/ci-integration-guide.md` から参照される `.github/workflows/validate-example.yml` がリポジトリに実在しない）を解消することで：

1. CI 統合を真似たいユーザーが、リポジトリ内の実ファイルをそのまま流用できるようになる（`cp` 1 コマンドで開始可能に）。
2. Yagra 自身の `examples/*/workflow.yaml` 6 個が CI で継続検証され、サイレント破壊（`examples/llm-basic` が過去に validator 不通になっていた事例）を防げる。
3. ガイドとリポジトリ実態の矛盾を解消し、Phase 1 ゲートの Critical 項目を 1 件消化する。

## What（成果物）

- **新規作成**: `.github/workflows/validate-example.yml`
- **任意の軽微修正**: ガイド実装と矛盾が残る場合のみ `docs/ci-integration-guide.md` を整合

## 成功基準（PO-PM Contract から転記）

| # | 基準 | 検証コマンド | 実質性チェック |
|---|------|------------|--------------|
| 1 | `.github/workflows/validate-example.yml` が実在する | `test -f .github/workflows/validate-example.yml && echo OK` | 中身が空でなく、有効な GitHub Actions YAML |
| 2 | トリガが `pull_request` + `push (main)` を含む | `uv run python -c "import yaml; c = yaml.safe_load(open('.github/workflows/validate-example.yml')); on = c.get(True, c.get('on', {})); assert 'pull_request' in on and 'push' in on; print('OK')"` | `on` キーが YAML で `true` に化ける問題に対応 |
| 3 | examples/ 全 6 個を検証するループが緑通過 | `for f in examples/*/workflow.yaml; do uv run yagra validate --workflow "$f" --bundle-root "$(dirname "$f")" --format json > /dev/null \|\| exit 1; done; echo OK` | exit=0 で通過（warnings 許容） |
| 4 | `docs/ci-integration-guide.md` の参照先と矛盾しない | `grep -n "validate-example.yml" docs/ci-integration-guide.md` | 参照が残り、参照先ファイルが実在 |
| 5 | `uv run pre-commit run --all-files` 通過 | `uv run pre-commit run --all-files` | ruff format / ruff check / mypy すべて Passed |
| 6 | 既存 `ci.yml` (`quality` job) と併存し衝突しない | `test -f .github/workflows/ci.yml && test -f .github/workflows/validate-example.yml` | 両方が同時に存在できる |

## スコープ

### In Scope
- `.github/workflows/validate-example.yml` の新規作成
- `docs/ci-integration-guide.md` の整合性確認（齟齬があれば微修正）
- ローカルでの examples/ 検証ループ実行（Developer 検証責務）

### Out of Scope
- 既存 `ci.yml` / `docs.yml` / `publish.yml` の変更
- `scripts/pr-comment-example.sh` の変更
- 「変更ファイルのみ検証」等の高度な設定（将来タスク）
- Yagra handler 実装の変更
- examples/ 配下の YAML 変更（#2 で修復済み）

## 制約

- Python 3.12 + uv 0.x（`ci.yml` と同じ toolchain）
- `astral-sh/setup-uv@v7`、`actions/checkout@v6` 等を既存 `ci.yml` と同じバージョンラインで使用
- `uv add / uv remove / uv sync` のみ。`pip install` / `uv pip install` 禁止
- Feature branch: `feature/add-validate-example-workflow`
- コミットメッセージは日本語・Conventional Commits・50 文字以内目安

## リスク/懸念

- `examples/human-review/workflow.yaml` 等の `prompt_ref` 解決には `--bundle-root "$(dirname "$f")"` 必須（既に PO が確認済み）
- `uv pip install --system yagra` は PyPI 公開版を入れるため、開発中コード検証には不適。`uv sync --locked --dev` + `uv run yagra` で現行コード検証する（PO と合意済み）
- `on` キーの YAML パースで `True` に化ける問題（yaml.safe_load の仕様）に対応した検証コマンドを採用済み
