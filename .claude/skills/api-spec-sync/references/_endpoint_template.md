# <METHOD> <PATH> — <機能名>

一覧: [<サービス名> API エンドポイント一覧](<indexファイルへの相対パス>)
最終更新: `<YYYY-MM-DD>`

## 1. 概要

- 目的: `<このAPIが何をするか>`
- 利用者/権限: `<例: ログイン済みユーザーのみ>`
- 副作用: `<例: DBへ保存 / 非同期ジョブ起動>`

## 2. リクエスト

### 2.1 ヘッダー

| 項目 | 必須 | 値 | 説明 |
| --- | --- | --- | --- |
| Authorization | Yes | Bearer `<ID_TOKEN>` | 認証が必要な場合 |
| Content-Type | Conditional | application/json | ボディありの場合 |

### 2.2 パスパラメータ

| name | type | required | 説明 | 例 |
| --- | --- | --- | --- | --- |
| id | string | Yes | 対象ID | `abc123` |

> パスパラメータがない場合は「なし」と明記する。

### 2.3 クエリパラメータ

| name | type | required | デフォルト | 説明 | 例 |
| --- | --- | --- | --- | --- | --- |
| limit | integer | No | 20 | 取得件数 | `10` |

> クエリパラメータがない場合は「なし」と明記する。

### 2.4 リクエストボディ

| field | type | required | 制約 | 説明 | 例 |
| --- | --- | --- | --- | --- | --- |
| title | string | Yes | 1..120文字 | タイトル | `日報` |

> ボディがない場合は「なし」と明記する。

### 2.5 リクエスト例

```bash
curl -X <METHOD> '<BASE_URL><PATH>' \
  -H 'Authorization: Bearer <ID_TOKEN>' \
  -H 'Content-Type: application/json' \
  -d '{"example":"value"}'
```

## 3. レスポンス

### 3.1 成功レスポンス

| Status | 条件 | 説明 |
| --- | --- | --- |
| 200 | 正常終了 | 成功データを返す |

### 3.2 レスポンスボディ

| field | type | nullable | 説明 | 例 |
| --- | --- | --- | --- | --- |
| id | string | No | リソースID | `abc123` |

### 3.3 成功レスポンス例

```json
{
  "id": "abc123"
}
```

## 4. エラー

| Status | type | message例 | 発生条件 | クライアント対応 |
| --- | --- | --- | --- | --- |
| 400 | validation_error | invalid request | パラメータ不正 | 入力修正 |
| 401 | http_error | unauthorized | 認証失敗 | 再ログイン |
| 404 | http_error | not found | 対象なし | 画面再読込 |
| 500 | internal_error | internal server error | サーバー異常 | リトライ/問い合わせ |

## 5. 備考

- タイムアウト: `<例: 30s>`
- 冪等性: `<例: Idempotency-Keyで担保>`
- 非同期処理: `<例: 202でjob_id返却>`

## 6. 実装同期メモ

- 関連実装ファイル: `<path/to/router>`, `<path/to/handler>`
- 関連テスト: `<path/to/test>`
- 未解決事項: `<TODO(要実装確認)>`
