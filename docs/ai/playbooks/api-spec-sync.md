---
name: api-spec-sync
description: REST/HTTP APIの定義書（index + 1エンドポイント1ファイル）を新規作成・更新し、実装差分と常時同期させるためのPlaybook。API実装の追加・変更・削除、認証仕様変更、エラー形式変更、入出力スキーマ変更が発生したときに使う。
---

<!-- AUTO-GENERATED FILE. DO NOT EDIT DIRECTLY. -->
<!-- source: docs/ai/canonical/playbooks/api-spec-sync.md + scripts/sync_ai_context.py -->

# API定義書同期

API実装の変更とAPIドキュメント更新を同一タスクで完結させる。

## 実行手順

1. 実装差分から影響エンドポイントを特定する。
- ルーター・ハンドラー・コントローラー・DTO/Schema・OpenAPI定義の差分を確認する。
- 追加/変更/削除をエンドポイント単位に整理する。

2. 一覧ドキュメントを更新する。
- `docs/ai/playbook-assets/api-spec-sync/references/_index_template.md` を読み、`index.md` の共通仕様とエンドポイント一覧を更新する。
- 新規エンドポイント追加時は、必ず一覧リンクを追加する。
- 廃止エンドポイントは一覧から削除し、必要に応じて「非推奨 / 廃止」に移す。

3. エンドポイント詳細ドキュメントを更新する。
- `docs/ai/playbook-assets/api-spec-sync/references/_endpoint_template.md` を読み、対象エンドポイントの詳細ファイルを作成/更新する。
- 命名は `<resource>-<method>.md` を基本とし、必要ならプロジェクト規約に合わせる。
- 1エンドポイント1ファイルを厳守する。

4. 実装と仕様を突合する。
- HTTPメソッド、パス、認証、パラメータ、リクエスト/レスポンススキーマ、ステータスコード、エラーを確認する。
- 実装で確認できない項目は推測しない。`TODO(要実装確認)` として明示する。

5. 同期ゲートを通す。
- `docs/ai/playbook-assets/api-spec-sync/references/sync-checklist.md` のチェックを上から順に実施する。
- 必要なら `python3 scripts/playbooks/api-spec-sync/check_api_docs_sync.py --docs-root <APIドキュメントルート>` を実行する。
- API実装が変わっているのにドキュメント差分がない場合、タスク完了にしない。

6. 変更結果を報告する。
- 更新した一覧ファイルと詳細ファイルを明示する。
- 実装側の関連ファイルと未解決TODOを明示する。

## 厳守ルール

- API実装変更とAPIドキュメント更新を分離しない。
- 共通仕様（認証、エラーフォーマット、ベースURL）変更時は `index.md` を必ず更新する。
- エンドポイント仕様変更時は該当詳細ファイルを必ず更新する。
- 差分が大きい場合でも、最小限の追記で済ませず仕様全体の整合を優先する。

## 参照ファイル

- 一覧テンプレート: `docs/ai/playbook-assets/api-spec-sync/references/_index_template.md`
- 詳細テンプレート: `docs/ai/playbook-assets/api-spec-sync/references/_endpoint_template.md`
- 同期チェック: `docs/ai/playbook-assets/api-spec-sync/references/sync-checklist.md`
- 同期漏れ簡易検知スクリプト: `scripts/playbooks/api-spec-sync/check_api_docs_sync.py`
