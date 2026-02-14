# POST /api/studio/file/read — workspace内 YAML ファイル読込

一覧: [Yagra Workflow Studio API エンドポイント一覧](./index.md)
最終更新: `2026-02-14`

## 1. 概要

- 目的: workspace 配下の YAML ファイルを読み込み、内容とキー候補を返す。
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
| path | string | Yes | `workspace_root` 配下の `.yaml/.yml` | 読込対象パス |

### 2.5 リクエスト例

```bash
curl -X POST 'http://127.0.0.1:8787/api/studio/file/read' \
  -H 'Content-Type: application/json' \
  -d '{"path":"prompts/new_task.yaml"}'
```

## 3. レスポンス

### 3.1 成功レスポンス

| Status | 条件 | 説明 |
| --- | --- | --- |
| 200 | 正常終了 | YAML 内容を返す |

### 3.2 レスポンスボディ

| field | type | nullable | 説明 |
| --- | --- | --- | --- |
| path | string | No | 読込対象（workspace相対） |
| content | string | No | ファイル本文 |
| key_paths | string[] | No | ルートがmappingの場合の `a.b.c` キー候補 |
| parse_error | string | Yes | YAMLパース失敗またはmapping以外の場合の説明 |

### 3.3 成功レスポンス例

```json
{
  "path": "prompts/new_task.yaml",
  "content": "intent:\n  system: classify\n",
  "key_paths": ["intent", "intent.system"],
  "parse_error": null
}
```

## 4. エラー

| Status | type | message例 | 発生条件 | クライアント対応 |
| --- | --- | --- | --- | --- |
| 400 | invalid_yaml_path | path must be inside workspace_root | path不正 | 入力修正 |
| 404 | yaml_file_not_found | yaml file not found: ... | 対象ファイルなし | path確認 |
| 422 | yaml_read_failed | yaml file read failed: ... | 読込失敗 | パーミッション/FS確認 |

## 5. 備考

- `key_paths` は `prompt_ref` 入力補助用途。

## 6. 実装同期メモ

- 関連実装ファイル: `src/yagra/adapters/inbound/workflow_studio_server.py`
- 関連テスト: `tests/integration/test_workflow_studio_api.py`
- 未解決事項: なし
