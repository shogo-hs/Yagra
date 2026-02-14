# POST /api/workflow/catalogs/preview — prompt catalog参照設定プレビュー

一覧: [Yagra Workflow Studio API エンドポイント一覧](./index.md)
最終更新: `2026-02-14`

## 1. 概要

- 状態: Legacy（現行 Studio UI では使用しない）。
- 目的: 候補workflowに対する `prompt_catalog` の解決結果とキー候補を返す。
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
| workflow | object | Yes | mapping | 解析対象候補workflow |

### 2.5 リクエスト例

```bash
curl -X POST 'http://127.0.0.1:8787/api/workflow/catalogs/preview' \
  -H 'Content-Type: application/json' \
  -d '{"workflow":{"params":{"prompt_catalog":"./prompts.yaml"}}}'
```

## 3. レスポンス

### 3.1 成功レスポンス

| Status | 条件 | 説明 |
| --- | --- | --- |
| 200 | 正常終了 | catalog解決結果と問題一覧 |

### 3.2 レスポンスボディ

| field | type | nullable | 説明 |
| --- | --- | --- | --- |
| prompt_catalog_path | string | Yes | 解決済みprompt catalog絶対パス |
| prompt_catalog_keys | string[] | No | prompt catalogキー候補 |
| issues | object[] | No | catalog設定の問題一覧 |

### 3.3 成功レスポンス例

```json
{
  "prompt_catalog_path": "/tmp/prompts.yaml",
  "prompt_catalog_keys": ["planning", "planning.special"],
  "issues": []
}
```

## 4. エラー

| Status | type | message例 | 発生条件 | クライアント対応 |
| --- | --- | --- | --- | --- |
| 400 | workflow must be a mapping | - | body不正 | 入力修正 |
| 400 | invalid_payload | ... | payload型不整合 | 入力修正 |
| 409 | studio_target_required | workflow target is not selected | ターゲット未選択 | `/api/studio/open/create` |

## 5. 備考

- `issues` は200で返る（catalog不在などは業務エラー扱い）。
- `prompt_catalog` 運用は非推奨。Node Properties の `prompt yaml` + `prompt_ref=<path>[#key]` を推奨。
- `model_ref` は廃止済みのため、model catalog のプレビューは提供しない。

## 6. 実装同期メモ

- 関連実装ファイル: `src/yagra/adapters/inbound/workflow_studio_server.py`
- 関連テスト: `tests/integration/test_workflow_studio_api.py`, `tests/unit/application/test_workflow_form_model.py`
- 未解決事項: なし
