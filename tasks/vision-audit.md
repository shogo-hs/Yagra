# Yagra ビジョン整合性監査レポート

**実施日**: 2026-04-23
**目的**: `docs/product/vision.md` と実装の整合性を「誤魔化し」「使いにくさ」「ビジョン体現度」の観点で検証
**方式**: 読み取り専用。並列サブエージェント6本で分担調査（Explore 1 + general-purpose 4 + architecture-reviewer 1。うち1本再実行で Studio詳細のみ直接読取補完）
**ベース**: Goal G-01..G-26 / Milestone M-01..M-58 すべて Done 記載

---

## 0. 結論（300字）

Yagra のコア機能（Build/Run/Analyze/Apply のサイクル、MCP 11 ツール、Pydantic スキーマ、Template Library、Golden Test）は実装が揃い、「Langfuse/Datadog 型ダッシュボードを作らない」「Local-First」「MCP 特化」という**差別化軸のうち「何を作らないか」側は高水準で守られている**。誤魔化し痕跡（TODO/NotImplementedError/裸 except）は src/ 内にほぼ皆無、CI は 80% カバレッジ閾値で運用中。一方で **「AI が AI を評価・改善」という最重要差別化軸のコードが 1 行も存在しない**（`judge` / `self-improve` / `grading` は src/ 内 0 ヒット）、**README 代表例 `examples/llm-basic/workflow.yaml` が自身の validator を通らない**、**CI 統合ガイドが参照する `.github/workflows/validate-example.yml` が欠落**、**optimization cycle の 30分 DoD に計測根拠なし**という"入口と看板"の綻びが複数残る。また Hexagonal 境界違反とモジュール肥大化（studio_server 5090行、__init__ 1309行）が構造負債として沈殿している。

---

## 1. スコア（1-5、ベースライン）

| 観点 | スコア | 評価 |
|------|:------:|------|
| ビジョン要素の体現度（機能網羅） | 4 | 主要 12 要素中 11 が Embodied、1 が Superficial |
| 差別化軸の実装度（AI が AI を改善） | 2 | コード 0件。ビジョン最重要軸が看板のみ |
| 原則遵守度（Local-First / 人間ダッシュボード排除） | 5 | 完全遵守。src/ に違反 0 件 |
| UX 一貫性（入口体験〜サイクル完結） | 3 | 代表サンプル破綻、CI統合ファイル欠落で -2 |
| 誤魔化し耐性（TODO/サイレント失敗/Done ラベル） | 4 | サイレント失敗 2 箇所のみ、運用型 CI が 80% gate |
| Hexagonal 純度 | 2 | domain→application 逆依存 1 件、I/O 混入 1 件、application→adapters 具象 new 複数 |
| SRP 遵守 | 1 | 5090 行の studio_server、1309 行の __init__、838 行の god class |
| API 一貫性（Yagra/CLI/MCP） | 4 | 命名・引数形式は良好、エラーコード構造化余地あり |
| エラーメッセージ品質（AI 修復可能性） | 4 | severity/context/fuzzy match が機能、修復適性高 |
| Golden Test 実効性 | 4 | 決定論再現 OK、LLM 出力回帰は原理的に検出不能 |
| E2E 実走性 | 2 | ダミー handler + tmp_path + 関数直接呼出、実 LLM シナリオ欠落 |

---

## 2. 整合している実装（強い体現）

