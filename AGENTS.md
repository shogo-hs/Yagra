# AGENTS.md

<!-- AUTO-GENERATED FILE. DO NOT EDIT DIRECTLY. -->
<!-- source: docs/ai/canonical/* + scripts/sync_ai_context.py -->

## このファイルについて
- このファイルは自動生成です。直接編集しないでください。
- 変更は `docs/ai/canonical/` を編集し、`python3 scripts/sync_ai_context.py` を実行してください。

## 1. グローバルポリシー
- 本リポジトリの AI 運用は「正本を1箇所に集約し、生成先へ配布する」方式を採用する。
- ルール更新時は `docs/ai/canonical/` を編集し、生成ファイルは直接編集しない。
- タスク開始時は必ずタスク設計を作成し、承認後に実装する。
- プロダクト方針は `docs/product/vision.md` / `docs/product/goals.md` / `docs/product/milestones.md` / `docs/product/progress.md` を正本として管理する。
- 新規タスク設計書には、`関連ゴールID` と `関連マイルストーンID` を必ず記載する。
- 既存の実装・ドキュメントとの整合を保ち、変更理由を記録する。
- ユーザーとのコミュニケーションは日本語で行う。
- CI は必須とし、品質ゲートの不一致を許容しない。
- Python パッケージの追加・更新・削除は `uv add` / `uv remove` / `uv sync` を使用し、`pip install` / `uv pip install` は使用しない。
- APIキー・トークン・秘密鍵・`.env.keys` などの秘密情報は、出力・コミット・Issue/PR本文へ記載しない。
- 想定外の大量差分、履歴破壊操作、広範囲削除が必要になった場合は作業を停止し、ユーザーへ再確認する。
- `README.md` は人間向けの入口として、目的・全体像・セットアップ・利用導線を記載する。
- `AGENTS.md` はエージェント向け実行規約として、判断基準・編集制約・検証手順・タスクルーティングを記載する。
- エージェント実行の詳細手順は `README.md` に重複記載しない。必要な場合は `AGENTS.md` と `docs/ai/playbooks/*.md` へリンクする。
- 記載先に迷った場合は「人が最初に理解するための説明は README、エージェントが実行時に守る規約は AGENTS」を優先する。

## 2. タスクルーティング
| 判断ケース | この条件なら使う | 参照先Playbook |
| --- | --- | --- |
| 実装前設計 | 実装・修正・移行など、ファイル変更前にスコープ整理と承認が必要 | [task-design-gate](docs/ai/playbooks/task-design-gate.md) |
| Python の CI / 品質ゲート導入 | `uv` 前提で lint/type/test/CI を一貫運用したい | [python-uv-ci-setup](docs/ai/playbooks/python-uv-ci-setup.md) |
| 新規プロジェクト初期構築 | Python プロジェクトを Hexagonal + 運用標準で立ち上げ、`docs/product/*.md` を初期擦り合わせする | [python-project-bootstrap](docs/ai/playbooks/python-project-bootstrap.md) |
| API 仕様同期 | API 実装と仕様ドキュメントの差分を同期する | [api-spec-sync](docs/ai/playbooks/api-spec-sync.md) |
| 設計判断の記録・更新 | アーキテクチャ方針や運用ルールの採否を ADR として記録・更新する | [adr-management](docs/ai/playbooks/adr-management.md) |
| コミット実行 | 変更内容を確認して規約に沿ったコミットを行う | [git-commit](docs/ai/playbooks/git-commit.md) |

## 使い分けルール

- AGENTS.md には「いつどの Playbook を使うか」を書き、実行時はリンク先ドキュメントを参照する。
- 詳細手順の正本は `docs/ai/canonical/playbooks/*.md` に集約し、`scripts/sync_ai_context.py` で `docs/ai/playbooks/*.md` へ配布する。
- 参照資料は `docs/ai/playbook-assets/`、補助スクリプトは `scripts/playbooks/` に集約する。
- 同じ手順を AGENTS.md と Playbook に重複記載しない。

## 3. コーディング標準
## 設計

- SOLID と DRY を基本原則にする。
- Hexagonal Architecture を採用し、`adapters/application/domain/ports` の責務を分離する。
- 依存方向は外側から内側へ固定し、domain は外部技術へ依存しない。

## Python

- Python 3.12+ を前提にする。
- 型ヒントを必須にし、`mypy` で検証する。
- `ruff` で format/lint を統一する。
- docstring は Google style を採用し、処理意図が伝わる説明を日本語で記述する。
- docstring は短文 1 行だけで終わらせず、少なくとも概要と入出力が分かる情報を含める。
- 引数がある関数・メソッドは `Args`、戻り値がある場合は `Returns`、送出しうる例外がある場合は `Raises` を記載する。
- docstring の説明内容は型ヒントおよび実装挙動と矛盾させない。

## 環境変数

- `.env.development` / `.env.production` を利用する。
- 秘密情報は dotenvx の `encrypted:` 形式で管理する。
- `.env.keys` はコミットしない。
