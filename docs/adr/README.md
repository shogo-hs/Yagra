# ADR 一覧

このディレクトリは Architecture Decision Record（ADR）を保存する。

## 目的

- 設計判断の背景・採否理由・影響を時系列で追跡可能にする。
- ルール変更時に「なぜそうしたか」を再確認できるようにする。

## 命名規則

- 形式: `NNNN-short-title.md`
- 例: `0001-record-architecture-decisions.md`
- `NNNN` は 4 桁連番を使用する。

## ステータス

- `提案(proposed)`
- `承認済み(accepted)`
- `却下(rejected)`
- `置換済み(superseded)`

## 作成ルール

- 新規ADRは `docs/ai/playbook-assets/adr-management/references/_adr-template.md` を利用する。
- 1ADR には 1 つの判断だけを記載する。
- 既存判断を置換した場合は、新旧ADRの双方に相互リンクを張る。

## ADR 一覧

- [0001: ADR運用を導入して設計判断を記録する](./0001-record-architecture-decisions.md) - 承認済み(accepted)
