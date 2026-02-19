# プロダクトビジョン

最終更新: 2026-02-19 <!-- 競合分析を踏まえた差別化戦略を反映 -->

## 1. Vision Statement

Yagra は、YAML 定義から LangGraph の StateGraph を動的に構築する
Declarative LangGraph Builder を中核に、
非エンジニアも参加できる Workflow Studio 体験（WebUI 可視化・編集）へ拡張する。
さらに、コーディングエージェントがワークフローを自動生成・検証できる AI-Native な基盤を提供し、
将来的にはプロンプト自動最適化との統合を見据える。
ロジックと構成を分離したまま、チーム全体の改善サイクルを高速化する。

**差別化ポジション**：LangFlow・Flowise・Dify 等のノーコード GUI ツールとは異なり、
Yagra は「エンジニアが YAML で書き、Git で管理し、CI で検証し、エージェントが生成する」
Code-First × Git-Native なワークフロー基盤を提供する。
LangGraph の全能力（checkpointer・HITL・並列実行）を宣言型 YAML で包み、
チームの改善サイクルを PR ベースで回せる唯一の OSS ツールを目指す。

## 2. 対象ユーザー

- LangGraph を使う LLM アプリケーション開発者（コアターゲット）
- プロンプトやフロー改善に関わる PM / ドメインエキスパート
- ワークフロー改善に参加する非エンジニア（業務担当者・オペレーター）
- コーディングエージェント（Codex, Claude Code, Gemini 等）を活用してワークフローを自動生成する開発者
- 承認・レビューフローを AI ワークフローに組み込みたいエンタープライズ開発者（G-09 HITL 対象）
- GitHub Actions / CI パイプラインでワークフロー品質を担保したい DevOps エンジニア

## 3. 解決する課題

- LangGraph のフロー構造やプロンプト設定が Python コードと密結合し、改善のたびに実装コストが高い。
- 処理順序や条件分岐の調整をエンジニアしか行えず、PDCA サイクルが遅くなる。
- YAML を直接編集する運用は、非エンジニアにとって認知負荷と誤編集リスクが高い。
- ワークフロー定義の自動生成に必要なスキーマ情報が機械可読な形で提供されておらず、コーディングエージェントが正確なワークフローを生成できない。
- LangFlow・Flowise 等の GUI ツールは Git 管理・CI 統合・差分レビューができず、チーム開発・本番運用での品質担保が困難。
- AI ワークフローで人間の承認・確認を挟むには LangGraph の checkpointer を手動で実装する必要があり、開発コストが高い。
- ワークフロー定義の変更が本番に影響するリスクを実行前に検証する手段がない（GitHub Actions 等との統合不足）。

## 4. 提供価値

### コア価値（Terraform for LangGraph）
- Schema-Driven: Pydantic スキーマで YAML 記述ミスを早期検知する。
- Registry Pattern: YAML 上の文字列定義と Python 関数を疎結合に接続する。
- Zero-Boilerplate: グラフ構築コードを毎回書かず、YAML 差し替えで異なるワークフローを実行できる。

### Git-Native ワークフロー管理
- Git-First: ワークフロー定義が YAML ファイルであるため、Git によるバージョン管理・差分レビュー・ロールバックが自然に実現する。
- CI Integration: `yagra validate` を GitHub Actions 等の CI パイプラインに組み込み、PR ごとにワークフロー品質を自動検証できる。
- Team Collaboration: 非エンジニアは WebUI で編集し、エンジニアは YAML を直接修正し、全員が PR ベースでレビューに参加できる。

### Visual-First WebUI
- Visual-First: まず WebUI でワークフローを可視化し、構造理解とレビューを容易にする。
- Safe Editing: 次段階で WebUI 上の編集機能を提供し、非エンジニアでも prompt/model/遷移条件を調整できる。
- Usability-First: 編集可能な状態で止めず、情報設計・視認性・操作導線を継続改善して「迷わず使える」体験へ引き上げる。
- Data Flow Visibility: グラフ上の各ノードが要求する入力変数と生成する出力変数をバッジで可視化し、ワークフロー全体のデータフローを視覚的に追跡できる。

### AI-Native インターフェース
- AI-Ready Schema: JSON Schema を公開し、コーディングエージェントが正確なワークフロー YAML を生成できる基盤を提供する。スキーマには意味情報（description/examples）を含め、エージェントがスキーマ単体で有効な YAML を構成できる水準を目指す。
- Validate Feedback Loop: 構造化されたバリデーション結果を返し、エージェントが自律的にエラー修正ループを回せる。修正提案（suggestion/候補値）を含めることで、エージェントの修正精度を高める。
- Template Library: 典型パターン（分岐・ループ・RAG・マルチエージェント・HITL 等）のテンプレートを提供し、エージェントおよび開発者の生成精度と立ち上がり速度を向上させる。
- Handler Discoverability: ハンドラーが受け付けるパラメータ構造を機械可読な形で公開し、エージェントが正しい `params` を生成できるようにする。
- Agent-Native Interface: stdin 対応・MCP サーバー公開など、エージェントが CLI を超えて直接ツールとして Yagra 機能を呼び出せるインターフェースを提供する。

