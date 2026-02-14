# POST /api/studio/create — 新規workflow作成とターゲット設定

一覧: [Yagra Workflow Studio API エンドポイント一覧](./index.md)
最終更新: `2026-02-14`

## 1. 概要

- 目的: 新規 workflow / ui_state を生成し、Studio のアクティブターゲットに設定する。
- 利用者/権限: ローカル Studio 利用者。
- 副作用: ファイル作成（または上書き）とターゲット更新。

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
| workflow_path | string | Yes | non-empty / workspace内 / `.yaml` or `.yml` | 作成先workflowパス | `workflows/new.yaml` |
| overwrite | boolean | No | 既定 `false` | 既存ファイルを上書きするか | `true` |

### 2.5 リクエスト例

```bash
curl -X POST 'http://127.0.0.1:8787/api/studio/create' \
  -H 'Content-Type: application/json' \
  -d '{"workflow_path":"workflows/new.yaml","overwrite":false}'
```

## 3. レスポンス

### 3.1 成功レスポンス

| Status | 条件 | 説明 |
| --- | --- | --- |
| 200 | 正常終了 | 作成後のターゲットパスを返す |

### 3.2 レスポンスボディ

| field | type | nullable | 説明 | 例 |
| --- | --- | --- | --- | --- |
| workflow_path | string | No | 作成したworkflow絶対パス | `/Users/me/project/workflows/new.yaml` |
| ui_state_path | string | No | 作成したUI state絶対パス | `/Users/me/project/workflows/new.workflow-ui.json` |

### 3.3 成功レスポンス例

```json
{
  "workflow_path": "/Users/me/project/workflows/new.yaml",
  "ui_state_path": "/Users/me/project/workflows/new.workflow-ui.json"
}
```

## 4. エラー

| Status | type | message例 | 発生条件 | クライアント対応 |
| --- | --- | --- | --- | --- |
| 400 | `workflow_path must be a string` | - | `workflow_path` 型不正 | 入力修正 |
| 400 | `overwrite must be a boolean` | - | `overwrite` 型不正 | 入力修正 |
| 400 | invalid_workflow_path | workflow_path must be inside workspace_root | path不正/拡張子不正/workspace外 | 入力修正 |
| 409 | workflow_exists | workflow already exists: ... | 既存ファイルありかつ `overwrite=false` | `overwrite=true` 再実行 or 別パス |

## 5. 備考

- 初期workflow内容は最小構成（`start` → `end`）。
- 初期ui_stateは空オブジェクト。

## 6. 実装同期メモ

- 関連実装ファイル: `src/yagra/adapters/inbound/workflow_studio_server.py`
- 関連テスト: `tests/integration/test_workflow_studio_api.py`
- 未解決事項: なし
