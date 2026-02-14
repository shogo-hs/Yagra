# GET /api/workflow — 現在workflowの生データ取得

一覧: [Yagra Workflow Studio API エンドポイント一覧](./index.md)
最終更新: `2026-02-14`

## 1. 概要

- 目的: 現在の workflow / ui_state / revision / validation_report を取得する。
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
curl -X GET 'http://127.0.0.1:8787/api/workflow'
```

## 3. レスポンス

### 3.1 成功レスポンス

| Status | 条件 | 説明 |
| --- | --- | --- |
| 200 | 正常終了 | 現在のworkflow編集セッション情報 |

### 3.2 レスポンスボディ

| field | type | nullable | 説明 |
| --- | --- | --- | --- |
| workflow | object | No | workflow YAML を辞書化した内容 |
| ui_state | object | No | UI state |
| revision | string | No | 現在リビジョン |
| validation_report | object | No | `is_valid`, `issues[]` |

### 3.3 成功レスポンス例

```json
{
  "workflow": {"version": "1.0", "nodes": [], "edges": []},
  "ui_state": {},
  "revision": "9e9b...",
  "validation_report": {
    "is_valid": true,
    "issues": []
  }
}
```

## 4. エラー

| Status | type | message例 | 発生条件 | クライアント対応 |
| --- | --- | --- | --- | --- |
| 409 | studio_target_required | workflow target is not selected | ターゲット未選択 | `/api/studio/open/create` 実行 |
| 422 | load_failed | workflow の読み込みに失敗しました: ... | workflow/ui_state 読み込み失敗 | ファイル修正 |

## 5. 備考

- このAPIはフォーム情報整形を行わず、生データを返す。

## 6. 実装同期メモ

- 関連実装ファイル: `src/yagra/adapters/inbound/workflow_studio_server.py`
- 関連テスト: `tests/integration/test_workflow_studio_api.py`
- 未解決事項: なし
