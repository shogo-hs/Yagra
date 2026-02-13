# `.env.*` と dotenvx 運用ガイド

## 基本方針

- 環境変数は `.env.development` と `.env.production` で分離する。
- 機密情報は dotenvx で `encrypted:` 形式にして管理する。
- `.env.example` は本運用では原則作成しない（dotenvx 管理と役割が重複するため）。
- 秘密鍵を含む `.env.keys` は Git 管理しない。

## ファイル責務

- `.env.development`: 開発環境で使う値を保持する（機密は暗号文、非機密は平文可）。
- `.env.production`: 本番環境で使う値を保持する（機密は暗号文、非機密は平文可）。
- `.env.keys`: 復号に必要な秘密鍵を保持する（絶対にコミットしない）。

## 初期セットアップ

```bash
# dotenvx をグローバルインストール（Linux/macOS）
curl -sfS https://dotenvx.sh | sudo sh

# バージョン確認
dotenvx --version
```

## 初回暗号化フロー

1. まず環境別ファイルを用意する。

```dotenv
# .env.development
DATABASE_URL="postgresql://localhost:5432/app_dev"
API_KEY="dev-secret"
```

```dotenv
# .env.production
DATABASE_URL="postgresql://db.internal:5432/app_prod"
API_KEY="prod-secret"
```

2. 各ファイルを暗号化する。

```bash
dotenvx encrypt -f .env.development
dotenvx encrypt -f .env.production
```

3. 暗号化後の状態を確認する。

- `.env.development` / `.env.production` に `DOTENV_PUBLIC_KEY_<ENV>` と `encrypted:` 値が入る。
- `.env.keys` に `DOTENV_PRIVATE_KEY_<ENV>` が追加される。

## 実行方法

```bash
# 開発設定で実行
dotenvx run -f .env.development -- uv run python -m your_package

# 本番設定で実行
dotenvx run -f .env.production -- uv run python -m your_package
```

Python 側は通常の `os.environ[...]` で取得する。

## 値の追加・更新

機密値は `dotenvx set` を使って更新する。

```bash
dotenvx set NEW_SECRET "my_new_secret_value_development" -f .env.development
dotenvx set NEW_SECRET "my_new_secret_value_production" -f .env.production
```

- 既存ファイルに `encrypted:` 形式で追記/更新される。
- 手編集で平文機密を入れない（更新は `dotenvx set` を優先）。

## 平文と暗号文の混在ルール

- `encrypted:` プレフィックス付きは機密値として扱われる。
- プレフィックスがない値は平文としてそのまま注入される。
- したがって、モデル名・URL・フラグなど非機密は平文で管理してよい。

例:

```dotenv
DOTENV_PUBLIC_KEY_DEVELOPMENT="<PUBLIC_KEY>"

# 機密
API_KEY="encrypted:..."

# 非機密
MODEL_NAME="gpt-4.1-mini"
API_BASE_URL="https://api.example.com"
```

## コミット/共有ポリシー

- コミットしてよい:
  - `.env.development`（機密は `encrypted:` に限る）
  - `.env.production`（機密は `encrypted:` に限る）
- コミットしてはいけない:
  - `.env.keys`
  - `DOTENV_PRIVATE_KEY_*` の値を含むあらゆるログ・メッセージ

`.env.keys` のチーム共有が必要な場合:

- パスワードマネージャー等の安全な私的チャネルのみ使用する。
- Issue/PR 本文、チャット公開チャンネル、CI ログへ貼り付けない。
- 漏えいが疑われる場合は即時キーをローテーションする。

## チェックポイント

- `.gitignore` に `.env.keys` が含まれている。
- `.env.*` の機密値が `encrypted:` になっている。
- 実行コマンド例として `dotenvx run -f ... -- <command>` が README/運用手順にある。
- `.env.example` を前提にした運用説明が残っていない。
