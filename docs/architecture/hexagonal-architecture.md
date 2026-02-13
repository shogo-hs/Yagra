# Hexagonal Architecture

## ディレクトリ構成

```text
src/graphyml/
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

## 開発ガイド

1. まず `domain` でビジネスルールを定義する。
2. `application` でユースケースを実装する。
3. 外部 I/O は `ports` に契約を定義する。
4. `adapters` で `ports` の実装を提供する。

## テスト戦略

- 単体テストは `domain` と `application` を中心に行う。
- 結合テストは adapter + 外部依存の接続点を検証する。
- port 契約を満たすことをインターフェーステストで確認する。
