# コードアーキテクチャ方針

## 採用アーキテクチャ

本プロジェクトは Hexagonal Architecture（Ports and Adapters）を採用する。

## 依存方向

- `src/yagra/adapters` -> `src/yagra/application`
- `src/yagra/application` -> `src/yagra/domain`
- `src/yagra/ports` は契約のみを保持し、実装は持たない。
- `domain` は外部ライブラリ・フレームワークへ依存しない。

## 層責務

- `domain`: エンティティ、値オブジェクト、ドメインサービス
- `application`: ユースケース、トランザクション境界、アプリケーションサービス
- `ports`: 入出力契約（抽象）
- `adapters`: Web/API/DB/外部サービス連携の実装

## 禁止事項

- domain 層で DB クエリや HTTP 呼び出しを行う。
- adapter 層へビジネスルールを複製する。
- use case で framework 依存型を直接受け取る。
