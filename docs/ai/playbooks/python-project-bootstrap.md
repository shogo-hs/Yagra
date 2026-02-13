---
name: python-project-bootstrap
description: 新しい Python プロジェクトの初期セットアップを標準化するPlaybook。AGENTS.md と docs/product を対話で確定し、Hexagonal Architecture 前提のディレクトリ、SOLID/DRY ガイド、API/タスク設計ドキュメント、`.env.development`/`.env.production` と dotenvx 暗号化運用を整備するときに使う。CI は必須工程とし、品質ゲート設定は必ず `python-uv-ci-setup` を呼び出して完了させる依頼で適用する。
---

<!-- AUTO-GENERATED FILE. DO NOT EDIT DIRECTLY. -->
<!-- source: docs/ai/canonical/playbooks/python-project-bootstrap.md + scripts/sync_ai_context.py -->

# Pythonプロジェクト初期構築

このPlaybookは、Python 新規プロジェクトの「最初に揃えるべき構造と運用ドキュメント」を再利用可能な手順で作る。

## 実行ルール

- AGENTS.md の不明点がある状態で雛形を確定しない。必ず対話で埋める。
- `docs/product/vision.md` / `docs/product/goals.md` / `docs/product/milestones.md` / `docs/product/progress.md` を空欄のまま放置しない。初期化時に必ずユーザーと擦り合わせる。
- 質問は 1〜3 問ずつ行い、回答を反映して次の質問へ進む。
- CI 設定は必須。必ず `python-uv-ci-setup` を使って完了させる。
- 既存ファイルがある場合は破壊的上書きを避け、差分統合を優先する。
- AGENTS.md は常時有効ルールのみを記載し、長い手順やコマンドは Playbook 側へ集約する。
- 原則として新規作成は Playbook 同梱のテンプレートリポジトリから開始する。
- 空リポジトリから開始する場合のみ、グローバル `python-project-bootstrap` を初回1回だけ使う。
- 初回生成直後に手順正本を `<repo>/docs/ai/canonical/playbooks/` へ配置し、以後は repo ローカルを正本とする。

## 実行フロー

1. 前提を確認する。
- ルートディレクトリと Git 管理状態を確認する。
- 既存の `AGENTS.md` と `docs/task-designs` の有無を確認する。
- 既存プロジェクトで `docs/tasks` を使っている場合のみ、後方互換として既存パス命名を尊重する。
- 空リポジトリの場合は「初回のみグローバル bootstrap」を適用し、完了後に repo ローカル Playbook 運用へ移行する。

2. AGENTS.md 情報を対話で確定する。
- `docs/ai/playbook-assets/python-project-bootstrap/references/agents-md-checklist.md` の必須項目から埋める。
- `docs/ai/playbook-assets/python-project-bootstrap/references/agents-playbooks-boundary.md` を基準に、AGENTS と Playbooks の責務境界を固定する。
- 未確定項目は既定値を勝手に固定せず、ユーザー確認を優先する。
- 既定値を使う場合は「既定値を採用した」と明示してから確定する。

3. 初期構成を生成する。
- `scripts/playbooks/python-project-bootstrap/bootstrap_python_project.py` を実行して、ディレクトリと初期ドキュメントを生成する。
- 例:
  - `python3 scripts/playbooks/python-project-bootstrap/bootstrap_python_project.py --target <project-root> --project-name <name> --package-name <package_name> --description "<description>"`
- 必要に応じて `--task-design-dir docs/task-designs`（既定）や `--force` を使う。
- 生成後に手順正本を `<repo>/docs/ai/canonical/playbooks/` に配置してコミットし、以後の実行基盤を repo ローカルへ固定する。

4. プロダクト方針（docs/product）を対話で初期確定する。
- `docs/ai/playbook-assets/python-project-bootstrap/references/product-docs-alignment.md` を使い、1〜3問ずつ擦り合わせる。
- 最低限、次を埋める。
  - `docs/product/vision.md`: 対象ユーザー、解く課題、成功状態
  - `docs/product/goals.md`: ユーザー到達状態ゴールと到達判定
  - `docs/product/milestones.md`: 到達ステップ
  - `docs/product/progress.md`: やるべきこと一覧ベースの現在地
- 不確定項目が残る場合は、`仮置き` と明記して次の確認タイミングを残す。

5. 生成内容をレビューする。
- `docs/ai/playbook-assets/python-project-bootstrap/references/project-structure.md` を基準に、`adapters/application/domain/ports` の責務分離を確認する。
- `docs/rules/solid/README.md` と `docs/rules/code_architecture/README.md` の導線が AGENTS.md から参照できることを確認する。
- `docs/ai/playbook-assets/python-project-bootstrap/references/env-and-dotenvx.md` を基準に `.env.*` の運用記載が整合しているか確認する。
- `docs/product/*.md` が生成され、対話で確定した内容が反映されていることを確認する。

6. CI を必須で設定する。
- 生成直後に必ず `python-uv-ci-setup` を呼び出して、`uv` ベースの品質ゲートと GitHub Actions を整備する。
- 本Playbook内で CI 設定を再実装しない（DRY を維持）。

7. 検証する。
- 生成ファイル一覧を確認する。
- `AGENTS.md` の必須セクションが埋まっていることを確認する。
- `docs/product/vision.md` / `docs/product/goals.md` / `docs/product/milestones.md` / `docs/product/progress.md` が初期記入されていることを確認する。
- `.env.development` / `.env.production` の整合を確認する。
- CI 設定完了後に `uv run pre-commit install` が実行可能な状態であることを確認する。

8. 結果を報告する。
- 作成・更新したファイル
- 対話で確定した項目
- `docs/product` で合意した内容（Vision/Goal/Milestone/Progress）
- CI 設定の実行結果
- 残課題（手動で埋めるべき値や鍵など）
- Playbook 配置先（repo 配下 / 個人グローバル）と採用理由

## 参照ファイル

- AGENTS.md ヒアリング項目: `docs/ai/playbook-assets/python-project-bootstrap/references/agents-md-checklist.md`
- AGENTS と Playbooks の責務境界: `docs/ai/playbook-assets/python-project-bootstrap/references/agents-playbooks-boundary.md`
- docs/product 擦り合わせ質問: `docs/ai/playbook-assets/python-project-bootstrap/references/product-docs-alignment.md`
- Hexagonal 構成と責務: `docs/ai/playbook-assets/python-project-bootstrap/references/project-structure.md`
- `.env.*` と dotenvx 暗号化運用: `docs/ai/playbook-assets/python-project-bootstrap/references/env-and-dotenvx.md`
