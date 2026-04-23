---
paths:
  - "src/yagra/**"
  - "tests/**"
---

# Yagra Architecture Rules

## Hexagonal 境界

Yagra は Hexagonal Architecture を採用する。依存方向は外側から内側へ固定する。

- `domain/`: ドメインエンティティ・サービス。外部技術へ依存しない
- `ports/`: 境界を定義するインターフェース
- `application/`: ユースケース・サービス。`domain` と `ports` のみを参照
- `adapters/`: `ports` の具象実装（inbound: CLI/API、outbound: DB/ファイル/HTTP）

## 禁止事項（機械的チェック対象）

- `domain/` 内で `adapters` / `application` を import しない
- `domain/` 内に I/O コード（HTTP、DB、ファイル読書き）を書かない
- `application/` から adapters 実装を直接参照しない（ports 経由で）
- `ports/` に具象実装を書かない（インターフェース定義のみ）

## SOLID 原則

- Single Responsibility: 1 モジュール 1 責務
- Open/Closed: 拡張に開き、変更に閉じる
- Liskov Substitution: 派生型は基底型と置換可能
- Interface Segregation: クライアント固有のインターフェース
- Dependency Inversion: 抽象に依存（具象に依存しない）

## 変更時のチェックポイント

- import 文を確認し、逆方向依存がないことを検証
- 新規ファイルの配置先が責務に合っているか
- `docs/rules/code_architecture/` と `docs/rules/solid/` のルールに整合しているか

## 参照

- @docs/rules/code_architecture/README.md
- @docs/rules/solid/README.md
- @docs/architecture/hexagonal-architecture.md
