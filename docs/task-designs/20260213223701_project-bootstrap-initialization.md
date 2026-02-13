# タスク設計書: Graphyml 初期化と品質ゲート整備

最終更新: 2026-02-13
- ステータス: 完了(done)
- 作成者: Codex
- レビュー: shogohasegawa
- 対象コンポーネント: backend / docs / infra
- 関連: `docs/ai/playbooks/task-design-gate.md`, `docs/ai/playbooks/python-project-bootstrap.md`, `docs/ai/playbooks/python-uv-ci-setup.md`
- チケット/リンク: 該当なし
- 関連ゴールID: G-04
- 関連マイルストーンID: M-04

## 0. TL;DR
- `Graphyml` の初期化として、既存 Playbook と補助スクリプトを使って Python の土台を生成する。
- `scripts/bootstrap_after_canonical.py` で AI context 同期確認 + 初期構成生成を実施し、続けて `uv` ベースの CI 品質ゲートを導入する。
- `docs/product/*.md` は空欄テンプレートのままにせず、初期値を入れて運用開始可能な状態にする。
- 既存ファイルは破壊的上書きを避け、差分統合で進める。

## 1. 背景 / 課題
- 現在のリポジトリはテンプレート状態で、`src/`、`tests/`、`pyproject.toml`、`uv` 品質ゲートが未整備。
- `README.md` の新規立ち上げフローでは初期化を実行する前提になっているため、実体を揃える必要がある。
- `docs/product/*.md` がプレースホルダのままなので、タスク設計と Goal/Milestone の紐づけ運用が開始できない。

## 2. ゴール / 非ゴール
### 2.1 ゴール
- Python プロジェクトとして開発可能な最小構成（Hexagonal の骨組み、環境変数雛形、API/docs 雛形）を生成する。
- `uv + ruff + mypy + pytest + pre-commit + GitHub Actions` の品質ゲートをローカルと CI で一致させる。
- `docs/product/vision.md` / `docs/product/goals.md` / `docs/product/milestones.md` / `docs/product/progress.md` を初期記入済みにする。

### 2.2 非ゴール
- 業務ロジック実装や API 本実装は行わない。
- 外部サービスの本番キー投入や `.env.keys` の配布は行わない。
- 既存 `AGENTS.md` の canonical ルール再設計は行わない。

## 3. スコープ / 影響範囲
- 変更対象: プロジェクト初期ファイル群、`docs/product/*.md`、CI 設定、開発ツール設定。
- 影響範囲: 開発者のローカルセットアップ手順、GitHub Actions の必須チェック、タスク設計運用の開始条件。
- 互換性: 後方互換性への影響は小さいが、CI 必須化により既存ブランチの品質チェック基準は厳格化される。
- 依存関係: `uv`、GitHub Actions、`scripts/bootstrap_after_canonical.py`、`scripts/playbooks/python-project-bootstrap/bootstrap_python_project.py`。

## 4. 要件
### 4.1 機能要件
- `python3 scripts/bootstrap_after_canonical.py --project-name "Graphyml" --description "Graphyml プロジェクト初期化" --task-design-dir "docs/task-designs"` を成功させる。
- `pyproject.toml` と `uv.lock` を整備し、`dependency-groups.dev` に `ruff` / `mypy` / `pytest` / `pytest-cov` / `pre-commit` を追加する。
- `.pre-commit-config.yaml` と `.github/workflows/ci.yml` を整備して品質ゲートを実行可能にする。
- `docs/product/*.md` のプレースホルダを初期内容へ更新し、Goal/Milestone/Progress を相互参照可能にする。

### 4.2 非機能要件 / 制約
- 依存追加は `uv add` / `uv sync` を使用し、`pip install` は使用しない。
- 秘密情報は `encrypted:` プレースホルダを維持し、秘密値をコミットしない。
- 既存ファイルの上書きは最小化し、必要な変更のみを加える。
- 実行後に `ruff format --check` / `ruff check` / `mypy` / `pytest` が通る状態を目標にする。

## 5. 仕様 / 設計
### 5.1 全体方針
- 既存 Playbook の補助スクリプトを優先利用し、手作業生成を避ける。
- 初期化後に CI Playbook のテンプレートへ寄せ、ローカルと CI のコマンド差分をなくす。
- Product ドキュメントは「仮置き明記」ではなく、運用開始に必要な初期値を埋める。