| 領域 | 内容 | 根拠 |
|------|------|------|
| Schema-Driven YAML | `extra="forbid"`, description/examples 充実 | `src/yagra/domain/entities/graph_schema.py` |
| Registry Pattern | YAML `handler` 文字列 ↔ Python callable の疎結合 | `src/yagra/adapters/outbound/in_memory_node_registry.py` |
| MCP 11 ツール | validate/explain/list_templates/list_handlers/get_template/get_traces/analyze_traces/propose_update/apply_update/rollback_update/run_golden_tests | `src/yagra/adapters/inbound/mcp_server.py:438-952` |
| Structured Trace JSON | NodeTrace/LLMCallTrace/ErrorTrace/RunSummary、schema_version 固定 | `src/yagra/domain/entities/trace.py` |
| Local-First | 外部送信コード皆無、Studio デフォルト 127.0.0.1、telemetry 0件 | `src/yagra/adapters/inbound/workflow_studio_server.py:99` |
| Safe Iteration | atomic write + 世代 backup + revision conflict 検出 | `src/yagra/application/use_cases/workflow_persistence.py` |
| Error Message 品質 | severity/context + difflib による fuzzy match | `src/yagra/domain/services/schema_validator.py:60-182` |
| カバレッジ運用 | pytest-cov + octocov 80% 閾値 | `.github/workflows/ci.yml:61-67`, `.octocov.yml` |
| 未完了痕跡 | TODO/FIXME/NotImplementedError = 0（vendor JS 除く） | src/ 全域 grep |
| Template Library | 9テンプレート（branch/chat/loop/parallel/rag/subgraph/tool-use/multi-agent/human-review） | `src/yagra/templates/` |

---

## 3. 乖離が見つかった実装（優先度順）

### Critical（ビジョン根幹 or 入口体験）

| ID | 乖離内容 | 根拠 | 推奨対応 |
|----|---------|------|---------|
| **D-C1** | 差別化軸「AI が AI を評価・改善（LLM-as-a-Judge / 自己改善ループ）」のコードが src/ に 0 件 | `src/yagra/` で `judge` / `self_improv` / `grading` すべて 0 マッチ。vision.md 第4節・第7節・第1節で最重要軸として宣言 | ビジョンの再定義（素材提供に徹する方針を明記）または実装着手。差別化軸は屋台骨のため、どちらにしても即対応が必要 |
| **D-C2** | `examples/llm-basic/workflow.yaml` が自身の validator を通らない（`version`/`start_at`/`end_at` 欠落、エッジが `from:/to:` で `source:/target:` 必須に違反） | `examples/llm-basic/workflow.yaml`（11行全体） | スキーマ準拠の最小例に修正。README 誘導の入口で躓く |
| **D-C3** | CI 統合ガイド `docs/ci-integration-guide.md` が参照する `.github/workflows/validate-example.yml` が実在しない | `ls .github/workflows/` は `ci.yml` / `docs.yml` / `publish.yml` のみ | サンプルワークフローを配置、または参照削除。G-12/M-35 Done の裏付け欠落 |

### Major（E2E / 安全性 / ビジョン徹底）

| ID | 乖離内容 | 根拠 | 推奨対応 |
|----|---------|------|---------|
| **D-M1** | `tests/integration/test_optimization_cycle_e2e.py` が実 LLM 不使用（pure Python handler + tmp_path + 関数直接呼出） | 同ファイル 56-63 / 85 / 103 行。`run_golden_tests` も連結せず | 実 LLM（moto 系 or vcrpy / litellm test providers）を使った E2E を追加、`run_golden_tests` を挟む一連シナリオ化 |
| **D-M2** | G-19 DoD「サイクル 30 分以内」に計測根拠なし（`time.perf_counter`/`pytest.mark.timeout`/"30 分" 文言いずれも grep 0 件） | テスト・ドキュメントとも計測がない | ベンチマーク枠を CI に追加、または DoD 文言を削除 |
| **D-M3** | `_tool_apply_update` が `run_golden_tests` の成功を前提としない。思想的完結性（提案→回帰検証→適用）がコードで強制されない | `src/yagra/adapters/inbound/mcp_server.py:824-905`、`agent-integration-guide.md:376` は努力義務として記述のみ | `apply_update` に `golden_pass_required=True` のデフォルトオプション追加、または WARN ログを必須化 |
| **D-M4** | Golden Test は LLM 出力の回帰を構造的に検出不能（モック一致+AUTO=STRUCTURAL で型のみ確認）だが、その**制約がドキュメントに明示されていない** | `src/yagra/application/use_cases/golden_test_runner.py:215-233, 403-405`、`domain/entities/comparison.py:126-128` | 制約を docs/sphinx に明記、LLM-as-a-Judge 併用の推奨パスを書く |
| **D-M5** | `workflow_persistence` はプロセス間ロックを持たず、多プロセス Studio でレース条件の可能性 | `src/yagra/application/use_cases/workflow_persistence.py`（threading.Lock のみ） | ファイルロック（fcntl.flock）追加 or 制約ドキュメント化 |
| **D-M6** | `state_graph_builder` の timeout が daemon スレッド実装で強制停止できず、背景走行が残存する可能性（ドキュメント未記載） | `src/yagra/application/use_cases/state_graph_builder.py:595-663` | 制約ドキュメント化、または multiprocessing 実装に変更 |

