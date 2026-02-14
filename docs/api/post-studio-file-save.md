# POST /api/studio/file/save — workspace内 YAML ファイル保存

一覧: [Yagra Workflow Studio API エンドポイント一覧](./index.md)
最終更新: `2026-02-14`

## 1. 概要

- 目的: workspace 配下の YAML ファイルを新規作成または更新する。
- 利用者/権限: ローカル Studio 利用者。
- 副作用: あり（ファイル書き込み）。

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
| path | string | Yes | `workspace_root` 配下の `.yaml/.yml` | 保存先パス |
| content | string | Yes | YAMLとしてパース可能 | 保存本文 |
| overwrite | boolean | No | 既定 `false` | 既存ファイル上書き可否 |

### 2.5 リクエスト例

```bash
curl -X POST 'http://127.0.0.1:8787/api/studio/file/save' \
  -H 'Content-Type: application/json' \
  -d '{
    "path":"prompts/new_task.yaml",
    "content":"intent:\n  system: classify\n",
    "overwrite":false
  }'
```

## 3. レスポンス

### 3.1 成功レスポンス

| Status | 条件 | 説明 |
| --- | --- | --- |
| 200 | 正常終了 | 保存先 path を返す |

### 3.2 レスポンスボディ

| field | type | nullable | 説明 |
| --- | --- | --- | --- |
| path | string | No | 保存先（workspace相対） |

### 3.3 成功レスポンス例

```json
{
  "path": "prompts/new_task.yaml"
}
```

## 4. エラー

| Status | type | message例 | 発生条件 | クライアント対応 |
| --- | --- | --- | --- | --- |
| 400 | invalid_yaml_path | path must be inside workspace_root | path不正 | 入力修正 |
| 400 | invalid_yaml_content | mapping values are not allowed ... | YAML構文不正 | 内容修正 |
| 409 | yaml_file_exists | yaml file already exists: ... | overwrite=false かつ既存あり | overwrite指定または別path |
| 422 | yaml_save_failed | yaml file save failed: ... | 保存失敗 | パーミッション/FS確認 |

## 5. 備考

- 保存は atomic write で行う。

## 6. 実装同期メモ

- 関連実装ファイル: `src/yagra/adapters/inbound/workflow_studio_server.py`
- 関連テスト: `tests/integration/test_workflow_studio_api.py`
- 未解決事項: なし
