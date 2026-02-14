# GET /api/studio/target — 現在のStudioターゲット取得

一覧: [Yagra Workflow Studio API エンドポイント一覧](./index.md)
最終更新: `2026-02-14`

## 1. 概要

- 目的: Studio が現在どの workflow を編集対象にしているかを返す。
- 利用者/権限: ローカル Studio 利用者。
- 副作用: なし。

## 2. リクエスト

### 2.1 ヘッダー

なし（任意ヘッダーのみ）。

### 2.2 パスパラメータ

なし。

### 2.3 クエリパラメータ

なし。

### 2.4 リクエストボディ

なし。

### 2.5 リクエスト例

```bash
curl -X GET 'http://127.0.0.1:8787/api/studio/target'
```

## 3. レスポンス

### 3.1 成功レスポンス

| Status | 条件 | 説明 |
| --- | --- | --- |
| 200 | 常に | 現在ターゲット情報を返す |

### 3.2 レスポンスボディ

| field | type | nullable | 説明 | 例 |
| --- | --- | --- | --- | --- |
| has_target | boolean | No | 編集ターゲットが選択済みか | `true` |
| workflow_path | string | Yes | 選択中 workflow の絶対パス | `/tmp/workflow.yaml` |
| ui_state_path | string | Yes | 対応する UI state パス | `/tmp/workflow.workflow-ui.json` |
| workspace_root | string | No | Studio の workspace ルート | `/Users/me/project` |

### 3.3 成功レスポンス例

```json
{
  "has_target": true,
  "workflow_path": "/tmp/workflow.yaml",
  "ui_state_path": "/tmp/workflow.workflow-ui.json",
  "workspace_root": "/Users/me/project"
}
```

## 4. エラー

| Status | type | message例 | 発生条件 | クライアント対応 |
| --- | --- | --- | --- | --- |
| 404 | not_found | (なし) | 未定義パス | URL確認 |

## 5. 備考

- ターゲット未選択時は `has_target=false` かつ `workflow_path/ui_state_path=null`。

## 6. 実装同期メモ

- 関連実装ファイル: `src/yagra/adapters/inbound/workflow_studio_server.py`
- 関連テスト: `tests/integration/test_workflow_studio_api.py`
- 未解決事項: なし
