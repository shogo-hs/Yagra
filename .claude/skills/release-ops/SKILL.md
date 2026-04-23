---
name: release-ops
description: Yagra のバージョンリリース実行スキル。Semantic Versioning に従い、CHANGELOG.md（日本語正本）/ docs/sphinx/source/changelog.md（英語）/ GitHub Release（英語）を同期し、pyproject.toml の version と一致させる。Keep a Changelog 形式を遵守する。リリース実行・バージョンバンプ依頼で使う。
---

# リリース運用

Yagra のリリースは 3 箇所の変更履歴を同期する必要がある。本スキルはその手順を規定する。

## 実行フロー

1. リリース範囲を確認する。
   - 前回リリースタグからの `git log --oneline <last-tag>..HEAD` を確認する。
   - 変更を `Added / Changed / Deprecated / Removed / Fixed / Security` に分類する。
   - 破壊的変更の有無を明示する。

2. バージョン番号を決定する（Semantic Versioning）。
   - MAJOR: 破壊的変更
   - MINOR: 後方互換な機能追加
   - PATCH: 後方互換なバグ修正
   - 確定したバージョンを `NEW_VERSION` として以後の手順で使う。

3. `pyproject.toml` の `version` を更新する。
   - `[project]` セクションの `version = "X.Y.Z"` を `NEW_VERSION` に変更する。
   - `uv lock` を実行してロックファイルを更新する。

4. `CHANGELOG.md`（ルート、日本語、正本）を更新する。
   - Keep a Changelog 形式（https://keepachangelog.com/ja/）を厳守する。
   - `[Unreleased]` セクションの項目を `[NEW_VERSION] - YYYY-MM-DD` へ移す。
   - セクション見出しは `Added / Changed / Deprecated / Removed / Fixed / Security` のみを使用する。
   - 末尾のリンク参照（`[NEW_VERSION]: https://.../compare/...`）も更新する。

5. `docs/sphinx/source/changelog.md`（英語、ユーザー向け）を同期する。
   - ルート `CHANGELOG.md` の NEW_VERSION 分を英訳して追加する。
   - ユーザー視点で重要な変更のみを要約する（内部リファクタは含めない）。
   - Sphinx ビルド対応の Markdown 構文を使う。

6. コミットとタグを作成する。
   - `git add pyproject.toml uv.lock CHANGELOG.md docs/sphinx/source/changelog.md`
   - `git commit -m "chore: vNEW_VERSION リリース"`（50 文字以内）
   - `git tag -a vNEW_VERSION -m "Release vNEW_VERSION"`

7. プッシュする。
   - `git push origin <branch>`
   - `git push origin vNEW_VERSION`

8. GitHub Release を作成する（英語、詳細説明付き）。
   - `gh release create vNEW_VERSION --title "vNEW_VERSION" --notes-file <tempfile>`
   - 内容は `docs/sphinx/source/changelog.md` の該当セクションをベースに、より詳細な説明を追加する。
   - 破壊的変更がある場合は "⚠️ Breaking Changes" セクションを冒頭に置く。

9. 結果を報告する。
   - リリースされたバージョン
   - 同期した 3 箇所のリンク（CHANGELOG 該当アンカー、Sphinx 該当アンカー、GitHub Release URL）
   - 付与したタグ

## 厳守ルール

- **3 箇所の変更履歴同期は必須**（CHANGELOG.md / Sphinx / GitHub Release）。どれか一つでも欠けたらリリース未完了とする。
- `CHANGELOG.md` が正本で日本語、Sphinx と GitHub Release は英語。
- `pyproject.toml` の `version` は `NEW_VERSION` と完全一致させる。
- Keep a Changelog のセクション見出し以外は使わない（カスタム見出し禁止）。
- リリース前に `uv run pre-commit run --all-files` と `uv run pytest` が全てパスすることを確認する。
- 破壊的変更がある場合は MAJOR バンプを強制する。

## 参照

- Keep a Changelog: https://keepachangelog.com/ja/1.1.0/
- Semantic Versioning: https://semver.org/lang/ja/
