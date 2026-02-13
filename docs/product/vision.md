# プロダクトビジョン

最終更新: 2026-02-13

## 1. Vision Statement

Yagra は、YAML 定義から LangGraph の StateGraph を動的に構築する
Declarative LangGraph Builder として、エージェントのロジックと構成を分離する。
Python 実装の柔軟性を維持したまま、非エンジニアを含むチームで改善サイクルを高速化する。

## 2. 対象ユーザー

- LangGraph を使う LLM アプリケーション開発者
- プロンプトやフロー改善に関わる PM / ドメインエキスパート

## 3. 解決する課題

- LangGraph のフロー構造やプロンプト設定が Python コードと密結合し、改善のたびに実装コストが高い。
- 処理順序や条件分岐の調整をエンジニアしか行えず、PDCA サイクルが遅くなる。

## 4. 提供価値

- Schema-Driven: Pydantic スキーマで YAML 記述ミスを早期検知する。
- Registry Pattern: YAML 上の文字列定義と Python 関数を疎結合に接続する。
- Zero-Boilerplate: グラフ構築コードを毎回書かず、YAML 差し替えで異なるワークフローを実行できる。

## 5. 成功状態

- 開発チームが Python コード変更なしで、YAML 更新のみでフロー構成変更を反映できる。
- 主要な設定ミス（ノード参照不整合、必須パラメータ欠落）を実行前に検出できる。

## 6. Vision の再設定ルール

- LangGraph 以外の実行基盤への主軸変更を判断した時点で見直す。
- エンジニア外ユーザーの改善サイクル時間が短縮しない場合は仮説を再評価する。

## 7. 関連ドキュメント

- ユーザー到達状態ゴール: `docs/product/goals.md`
- 到達ステップ: `docs/product/milestones.md`
- 現在地スコアボード: `docs/product/progress.md`