### Major（Hexagonal 境界違反）

| ID | 乖離内容 | 根拠 | 推奨対応 |
|----|---------|------|---------|
| **D-A1** | domain → application 逆依存 | `src/yagra/domain/services/prompt_version_validator.py:13` `from yagra.application.services.reference_resolver import PromptVersionInfo` | `PromptVersionInfo` を domain 側に移動、または Protocol で抽象化 |
| **D-A2** | domain entity に I/O 混入 | `src/yagra/domain/entities/trace.py:5-6, 257-272` `import importlib.metadata`, `platform`、`build_metadata()` で実行環境収集 | `build_metadata()` を `application/use_cases/trace_collector` に移譲 |
| **D-A3** | application → adapters 具象 new（DIP 違反） | `src/yagra/application/use_cases/golden_test_runner.py:306-308`（`InMemoryNodeRegistry()` 直接 new）、`adapters/inbound/mcp_server.py:976, 989`（`LocalGoldenCaseStore(...)` 直接 new）、`__init__.py:182-184`（`LocalTraceSink(...)` 直接 new） | Port 経由の依存注入に統一。composition root（CLI / MCP 起動点）で注入 |
| **D-A4** | application → top-level Yagra 循環依存 | `src/yagra/application/use_cases/golden_test_runner.py:301` `from yagra import Yagra` | 遅延 import を解消、`Yagra` クラス自体を別モジュール（`runtime.py`）に分離 |
| **D-A5** | `handlers/` レイヤが Hexagonal 4 層の枠外（第5層化） | `src/yagra/handlers/_llm_common.py:13, 147, 176` が application 遅延 import | `adapters/outbound/handlers/` に再配置 |

### Major（SRP 違反 / モジュール肥大）

| ID | 乖離内容 | 根拠 | 推奨対応 |
|----|---------|------|---------|
| **D-S1** | `workflow_studio_server.py` が **5090 行**（うち約 4780 行が `_studio_html()` 内の文字列リテラル HTML/JS） | 確認済（`wc -l`） | UI を `web_assets/studio.html` に外出し。Python 部分は 300 行以下を目標 |
| **D-S2** | `src/yagra/__init__.py` が **1309 行** — `Yagra` Runtime + `main()` CLI + 10 個の `_run_*_command` 同居 | 確認済 | `yagra/cli/` パッケージ化、`yagra/runtime.py` を分離、`__init__.py` は再 export のみ |
| **D-S3** | `application/services/studio_service.py` が **838 行**（17 メソッドの god class） | 確認済 | 責務軸（target/file/form/persistence）で 4 サブサービスに分割、`StudioPort` をファサードに |
| **D-S4** | `adapters/inbound/mcp_server.py` が **1066 行**（14 tool 同居） | 確認済 | `mcp_server/` パッケージ化、1 tool = 1 モジュール |
| **D-S5** | `application/use_cases/state_graph_builder.py` が **690 行**（state schema / graph / edge / router / resilience wrapper 5種混在） | 確認済 | resilience を `application/services/node_resilience.py`、edge 分類を `edge_classifier.py` に分離 |

