# GET /api/studio/files — workspace内workflow候補一覧

一覧: [Yagra Workflow Studio API エンドポイント一覧](./index.md)
最終更新: `2026-02-14`

## 1. 概要

- 目的: Studio workspace 配下の `.yaml/.yml` workflow 候補を列挙する。
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
curl -X GET 'http://127.0.0.1:8787/api/studio/files'
```

## 3. レスポンス

### 3.1 成功レスポンス

| Status | 条件 | 説明 |
| --- | --- | --- |
| 200 | 常に | workflow 候補一覧を返す |

### 3.2 レスポンスボディ

| field | type | nullable | 説明 | 例 |
| --- | --- | --- | --- | --- |
| workspace_root | string | No | 探索基準ディレクトリ | `/Users/me/project` |
| workflows | string[] | No | `workspace_root` からの相対パス一覧 | `["workflows/a.yaml"]` |

### 3.3 成功レスポンス例

```json
{
  "workspace_root": "/Users/me/project",
  "workflows": [
    "workflows/main.yaml",
    "workflows/experimental.yaml"
  ]
}
```

## 4. エラー

| Status | type | message例 | 発生条件 | クライアント対応 |
| --- | --- | --- | --- | --- |
| 404 | not_found | (なし) | 未定義パス | URL確認 |

## 5. 備考

- 深さ制限なしで再帰探索し、workflow拡張子のみ返す。

## 6. 実装同期メモ

- 関連実装ファイル: `src/yagra/adapters/inbound/workflow_studio_server.py`
- 関連テスト: `tests/integration/test_workflow_studio_api.py`
- 未解決事項: なし
