# POST /api/workflow/save — workflow保存

一覧: [Yagra Workflow Studio API エンドポイント一覧](./index.md)
最終更新: `2026-02-14`

## 1. 概要

- 目的: 候補 workflow / ui_state を保存し、バックアップIDを返す。
- 利用者/権限: ローカル Studio 利用者。
- 副作用: workflow / ui_state の書き込み、backup作成。

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
| workflow | object | Yes | mapping | 保存候補workflow |
| ui_state | object | Yes | mapping | 保存候補ui_state |
| base_revision | string | Yes | - | 競合検知用revision |

### 2.5 リクエスト例

```bash
curl -X POST 'http://127.0.0.1:8787/api/workflow/save' \
  -H 'Content-Type: application/json' \
  -d '{
    "workflow": {},
    "ui_state": {},
    "base_revision": "9e9b..."
  }'
```

## 3. レスポンス

### 3.1 成功レスポンス

| Status | 条件 | 説明 |
| --- | --- | --- |
| 200 | 保存成功 | 新revisionとbackup ID |

### 3.2 レスポンスボディ

| field | type | nullable | 説明 |
| --- | --- | --- | --- |
| saved_revision | string | No | 保存後revision |
| backup_id | string | No | 作成されたbackup ID |

### 3.3 成功レスポンス例

```json
{
  "saved_revision": "f0aa...",
  "backup_id": "20260214153000_ab12cd34"
}
```

## 4. エラー

| Status | type | message例 | 発生条件 | クライアント対応 |
| --- | --- | --- | --- | --- |
| 400 | `... must be a ...` | - | 型不正 | 入力修正 |
| 400 | invalid_payload | ... | payload不正 | 入力修正 |
| 409 | studio_target_required | workflow target is not selected | ターゲット未選択 | `/api/studio/open/create` |
| 409 | revision_conflict | - | `base_revision` 不一致 | 再読み込み |
| 422 | validation_failed | - | workflow検証失敗 | 入力修正 |

## 5. 備考

- validation失敗時は `report` を返す。

## 6. 実装同期メモ

- 関連実装ファイル: `src/yagra/adapters/inbound/workflow_studio_server.py`, `src/yagra/application/use_cases/workflow_persistence.py`
- 関連テスト: `tests/integration/test_workflow_studio_api.py`, `tests/unit/application/test_workflow_persistence.py`
- 未解決事項: なし
