# Yagra Workflow Studio API エンドポイント一覧

最終更新: `2026-02-14`
ベースURL: `http://127.0.0.1:<port>`（`yagra studio --port <port>`）

## 1. 運用ルール

- API実装の変更と同時にこの一覧と個票を更新する。
- 1エンドポイントにつき詳細ドキュメントは1ファイルにする。
- 実装の一次情報は `src/yagra/adapters/inbound/workflow_studio_server.py` とする。

## 2. 共通仕様

### 2.1 認証

- 認証: なし（ローカル Studio サーバー前提）。

### 2.2 共通ヘッダー

- `Content-Type: application/json`（POSTでJSONボディを送る場合）

### 2.3 共通エラー形式

```json
{
  "error": "invalid_json",
  "message": "request body is not valid JSON: ..."
}
```

補足:
- `error` は必須。
- `message` はエラー種別に応じて付与される。
- `404` の未知パスは `{ "error": "not_found" }`。

### 2.4 主要エラーコード

- `studio_target_required` (`409`): workflow ターゲット未選択。
- `revision_conflict` (`409`): `base_revision` が最新と不一致。
- `validation_failed` (`422`): 保存候補の workflow 検証失敗。
- `load_failed` (`422`): workflow/ui_state 読み込み失敗。
- `yaml_file_exists` (`409`): YAML保存時に overwrite=false かつ既存ファイルあり。

## 3. エンドポイント一覧

### Studio Target / Workspace

- [GET /api/studio/target](./get-studio-target.md) - 現在の編集ターゲット情報を取得
- [GET /api/studio/files](./get-studio-files.md) - workspace 配下の workflow / yaml 候補一覧を取得
- [POST /api/studio/open](./post-studio-open.md) - 既存 workflow を編集ターゲットとして開く
- [POST /api/studio/create](./post-studio-create.md) - 新規 workflow を作成して開く
- [POST /api/studio/file/read](./post-studio-file-read.md) - workspace 配下の YAML ファイル内容を取得
- [POST /api/studio/file/save](./post-studio-file-save.md) - workspace 配下の YAML ファイルを作成/更新

### Workflow Read / Edit

- [GET /api/workflow](./get-workflow.md) - 現在の workflow/ui_state/revision を取得
- [GET /api/workflow/form](./get-workflow-form.md) - フォーム編集向け workflow ビューを取得
- [POST /api/workflow/diff](./post-workflow-diff.md) - 候補 workflow の差分を取得
- [POST /api/workflow/form/preview](./post-workflow-form-preview.md) - フォーム入力から候補 workflow を生成して差分取得
- [POST /api/workflow/catalogs/preview](./post-workflow-catalogs-preview.md) - （Legacy）prompt catalog 参照設定と候補キーを確認
- [POST /api/workflow/save](./post-workflow-save.md) - 候補 workflow を保存（backup作成）
- [POST /api/workflow/rollback](./post-workflow-rollback.md) - backup 指定で復元

## 4. 非推奨 / 廃止

- `model_ref` は廃止。`workflow.nodes[].params.model` をインライン指定する。
- `prompt_catalog` は Studio 現行UIでは非推奨（Node Properties の `prompt yaml` 運用を使用）。

## 5. 変更履歴

- `2026-02-14`: `model_ref` 廃止、prompt file read/save API 追加、一覧を実装準拠へ更新。
- `2026-02-14`: `/api/studio/file/read` に `prompt_entries` を追加。Studio UI は `prompt yaml` 選択 + 未選択時自動生成フローへ更新。
