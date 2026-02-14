# POST /api/workflow/form/preview — フォーム入力差分プレビュー

一覧: [Yagra Workflow Studio API エンドポイント一覧](./index.md)
最終更新: `2026-02-14`

## 1. 概要

- 目的: フォーム編集入力を候補workflowへ適用し、差分とvalidationを返す。
- 利用者/権限: ローカル Studio 利用者。
- 副作用: なし。

## 2. リクエスト

### 2.1 ヘッダー

| 項目 | 必須 | 値 | 説明 |
| --- | --- | --- | --- |
| Content-Type | Yes | application/json | JSONボディ送信 |

### 2.2 パスパラメータ

なし。

### 2.3 クエリパラメータ

なし。

### 2.4 リクエストボディ

| field | type | required | 制約 | 説明 |
| --- | --- | --- | --- | --- |
| base_revision | string | Yes | - | 差分基準revision |
| node_creates | array | Yes | - | ノード追加操作 |
| node_edits | array | Yes | - | ノード編集操作 |
| edge_creates | array | Yes | - | エッジ追加操作 |
| edge_rewires | array | Yes | - | エッジ再接続操作 |
| edge_edits | array | Yes | - | エッジ編集操作 |
| ui_state | object | Yes | mapping | 候補ui_state |

### 2.5 リクエスト例

```bash
curl -X POST 'http://127.0.0.1:8787/api/workflow/form/preview' \
  -H 'Content-Type: application/json' \
  -d '{
    "base_revision": "9e9b...",
    "node_creates": [],
    "node_edits": [{"node_id":"planner","prompt_ref":"prompts/new_task.yaml#intent"}],
    "edge_creates": [],
    "edge_rewires": [],
    "edge_edits": [],
    "ui_state": {}
  }'
```

## 3. レスポンス

### 3.1 成功レスポンス

| Status | 条件 | 説明 |
| --- | --- | --- |
| 200 | 正常終了 | 差分結果 + 候補workflow |

### 3.2 レスポンスボディ

| field | type | nullable | 説明 |
| --- | --- | --- | --- |
| base_revision | string | No | 現在revision |
| candidate_revision | string | No | 候補revision |
| summary | object | No | 差分件数サマリ |
| changes | object[] | No | 変更イベント |
| yaml_unified_diff | string | No | unified diff |
| validation_report | object | No | `is_valid`,`issues[]` |
| candidate_workflow | object | No | 適用後workflow |
| candidate_ui_state | object | No | 返却ui_state |

### 3.3 成功レスポンス例

```json
{
  "base_revision": "9e9b...",
  "candidate_revision": "f0aa...",
  "summary": {"total": 2},
  "changes": [],
  "yaml_unified_diff": "@@ ...",
  "validation_report": {"is_valid": true, "issues": []},
  "candidate_workflow": {},
  "candidate_ui_state": {}
}
```

## 4. エラー

| Status | type | message例 | 発生条件 | クライアント対応 |
| --- | --- | --- | --- | --- |
| 400 | `... must be an array` | - | 必須配列項目の型不正/欠落 | 入力修正 |
| 400 | `ui_state must be a mapping` | - | 型不正 | 入力修正 |
| 400 | invalid_payload | ... | 操作内容不整合 | 入力修正 |
| 409 | studio_target_required | workflow target is not selected | ターゲット未選択 | `/api/studio/open/create` |
| 409 | revision_conflict | - | `base_revision` 不一致 | 再読み込み |
| 422 | load_failed | ... | 現在workflow読み込み失敗 | ファイル修正 |

## 5. 備考

- `node_creates` 等の入力契約は空配列でも必須。
- `model_ref` は廃止。`node_edits[].model` でインライン更新する。

## 6. 実装同期メモ

- 関連実装ファイル: `src/yagra/adapters/inbound/workflow_studio_server.py`
- 関連テスト: `tests/integration/test_workflow_studio_api.py`
- 未解決事項: なし
