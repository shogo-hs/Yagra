# POST /api/workflow/rollback — backup指定復元

一覧: [Yagra Workflow Studio API エンドポイント一覧](./index.md)
最終更新: `2026-02-14`

## 1. 概要

- 目的: 指定 backup へ rollback し、復元後revisionを返す。
- 利用者/権限: ローカル Studio 利用者。
- 副作用: workflow / ui_state をバックアップ内容へ復元。

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

| field | type | required | 制約 | 説明 | 例 |
| --- | --- | --- | --- | --- | --- |
| backup_id | string | Yes | non-empty | 復元対象backup ID | `20260214153000_ab12cd34` |

### 2.5 リクエスト例

```bash
curl -X POST 'http://127.0.0.1:8787/api/workflow/rollback' \
  -H 'Content-Type: application/json' \
  -d '{"backup_id":"20260214153000_ab12cd34"}'
```

## 3. レスポンス

### 3.1 成功レスポンス

| Status | 条件 | 説明 |
| --- | --- | --- |
| 200 | 復元成功 | 復元後revisionとbackup情報 |

### 3.2 レスポンスボディ

| field | type | nullable | 説明 |
| --- | --- | --- | --- |
| restored_revision | string | No | 復元後revision |
| backup_id | string | No | 復元元backup ID |
| safety_backup_id | string | Yes | rollback前の現状態を退避したbackup ID |

### 3.3 成功レスポンス例

```json
{
  "restored_revision": "9e9b...",
  "backup_id": "20260214153000_ab12cd34",
  "safety_backup_id": "20260214154500_ef56ab90"
}
```

## 4. エラー

| Status | type | message例 | 発生条件 | クライアント対応 |
| --- | --- | --- | --- | --- |
| 400 | `backup_id must be a non-empty string` | - | 入力不正 | 入力修正 |
| 404 | backup_not_found | backup not found: ... | backup不在 | backup_id確認 |
| 409 | studio_target_required | workflow target is not selected | ターゲット未選択 | `/api/studio/open/create` |

## 5. 備考

- `safety_backup_id` が返る場合、誤rollback時にそのIDで再復元できる。

## 6. 実装同期メモ

- 関連実装ファイル: `src/yagra/adapters/inbound/workflow_studio_server.py`, `src/yagra/application/use_cases/workflow_persistence.py`
- 関連テスト: `tests/integration/test_workflow_studio_api.py`, `tests/unit/application/test_workflow_persistence.py`
- 未解決事項: なし
