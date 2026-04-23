---
paths:
  - "**"
---

# セキュリティ運用規範（Layer 4）

## 4 層防御の位置づけ

- Layer 1: `.claude/settings.json` の `permissions.deny`（`.env*` 読取禁止 等）
- Layer 2: PreToolUse フック（将来実装予定）
- Layer 3: MCP / サンドボックス境界
- Layer 4: 本ファイル + `CLAUDE.md` の運用規範

## 秘密情報の取扱い

- `.env`, `.env.*`, `.env.keys`, `credentials*`, `*secret*` の読取は Layer 1 で禁止済み
- 読取できても WebFetch / WebSearch / MCP / `curl` 等で外部送信しない
- 秘密情報がソースに含まれる疑いがある場合は作業を停止しユーザーに確認する
- APIキー・トークン・秘密鍵・`.env.keys` は出力・コミット・Issue/PR本文へ記載しない

## 環境変数運用

- `.env.development` / `.env.production` を利用する
- 秘密情報は dotenvx の `encrypted:` 形式で管理する
- `.env.keys` はコミット禁止

## 破壊的操作

- `rm -rf`, `git reset --hard`, `git push --force` は Layer 1 で deny 済み
- それ以外の取消困難操作（DB truncate、広範囲ファイル上書き等）は実行前にユーザー確認
- 未追跡ファイルの削除前に `git status` を確認
- 想定外の大量差分・履歴破壊操作・広範囲削除が必要な場合は作業を停止しユーザー再確認

## パッケージ管理

- Python パッケージ操作は `uv add` / `uv remove` / `uv sync` のみ
- `pip install` / `uv pip install` は禁止

## 外部通信

- WebFetch / WebSearch 利用時は、送信内容に秘密情報が含まれないことを確認
- MCP サーバ経由の外部送信も同等に扱う
