# Product Backlog

**最終更新**: 2026-04-24（#28 完了、#5 候補）
**ビジョン**: Yagra = AI が AI を評価・改善するための AI-Friendly な OSS エージェント開発・最適化ライブラリ（IDE 完結 / LangGraph 拡張 / MCP 特化）
**正本**: `docs/product/vision.md`

## ビジョン整合性監査サマリ（2026-04-23）
- 監査詳細: `tasks/vision-audit.md`
- ベースライン: `tasks/vision-alignment-log.md`
- 体現度スコア（主要観点）: ゴール寄与 4 / 差別化軸 2 / UX 3 / 境界 5 / Hexagonal 2 / SRP 1
- 乖離: Critical 3 件 / Major 13 件 / Minor 3 件

---

## タスク一覧（優先順位順）

| # | タスク | 種別 | 優先度 | 依存 | 成功基準（DoD） | 状態 |
|---|--------|------|:-----:|------|---------------|:----:|
| 1 | ビジョンの「AI が AI を評価・改善」軸を再確認し、実装方針またはスコープ変更を確定する | 設計判断 | Must | - | ユーザー承認済み方針ドキュメント（実装着手する / ビジョンを「素材提供に徹する」に再定義する の二択）が `docs/product/` に反映。該当する場合はサブタスク（LLM-as-a-Judge handler、自己改善ループ walking example 等）をバックログに追加 | **done** |
| 2 | `examples/llm-basic/workflow.yaml` を validator 通過する形に修復 | 修正 | Must | - | `yagra validate --workflow examples/llm-basic/workflow.yaml` が error 0 で通過。`version`/`start_at`/`end_at` 補完、エッジは `source:/target:` に統一。README 誘導どおり動作する | **done** |
| 3 | `.github/workflows/validate-example.yml` を実在化（または CI 統合ガイドから参照削除） | 修正 | Must | - | ファイル実在、PR でのトリガ成功、または `docs/ci-integration-guide.md` 側の参照修正。いずれもユーザーが辿って動くサンプルになる | **done (PR #48)** |
| 4 | `_tool_apply_update` に「run_golden_tests 成功前提」オプションを追加しデフォルト ON | 修正 | Must | - | `apply_update(..., golden_pass_required=True)` が失敗時 apply を中止。MCP ツールスキーマと `agent-integration-guide.md` に反映。既存 E2E テスト更新 | **done (PR #49)** |
| 5 | 最適化サイクル E2E を実 LLM シナリオで補強（propose → golden → apply 連結） | 新規 | Must | #4 | litellm test provider または vcrpy で LLM 呼び出しを再現可能にした統合テストを追加。サイクル全連結を assert | pending |
| 6 | Golden Test の「LLM 出力回帰を構造的に検出不能」制約をドキュメント化 | 修正 | Must | - | `docs/sphinx/source/user_guide/regression_test.md`（または golden.md）に制約と LLM-as-a-Judge 併用の推奨パスを追記 | pending |
| 7 | `workflow_studio_server.py` のインライン HTML/JS を `web_assets/studio.html` に外出し | リファクタ | Must | - | `workflow_studio_server.py` が 500 行以下、HTML/JS/CSS は `web_assets/` 配下。既存 Studio テスト全通過、外見・機能変化なし | pending |
| 8 | G-19 DoD「30 分以内」に計測根拠を付与 or DoD を修正 | 修正 | Should | - | ベンチマーク CI ジョブ導入で実測、または goals.md / milestones.md の該当文言を「ユーザー実測値なし」に修正 | pending |
| 9 | domain → application 逆依存を解消（`PromptVersionInfo` を domain へ） | リファクタ | Should | - | `src/yagra/domain/services/prompt_version_validator.py` が application を import しない。`PromptVersionInfo` が domain に定義。全テスト通過 | pending |
| 10 | domain entity の I/O 撤去（`trace.py` の `build_metadata()` を application 移譲） | リファクタ | Should | - | `src/yagra/domain/entities/trace.py` が `importlib.metadata` / `platform` を import しない。同等機能が `trace_collector` にある | pending |
| 11 | application → adapters 具象 new の撤廃（Port 注入へ） | リファクタ | Should | - | `golden_test_runner.py` / `mcp_server.py` / `__init__.py` の `InMemoryNodeRegistry()` / `LocalGoldenCaseStore(...)` / `LocalTraceSink(...)` 直接 new が Port 経由の注入に置換される | pending |
| 12 | `application → from yagra import Yagra` 循環依存の解消 | リファクタ | Should | #11 | `src/yagra/runtime.py` を新設し `Yagra` クラスを移動。`application/use_cases/golden_test_runner.py:301` の循環 import 撤廃 | pending |
| 13 | `src/yagra/__init__.py` の CLI 分離 | リファクタ | Should | #12 | `yagra/cli/` パッケージ化し、`__init__.py` は再 export のみ（200 行以下） | pending |
| 14 | `handlers/` を `adapters/outbound/handlers/` へ再配置 | リファクタ | Should | - | レイヤ位置の明確化。import パスの更新。既存テスト全通過 | pending |
| 15 | `workflow_explainer` / `workflow_form_model` のサイレント失敗にログ追加 | 修正 | Should | - | `except Exception: return None/[]` 箇所（4行）で `_logger.warning(...)` が発火する。該当テスト追加 | pending |
| 16 | MCP ツールのエラーレスポンスに構造化コード追加 | 修正 | Should | - | 全 `_tool_*` のエラーが `{"error": {"code": ..., "message": ..., "hint": ...}}` に統一。`agent-integration-guide.md` 更新 | pending |
| 17 | `StudioPort` を責務単位に分割（ISP） | リファクタ | Could | #7 | `StudioFileRepositoryPort` / `StudioFormPort` / `StudioPersistencePort` への分割。`StudioService` がファサード化 | pending |
| 18 | `studio_service.py` god class の分割 | リファクタ | Could | #17 | 4 サブサービスへ分割。各 300 行以下 | pending |
| 19 | `mcp_server.py` のツール分割 | リファクタ | Could | - | `mcp_server/` パッケージ化、1 tool = 1 モジュール。`create_mcp_server` は集約のみ | pending |
| 20 | `state_graph_builder.py` の責務分離（resilience / edge） | リファクタ | Could | - | `application/services/node_resilience.py` / `edge_classifier.py` を新設、本体 400 行以下 | pending |
| 21 | timeout 実装の daemon スレッド制約をドキュメント化（または multiprocessing 化） | 修正 | Could | - | 制約が `docs/sphinx` に明記、または `cancel_futures` ベース実装に置換 | pending |
| 22 | `workflow_persistence` にプロセス間ロック（fcntl.flock）追加 or 制約明示 | 修正 | Could | - | 多プロセス競合テスト追加 or ドキュメント注記 | pending |
| 23 | `create_judge_handler` を実装（LLM-as-a-Judge 基本版、Port/Adapter 切替可） | 新規 | Must | #1 | `src/yagra/handlers/judge.py` に handler 実装。evaluation rubric YAML 読込、LLM 呼び出し、スコア + 根拠の構造化返却。ユニットテストで ≥3 ケース網羅。`yagra handlers` 出力に表示 | **done (PR #50)** |
| 24 | `examples/self-improve/` walking example を追加 | 新規 | Must | #23 | `examples/self-improve/workflow.yaml` + README。propose → judge → apply の自己改善ループを E2E で実走可能。validator 通過 | **done (PR #51)** |
| 25 | MCP tool `evaluate_traces` を追加 | 新規 | Should | #23 | `mcp_server.py` に `_tool_evaluate_traces` 追加。LLM 評価を既存 trace に対して実行し、スコア/根拠/改善提案を返却。`agent-integration-guide.md` 更新 | pending |
| 26 | 自己改善サイクル E2E 統合テスト | 新規 | Should | #23, #5 | propose → judge → run_golden_tests → apply_update のサイクル連結を E2E で assert。litellm test provider または vcrpy で再現可能 | pending |
| 27 | LLM-as-a-Judge ドキュメント | 新規 | Could | #23 | `docs/sphinx/source/user_guide/llm_as_a_judge.md` 追加。評価 rubric、metrics、best practices、Langfuse 等との差別化点を記述 | pending |
| 28 | 既存 `create_llm_handler` / `create_structured_llm_handler` / `create_streaming_llm_handler` を `LLMProviderPort` 経由に段階移行 | リファクタ | Should | #23 | 3 ハンドラが `resolve_provider(...)` 経由で provider を取得。既存 litellm 直接呼び出しを置換。backward compat は `params["provider"]` default = `"litellm"` で維持。全既存テスト通過 + structured_llm の dynamic schema_yaml も維持 | **done (PR #52)** |

---

## 優先順位の根拠
- **Must**: ビジョン根幹 or 入口体験 or サイクル思想的完結に直結。放置すると「Done」表示と実態の乖離が深まる
- **Should**: Hexagonal/SOLID 基盤の歪みと使いにくさの穴埋め。機能は動くが中長期の速度低下要因
- **Could**: 構造負債のさらなるリファクタ。Must/Should 後に取る

## 依存関係補足
- #4 → #5: 「golden_pass_required ON で E2E 通る」ことを #5 で検証
- #11 → #12 → #13: Port 注入整理 → 循環依存解消 → CLI 分離の順で進めると衝突が少ない
- #7 → #17 → #18: Studio UI 外出し → Port 分割 → service 分割の順で段階実装可能