### Human-in-the-Loop（LangGraph ネイティブ）
- Human-in-the-Loop: YAML 宣言だけでワークフローの中断・再開ポイントを定義でき、LangGraph の checkpointer と連携して人間のレビュー・承認・修正を実行フローに組み込める。GUI ツールでは実現できないコードレベルの制御を、宣言型で提供する。

## 5. 成功状態

### 既達成（v0.6.0 時点）
- 開発チームが Python コード変更なしで、YAML 更新のみでフロー構成変更を反映できる。
- 主要な設定ミス（ノード参照不整合、必須パラメータ欠落）を実行前に検出できる。
- 非エンジニアが WebUI 上でフローを理解・レビューできる（可視化フェーズ）。
- 非エンジニアが WebUI 上で prompt/model/接続を調整し、PoC を短サイクルで回せる（編集フェーズ）。
- 非エンジニアが WebUI 上で主要操作（ノード追加・接続変更・保存）を補助なしで完了できる（UX 高度化フェーズ）。
- コーディングエージェントが JSON Schema を参照して有効なワークフロー YAML を生成できる（AI-Native フェーズ）。
- 生成された YAML を `yagra validate` で検証し、エラーがあれば構造化フィードバックで修正ループを回せる（AI-Native フェーズ）。
- エージェントがスキーマの意味情報とバリデーションの修正提案を活用し、人間の介入なしに生成→検証→修正ループを完結できる（AI-Native 深化フェーズ）。
- `yagra explain` でワークフロー構造を実行前に把握し、`yagra handlers` でハンドラーのパラメータ仕様を発見できる（AI-Native 深化フェーズ）。
- MCP サーバー経由でエージェントが CLI を介さず直接 Yagra 機能を呼び出せる（AI-Native 深化フェーズ）。
- WebUI のグラフ上で各ノードの入力変数（プロンプトが要求する `{変数名}`）と出力変数（`output_key`）をバッジとして確認でき、どのノードで何が消費・生成されるかを一目で把握できる（Data Flow Visibility フェーズ）。

### 次フェーズ目標
- YAML に `interrupt_before` / `interrupt_after` を記述するだけで、ワークフロー実行中に人間の判断を挟み、修正を反映して再開できる（HITL フェーズ）。
- `yagra validate` を GitHub Actions に組み込み、PR ごとにワークフロー変更を自動検証できる（Git-Native フェーズ）。
- multi-agent・tool-use・human-review 等のテンプレートが充実し、`yagra init --list` でユースケース別に選択できる（テンプレート拡充フェーズ）。
- LangFlow・Flowise 等の GUI ツールでは実現困難な「コードレビュー → CI 検証 → 本番デプロイ」パイプラインが Yagra + Git で完結できる（Git-Native ワークフロー管理フェーズ）。

## 6. 将来展望

- プロンプト自動最適化（DSPy, Agent Lightning 等）との統合を視野に入れる。Yagra の `prompt_ref` による プロンプト分離構造は、外部オプティマイザーとの統合に適した設計であり、Optimizer Port のインターフェース設計を将来課題とする。
- 「AI がワークフローを生成し、AI がプロンプトを最適化し、人間がレビュー・承認する」サイクルを YAML + Git ベースで実現することを長期目標とする。HITL 機能（`interrupt_before` / `interrupt_after` + checkpointer）はこのサイクルにおける「人間がレビュー・承認する」部分の実行基盤となる。
- MCP (Model Context Protocol) サーバーとして Yagra の検証・解析・テンプレート・ハンドラー情報を公開し、エージェントが統一的なツール呼び出しプロトコルで Yagra を操作できる環境を整える。これにより CLI 依存を脱却し、エージェントフレームワーク間の相互運用性を確保する。
- GitHub Actions 公式アクション（`yagra-ai/validate-action`）を提供し、PR ごとのワークフロー自動検証を 1 行で組み込めるエコシステムを構築する。
- VS Code Extension による YAML エディタ統合（スキーマバリデーション・プレビュー・テンプレート挿入）を提供し、開発者体験を向上させる。

## 7. Vision の再設定ルール

- LangGraph 以外の実行基盤への主軸変更を判断した時点で見直す。
- エンジニア外ユーザーの改善サイクル時間が短縮しない場合は仮説を再評価する。
- WebUI 可視化・編集を導入しても PoC 速度が改善しない場合は、提供価値の優先順位を再定義する。
- WebUI が「機能的には編集可能」でも、初見ユーザーの操作完了率が上がらない場合は UX 要件を再定義する。
- AI-Native 機能（JSON Schema 公開・validate CLI）を導入しても、コーディングエージェントの生成精度が実用水準に達しない場合は、提供手段を再評価する。
- AI-Native 深化（スキーマ意味情報・修正提案・MCP サーバー）を導入しても、エージェントの自律生成→修正ループの完結率が向上しない場合は、インターフェース設計を根本的に見直す。
- 競合ツール（LangFlow・Flowise 等）が「YAML 定義 × LangGraph ネイティブ × Git 管理」の軸でキャッチアップしてきた場合は、差別化軸を再評価する。
- HITL 機能を実装しても、エンタープライズユーザーの承認フロー要件を満たさない場合は、要件定義から再設計する。

## 8. 関連ドキュメント

- ユーザー到達状態ゴール: `docs/product/goals.md`
- 到達ステップと実装項目: `docs/product/milestones.md`
