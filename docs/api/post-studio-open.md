# POST /api/studio/open — 既存workflowを編集ターゲットとして開く

一覧: [Yagra Workflow Studio API エンドポイント一覧](./index.md)
最終更新: `2026-02-14`

## 1. 概要

- 目的: 既存 workflow を Studio のアクティブターゲットに設定する。
- 利用者/権限: ローカル Studio 利用者。
- 副作用: サーバー内の現在ターゲットを更新する。

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
| workflow_path | string | Yes | non-empty / workspace内 / `.yaml` or `.yml` | 開くworkflowパス（相対または絶対） | `workflows/main.yaml` |

### 2.5 リクエスト例

```bash
curl -X POST 'http://127.0.0.1:8787/api/studio/open' \
  -H 'Content-Type: application/json' \
  -d '{"workflow_path":"workflows/main.yaml"}'
```

## 3. レスポンス

### 3.1 成功レスポンス

| Status | 条件 | 説明 |
| --- | --- | --- |
| 200 | 正常終了 | ターゲット更新後のパスを返す |

### 3.2 レスポンスボディ

| field | type | nullable | 説明 | 例 |
| --- | --- | --- | --- | --- |
| workflow_path | string | No | 開いたworkflow絶対パス | `/Users/me/project/workflows/main.yaml` |
| ui_state_path | string | No | 対応するUI state絶対パス | `/Users/me/project/workflows/main.workflow-ui.json` |

### 3.3 成功レスポンス例

```json
{
  "workflow_path": "/Users/me/project/workflows/main.yaml",
  "ui_state_path": "/Users/me/project/workflows/main.workflow-ui.json"
}
```

## 4. エラー

| Status | type | message例 | 発生条件 | クライアント対応 |
| --- | --- | --- | --- | --- |
| 400 | `workflow_path must be a string` | - | `workflow_path` 型不正 | 入力修正 |
| 400 | invalid_workflow_path | workflow_path must be inside workspace_root | path不正/拡張子不正/workspace外 | 入力修正 |
| 404 | workflow_not_found | workflow not found: ... | 対象ファイルが存在しない | パス確認 |

## 5. 備考

- `ui_state_path` は `--ui-state` 指定時はその固定パス、未指定時は `<workflow>.workflow-ui.json`。

## 6. 実装同期メモ

- 関連実装ファイル: `src/yagra/adapters/inbound/workflow_studio_server.py`
- 関連テスト: `tests/integration/test_workflow_studio_api.py`
- 未解決事項: なし