### 5.2 変更点一覧
| 対象 | 変更内容 | 影響 | 備考 |
| --- | --- | --- | --- |
| `docs/task-designs/20260213223701_project-bootstrap-initialization.md` | 本タスク設計書を追加 | 実装ゲートの根拠 | 承認後に実装着手 |
| `src/graphyml/**`, `tests/**`, `docs/rules/**`, `docs/architecture/**`, `docs/api/**`, `.env.development`, `.env.production` | bootstrap スクリプトで初期構成生成 | 開発土台を整備 | 既存があれば非破壊で統合 |
| `pyproject.toml`, `uv.lock` | `uv` 管理の依存と設定を追加 | CI とローカルの品質統一 | Python 3.12+ 前提 |
| `.pre-commit-config.yaml` | pre-commit フック設定を追加 | ローカル品質ゲート有効化 | `pre-commit` + `pre-push` |
| `.github/workflows/ci.yml` | CI ワークフローを追加 | PR/Push で品質検証 | 既存 `ai-context-sync.yml` と併存 |
| `docs/product/vision.md`, `docs/product/goals.md`, `docs/product/milestones.md`, `docs/product/progress.md` | 初期内容を記入 | Goal/Milestone 紐づけ開始 | 初期値として更新 |

### 5.3 詳細
#### API
- `docs/api/index.md` と `docs/api/_endpoint_template.md` を雛形として配置する。
- 本タスクでは実 API エンドポイント追加は行わない。

#### UI
- 該当なし。

#### データモデル / 永続化
- DB スキーマ変更は行わない。
- `src/graphyml/domain` などのディレクトリ雛形のみを作成する。

#### 設定 / 環境変数
- `.env.development` / `.env.production` を生成し、秘密値は `encrypted:` 形式のプレースホルダで管理する。
- `.gitignore` に `.env.keys` 等の除外設定が含まれることを確認する。

### 5.4 代替案と不採用理由
- 代替案A: すべて手動でファイル作成する。
  - 不採用理由: 既存 Playbook の再利用方針に反し、テンプレートとの乖離が発生しやすい。
- 代替案B: CI 設定を後回しにする。
  - 不採用理由: 本リポジトリは CI 必須運用であり、初期化完了条件を満たせない。

## 6. 移行 / ロールアウト
- 初期化は単一ブランチ内で段階実行する（bootstrap → CI 設定 → product docs 更新 → 検証）。
- ロールバック条件: `uv` 品質ゲートを通過できない、または既存運用を壊す差分が発生した場合。
- ロールバック手順: 該当ファイル差分のみを取り消し、設計書を更新して再実行手順を再合意する。

## 7. テスト計画
- 単体: `uv run pytest -q` でテスト雛形が失敗しないことを確認する。
- 結合: GitHub Actions の `ci.yml` で `uv sync --locked --dev` から品質チェックまで通ることを確認する。
- 手動: `python3 scripts/sync_ai_context.py --check`、`uv run pre-commit run --all-files` を実行する。
- LLM/外部依存: 外部 API モックは不要。`uv` ダウンロード失敗時はネットワーク要因として切り分ける。
- 合格条件: `sync_ai_context --check` と `ruff`/`mypy`/`pytest` が全て成功し、必要ファイルが生成されている。

## 8. 受け入れ基準
- `docs/task-designs/` 配下に本設計書が存在し、承認ログが更新される。
- `src/graphyml/` 配下に Hexagonal 構成ディレクトリが作成される。
- `.pre-commit-config.yaml` と `.github/workflows/ci.yml` が存在し、`uv` コマンド前提の品質ゲートを実行できる。
- `docs/product/*.md` がプレースホルダのままではなく、初期内容が記入されている。
- `git status` に初期化差分のみが現れ、意図しない広範囲削除がない。

## 9. リスク / 対策
- `uv init` と bootstrap 生成物が競合するリスク。
  - 対策: 既存ファイルの存在を都度確認し、上書きではなく差分統合で適用する。
- Python 3.12 環境がローカルで未整備のリスク。
  - 対策: `uv` の管理 Python を利用し、必要時のみ `uv` 経由で 3.12 を解決する。
- Product ドキュメント初期値が実際の方針とずれるリスク。
  - 対策: 初期化後にすぐ見直しラウンドを実施できるよう、更新箇所を明示して報告する。

## 10. オープン事項 / 要確認
- 該当なし。

## 11. 実装タスクリスト
- [x] bootstrap スクリプトを実行し、初期ディレクトリと雛形ファイルを生成する。
- [x] `uv` ベースの `pyproject.toml` / `uv.lock` / `.pre-commit-config.yaml` / `.github/workflows/ci.yml` を整備する。
- [x] `docs/product/*.md` を初期内容で更新し、Goal/Milestone/Progress を接続する。
- [x] 品質ゲート（format/lint/type/test/sync-check）を実行して結果を確認する。

## 12. ドキュメント更新
- [x] `README.md`（必要に応じて）
- [ ] `AGENTS.md`（必要に応じて）
- [x] `docs/`（`docs/product/*.md`、`docs/rules/*`、`docs/architecture/*`、`docs/api/*`）

## 13. 承認ログ
- 承認者: shogohasegawa
- 承認日時: 2026-02-13 22:46
- 承認コメント: 「OK」にて実装承認

## 実装開始条件
- [x] ステータスが `承認済み(approved)` である
- [x] 10. オープン事項が空である
- [x] 受け入れ基準とテスト計画に合意済み