### Major（ISP / OCP 違反）

| ID | 乖離内容 | 根拠 | 推奨対応 |
|----|---------|------|---------|
| **D-I1** | `StudioPort` に 14 メソッド集約（ISP 違反） | `src/yagra/ports/inbound/studio.py:43-107` | `StudioFileRepositoryPort` / `StudioFormPort` / `StudioPersistencePort` に分割 |
| **D-O1** | `ComparisonStrategy` enum に対する `if strategy == ...` チェーンが domain と application 両方に分散（OCP 違反） | `domain/entities/comparison.py:123-132`、`application/use_cases/golden_test_runner.py:215, 403` | Strategy パターン化（Protocol + 実装分離） |
| **D-O2** | `state_graph_builder.py:158` が `if node.handler == "subgraph":` で特別扱い（ハードコード） | 同行 | NodeSpec に `kind: Literal["regular","subgraph"]` 追加、または Strategy 登録に |

### Minor（使いにくさ）

| ID | 乖離内容 | 根拠 | 推奨対応 |
|----|---------|------|---------|
| **D-u1** | `workflow_explainer.py:270-271` の `except Exception: return []` がログ無しで prompt_ref 解決失敗を握りつぶす | 同行 | ログ追加、または warning 付きでエラー伝播 |
| **D-u2** | `workflow_form_model.py:481-482` の `except Exception: return None` がログ無し | 同行 | ログ追加 |
| **D-u3** | MCP ツールのエラーが文字列（`{"error": str(exc)}`）で構造化エラーコード無し | `mcp_server.py:706-1005` | error.code / error.hint を付与（schema_validator の context に倣う） |

---

## 4. 未実装のビジョン要素

| ビジョン要素 | 現状 | 対応 |
|-------------|------|------|
| LLM-as-a-Judge / 自己改善ループ | コード無し（差別化の中核） | **Critical D-C1** で起票 |
| プロンプト自動最適化（DSPy 等）との統合 | vision 第7節「将来展望」 | 現行ロードマップ外。今回の対応外 |
| VS Code Extension | vision 第7節「将来展望」 | 現行ロードマップ外 |
| エージェントによるエージェントの自律生成 | vision 第7節「将来展望」 | 現行ロードマップ外 |

---

## 5. 「やらないこと」境界遵守

| 境界 | 混入兆候 | 判定 |
|------|---------|------|
| Langfuse/Datadog 的ダッシュボード | `chart`/`dashboard`/`metrics ui` grep 0 件、Studio 内にも分析ビュー無し | 完全遵守 |
| 分析専用 UI | Studio は編集器、分析は CLI/MCP のみ | 完全遵守 |
| ホスティング / SaaS | `hosting`/`saas`/`cloud.` grep 0 件、PyPI 配布のみ | 完全遵守 |
| LangGraph からのピボット | ランタイムはすべて langgraph.graph 上 | 完全遵守 |

---

## 6. 最優先対応 Top 3（スタッフエンジニア視点）

1. **D-C1 LLM-as-a-Judge / 自己改善ループ** — ビジョン最重要軸の不在。**ビジョン再定義 or 実装着手**のどちらかを決める
2. **D-C2 + D-C3 入口体験の修復** — 壊れた `examples/llm-basic` と欠落した `validate-example.yml` を直す。小修正で体感品質が跳ね上がる
3. **D-S1 `workflow_studio_server.py` のインライン UI 4780 行外出し** — 5090 → 約 300 行。レビュー/テスト/i18n が可能に。**改修コスト小×効果大**

---

## 参照
- ビジョン正本: `docs/product/vision.md`
- Goal: `docs/product/goals.md`
- Milestone: `docs/product/milestones.md`
- Architecture ルール: `.claude/rules/architecture.md`
