# <サービス名> API エンドポイント一覧

最終更新: `<YYYY-MM-DD>`
ベースURL: `<https://api.example.com>`

## 1. 運用ルール

- API実装の変更と同時にこの一覧を更新する。
- 1エンドポイントにつき詳細ドキュメントは1ファイルにする。
- 一覧リンク切れを残さない。

## 2. 共通仕様

### 2.1 認証

- 対象: `<例: /api/v1/*>`
- ヘッダー: `<例: Authorization: Bearer <ID_TOKEN>>`
- 未認証時: `<例: 401 Unauthorized>`

### 2.2 共通ヘッダー

- `Content-Type: application/json`（ボディありの場合）
- `X-Request-Id`（任意）

### 2.3 エラーフォーマット

```json
{
  "error": {
    "message": "Authorization header is missing",
    "type": "http_error",
    "details": {
      "field": "optional"
    }
  }
}
```

### 2.4 タイムアウト・リトライ方針（任意）

- タイムアウト: `<例: 30s>`
- リトライ: `<例: GETのみ最大2回>`

## 3. エンドポイント一覧

### <ドメイン名1>

- [GET /path](./sample-get.md) - `<概要>`
- [POST /path](./sample-post.md) - `<概要>`

### <ドメイン名2>

- [PATCH /path/{id}](./sample-patch.md) - `<概要>`
- [DELETE /path/{id}](./sample-delete.md) - `<概要>`

## 4. 非推奨 / 廃止（任意）

- `GET /legacy/path` - `<廃止日/代替API>`

## 5. 変更履歴（任意）

- `<YYYY-MM-DD>`: `<変更内容要約>`
