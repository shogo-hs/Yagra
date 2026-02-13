# SOLID / DRY ガイドライン

## 目的

設計品質を一定に保つため、SOLID 原則と DRY 原則を実装判断の基準として採用する。

## SOLID

### S: Single Responsibility Principle
- 1 つのモジュールは 1 つの責務のみを持つ。
- 変更理由が複数になる実装は分割する。

### O: Open/Closed Principle
- 既存コードの破壊的変更ではなく、拡張で要件に対応する。
- 条件分岐の増殖より抽象化と差し替えを優先する。

### L: Liskov Substitution Principle
- 置換可能性を壊す継承・実装を禁止する。
- 契約を破る例外仕様や戻り値変更を避ける。

### I: Interface Segregation Principle
- 大きすぎるインターフェースを避ける。
- 利用側が必要な最小契約に分割する。

### D: Dependency Inversion Principle
- 上位層は実装ではなく抽象に依存する。
- 外部 I/O には ports を介して接続する。

## DRY

- 同一ルールが複数箇所に出現する場合は共通化する。
- ただし誤った早期抽象化は避け、責務境界が明確な共通化のみ採用する。

## 運用チェック

- 重複したバリデーションが複数 adapter に存在しないか。
- use case に技術詳細が混入していないか。
- テストしづらい密結合が発生していないか。
