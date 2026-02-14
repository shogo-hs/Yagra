# GET /api/workflow/form — フォーム編集向けworkflow取得

一覧: [Yagra Workflow Studio API エンドポイント一覧](./index.md)
最終更新: `2026-02-14`

## 1. 概要

- 目的: Studioフォーム編集用に整形した workflow 情報を取得する。
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
curl -X GET 'http://127.0.0.1:8787/api/workflow/form'
```

## 3. レスポンス

### 3.1 成功レスポンス

| Status | 条件 | 説明 |
| --- | --- | --- |
| 200 | 正常終了 | フォーム編集向けpayloadを返す |

### 3.2 レスポンスボディ

| field | type | nullable | 説明 |
| --- | --- | --- | --- |
| revision | string | No | 現在リビジョン |
| nodes | object[] | No | ノード編集項目（`id`,`handler`,`prompt_ref`,`prompt`,`model`） |
| edges | object[] | No | エッジ編集項目（`index`,`source`,`target`,`condition`） |
| prompt_catalog_keys | string[] | No | prompt catalog候補キー |
| workflow | object | No | workflow 生データ |
| ui_state | object | No | ui_state 生データ |
| catalog_preview | object | No | `prompt_catalog_path`,`prompt_catalog_keys`,`issues[]` |
| validation_report | object | No | `is_valid`,`issues[]` |

### 3.3 成功レスポンス例

```json
{
  "revision": "9e9b...",
  "nodes": [
    {
      "id": "planner",
      "handler": "planner_handler",
      "prompt_ref": "planning.special",
      "prompt": null,
      "model": {"provider": "openai", "name": "gpt-4.1-mini", "temperature": 0.2}
    }
  ],
  "edges": [],
  "prompt_catalog_keys": ["planning", "planning.special"],
  "workflow": {},
  "ui_state": {},
  "catalog_preview": {
    "prompt_catalog_path": "/tmp/prompts.yaml",
    "prompt_catalog_keys": ["planning.special"],
    "issues": []
  },
  "validation_report": {"is_valid": true, "issues": []}
}
```

## 4. エラー

| Status | type | message例 | 発生条件 | クライアント対応 |
| --- | --- | --- | --- | --- |
| 409 | studio_target_required | workflow target is not selected | ターゲット未選択 | `/api/studio/open/create` 実行 |
| 422 | load_failed | workflow の読み込みに失敗しました: ... | workflow/ui_state 読み込み失敗 | ファイル修正 |

## 5. 備考

- UIでは通常このAPIをロード起点として利用する。
- `model_ref` は廃止。モデル設定は `nodes[].params.model` のインライン定義を使用する。

## 6. 実装同期メモ

- 関連実装ファイル: `src/yagra/adapters/inbound/workflow_studio_server.py`
- 関連テスト: `tests/integration/test_workflow_studio_api.py`
- 未解決事項: なし
