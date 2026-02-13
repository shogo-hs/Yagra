# コーディング標準

## 設計

- SOLID と DRY を基本原則にする。
- Hexagonal Architecture を採用し、`adapters/application/domain/ports` の責務を分離する。
- 依存方向は外側から内側へ固定し、domain は外部技術へ依存しない。

## Python

- Python 3.12+ を前提にする。
- 型ヒントを必須にし、`mypy` で検証する。
- `ruff` で format/lint を統一する。
- docstring は Google style を採用し、処理意図が伝わる説明を日本語で記述する。
- docstring は短文 1 行だけで終わらせず、少なくとも概要と入出力が分かる情報を含める。
- 引数がある関数・メソッドは `Args`、戻り値がある場合は `Returns`、送出しうる例外がある場合は `Raises` を記載する。
- docstring の説明内容は型ヒントおよび実装挙動と矛盾させない。

## 環境変数

- `.env.development` / `.env.production` を利用する。
- 秘密情報は dotenvx の `encrypted:` 形式で管理する。
- `.env.keys` はコミットしない。
