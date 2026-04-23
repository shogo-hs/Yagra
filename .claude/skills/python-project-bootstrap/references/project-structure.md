# Pythonプロジェクト構成ガイド（Hexagonal + SOLID/DRY）

## 設計原則

- Outside-In ではなく Inside-Out で依存を管理する。
- 依存方向は `adapters -> application -> domain` を基本にし、`domain` は外部技術へ依存しない。
- 外部 I/O は `ports`（インターフェース）で抽象化し、実装は `adapters` に閉じ込める。
- 重複ロジックは utility 化ではなく、責務が正しい層へ移動して DRY を満たす。

## 推奨ディレクトリ

```text
src/<package_name>/
  adapters/
    inbound/
    outbound/
  application/
    use_cases/
    services/
  domain/
    entities/
    value_objects/
    services/
  ports/
    inbound/
    outbound/
```

補助:

```text
tests/
  unit/
  integration/
```

## 層ごとの責務

- `domain`
  - ビジネスルール、エンティティ、不変条件。
  - フレームワーク、DB、HTTP クライアントへ依存しない。

- `application`
  - ユースケースのオーケストレーション。
  - `ports` を経由して外部と連携する。

- `ports`
  - ユースケースが必要とする入出力契約（抽象）を定義する。
  - 実装の詳細を持ち込まない。

- `adapters`
  - Web/API、DB、メッセージング、外部APIなど技術依存実装。
  - `ports` 実装として application/domain を利用する。

## SOLID 適用ポイント

- SRP: 1 モジュール 1 責務。ユースケースと I/O 詳細を分離する。
- OCP: 新規要件は adapter 追加で対応し、domain 変更を最小化する。
- LSP: 派生実装は port 契約を破らない。
- ISP: port を小さく分割し、不要メソッドを持たせない。
- DIP: application は concrete adapter ではなく port 抽象に依存する。

## DRY 適用ポイント

- 同一バリデーションを各 adapter に重複させない。domain/application に集約する。
- 例外変換ルールは application 境界で共通化する。
- ログフォーマットやエラーレスポンス整形は共通モジュールに寄せる。

## 実装時の禁止事項

- domain から ORM モデルや HTTP クライアントを直接呼び出す。
- use case にフレームワーク依存オブジェクトを直接渡す。
- adapter 内にビジネスルールを複製する。
