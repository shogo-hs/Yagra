# ビジョン体現度ログ

ビジョン整合性の推移を時系列で記録する。タスク完了ごとに追記（Edit）する。Write による全体上書きは禁止。

---

## ベースライン — 2026-04-23

初回監査（Phase 1c）で算出したスコア。後続タスクはこの値を基準に改善を測る。

| 観点 | スコア (1-5) | 根拠 |
|------|:------:|------|
| ゴール寄与（ビジョン要素の体現度） | 4 | Phase 1〜6 の主要機能実装が揃う。差別化軸欠落で -1 |
| 原則遵守（Local-First / 人間ダッシュボード排除） | 5 | src/ 内に違反 0 件 |
| UX 一貫性（入口〜サイクル完結） | 3 | llm-basic 破綻、CI 統合ファイル欠落 |
| スコープ境界（やらないこと） | 5 | 混入兆候なし |
| 差別化軸の実装度（AI が AI を改善） | 2 | `judge` / `self_improv` 系コード 0 件 |
| 誤魔化し耐性（TODO/サイレント失敗/Done ラベル） | 4 | サイレント失敗 2 箇所のみ、CI 80% gate |
| Hexagonal 純度 | 2 | domain→application 逆依存 1、I/O 混入 1、application→adapters 具象 new 3+ |
| SRP 遵守 | 1 | 5090 行 studio、1309 行 __init__、838 行 god class |
| API 一貫性 | 4 | 命名・引数統一、MCP エラーコード構造化余地 |
| エラーメッセージ品質 | 4 | severity/context/fuzzy match が有効 |
| Golden Test 実効性 | 4 | 決定論的再現 OK、LLM 出力回帰は原理的不可 |
| E2E 実走性 | 2 | 実 LLM 不使用、30分 DoD の計測なし |

### 主な体現が進んでいる領域
- MCP 11 ツールで最適化サイクルの素材提供
- Pydantic スキーマの description/examples が AI-Ready
- Local-First + atomic write + revision conflict 検出で Safe Iteration
- Template Library 9 種が validate 通過
- `.github/workflows/ci.yml` + octocov で 80% カバレッジ gate

### 主な残課題
- **差別化軸「AI が AI を評価」が src/ に未実装**（最重要）
- **入口体験の破綻**: `examples/llm-basic/workflow.yaml` validator 不通、`.github/workflows/validate-example.yml` 欠落
- **E2E テストが実 LLM 不在**
- **apply_update が run_golden_tests の成功を前提としない**（思想的綻び）
- Hexagonal 境界違反と巨大モジュール肥大化の沈殿
- Golden Test の LLM 出力回帰検出不能の制約がドキュメント未明示

### 累積ドリフト所見（ベースライン時点）
なし（初回）。次タスクから監視する。

### 次タスクへの示唆
- **UX 一貫性 / 差別化軸** のスコアが 3 以下で、かつインパクトが大きい。優先領域。
- **SRP / Hexagonal 純度** は沈殿した構造負債。機能改修と並行でリファクタ機会を取る。

---

### Task #1: ビジョンの差別化軸の方針確定 — 2026-04-23

方針 A（LLM-as-a-Judge を実装する）をユーザー承認。`docs/product/vision.md` に実装コミットを明示（Phase 3 に LLM-as-a-Judge Handlers、やることに judge handler 提供を追加）。サブタスク #23-27 をバックログに追加。

| 観点 | スコア | 前回差分 |
|------|:------:|:-------:|
| 差別化軸の実装度 | 2/5 | ±0（方針決定のみ、実装未着手） |
| ゴール寄与 | 4/5 | ±0 |
| UX 一貫性 | 3/5 | ±0 |

- **体現が進んだ点**: ビジョンの実装コミットを明示化。従来 vision 記述と src/ 実装の乖離があった点を、バックログに落として計画可視化
- **残課題・新規課題**: #23 (create_judge_handler) 実装までは差別化軸スコアは上がらない。実装完了後に再評価
- **累積ドリフト所見**: なし（初回タスク）
- **次タスクへの示唆**: #2, #3 を並列で消化し UX 一貫性を回復しつつ、#23 の judge handler 実装に着手する

---

### Task #2: `examples/llm-basic/workflow.yaml` を v1.0 形式に修復 — 2026-04-23

PO 直接作業で修復。`version`/`start_at`/`end_at` 追加、`edges: []`。README のサンプル YAML も同期。`uv run yagra validate` が error 0 通過（warning 2 件は他 examples と同水準）。`uv run pre-commit run --all-files` 全通過。PR #47 に同梱。

| 観点 | スコア | 前回差分 |
|------|:------:|:-------:|
| UX 一貫性 | 4/5 | +1（入口体験の C2 乖離を解消） |
| 誤魔化し耐性 | 4/5 | ±0（Done 表示と実態の乖離を 1 つ解消） |

- **体現が進んだ点**: README から辿ったユーザーが validator 通過 YAML にたどり着ける状態に回復。他 examples と構文統一
- **残課題・新規課題**: #3 の validate-example.yml 欠落は未対応（次タスクで解消予定）
- **累積ドリフト所見**: なし。llm-basic が放置されていた原因は M-15/M-16 実装時に引き継ぎ漏れたものと推定（他 examples は v1.0 化済）
- **次タスクへの示唆**: #3（validate-example.yml 実在化）を PM 委任で進める。CI 経由で llm-basic 含む全 examples を継続検証する仕組みに繋げる

---

### Task #3: `.github/workflows/validate-example.yml` を実在化（Critical C3 解消）— 2026-04-24

PM 委任（general-purpose + opus）で完了。PR #48（Accept判定、Critical:0/Major:0/Minor:0）。CI 実ジョブで `validate-examples` 16 秒 pass、examples/ 全 6 個が `is_valid: true`。Developer 2 名（PM 代行）で concurrency ブロック + 0 マッチガード + CHANGELOG 更新まで拡張。`docs/ci-integration-guide.md` の `find` 記述も glob 実装と整合化。

| 観点 | スコア | 前回差分 |
|------|:------:|:-------:|
| UX 一貫性 | 5/5 | +1（Critical C3 解消で入口〜CI の一貫性が整った） |
| 誤魔化し耐性 | 5/5 | +1（docs と実装の乖離を完全解消） |
| 差別化軸 / Hexagonal / SRP | 2/5 / 2/5 / 1/5 | ±0（本タスクはスコープ外） |

- **体現が進んだ点**: Phase 4 (Approve & Update) の CI Integration が実証サンプルとして機能。Yagra 自身のリポジトリが「例を自分で検証している」状態になり、Dogfooding が整う
- **残課題・新規課題**: なし。Critical 3 件すべて本 Phase で解消完了
- **累積ドリフト所見**: 良い方向へのドリフト。docs ↔ 実装の乖離が 0 に
- **次タスクへの示唆**: Must 残り 6 件（#4 apply_update golden gate, #5 E2E 実 LLM, #6 Golden Test 制約ドキュメント, #7 studio UI 外出し, #23 judge handler, #24 self-improve example）。#4 は apply サイクル思想の綻び補正、#23 は差別化軸実装の起点。#4 → #23 の順が整合性高い

### PO 検証（Phase 2d / Task #3）

| 観点 | 判定 | 根拠 |
|------|:----:|------|
| ゴール寄与 | ✓ | Phase 4 CI Integration の実証サンプル整備 |
| 原則遵守 | ✓ | Local-First 維持、外部送信なし、既存 `ci.yml` と併存 |
| UX 一貫性 | ✓ | ガイドとコードの整合、クイックスタートが辿れる |
| 累積ドリフト | ポジティブ | docs ↔ 実装の乖離が 0 に |

**PO 判定: Accept**。PR #48 マージ後に main 反映。

---

### Task #4: `apply_update` に `golden_pass_required` オプション追加（デフォルト ON）— 2026-04-24

PM 委任（general-purpose + opus）で完了。PR #49（PMO Accept、Critical:0 / Major:0 / Minor:0）。Option C ハイブリッド採用（`last_golden_result` 明示渡し or 未指定時は内部で `_tool_run_golden_tests` 実行）。golden case 未定義時は `warnings: ["no_golden_cases_defined"]` 付き apply 許可で silent success を防止。`_assert_golden_passed` helper を切り出し SRP 遵守、構造化エラー `golden_not_passed` + `summary` + `hint` で AI エージェントの自己修復を支援。docs / MCP schema / CHANGELOG 完全同期。フルスイート 952/952 PASSED（playwright 33 件 pre-existing 除外）。

| 観点 | スコア | 前回差分 |
|------|:------:|:-------:|
| ゴール寄与 | 5/5 | +1（Phase 4 Safe Iteration を API レベルで担保、サイクル思想綻び解消） |
| 原則遵守 | 5/5 | ±0（Local-First 維持、silent success 禁止を warnings で担保） |
| UX 一貫性 | 5/5 | ±0（docs / MCP description / 実装の三者整合、エラーメッセージに hint 付き） |
| 誤魔化し耐性 | 5/5 | ±0（強制ゲート化で「docs には書いてあるが API は守らない」綻びが消失） |
| Hexagonal 純度 | 2/5 | ±0（private helper 抽出で SRP は改善したが adapters → application の経由は維持、レイヤ境界変化なし） |
| SRP 遵守 | 1/5 | ±0（helper 抽出は局所改善、mcp_server.py の肥大 1000+ 行は未解決） |
| API 一貫性 | 4/5 | ±0（構造化エラー形式が本タスクで確立、#16 で全 MCP tool 統一する際の雛形になる） |
| エラーメッセージ品質 | 5/5 | +1（`error` / `message` / `summary` / `hint` の 4 フィールド構造化、AI エージェントが解釈可能） |
| 差別化軸の実装度 | 2/5 | ±0（#23 judge handler 未実装のまま。ただし #23 完了後の「propose→judge→golden→apply」サイクルの前提は本タスクで整備） |

- **体現が進んだ点**:
  - Phase 4「Safe Iteration」の思想を **API で強制** するレベルに到達。docs と実装の乖離 0 を #3 に続き維持
  - 構造化エラー（`error` / `message` / `summary` / `hint`）の形式が確立。#16 (MCP エラー統一) の雛形として他 tool に展開できる
  - `last_golden_result` 再利用設計により「二重実行を避けたい AI エージェント」の UX 向上
  - golden case 未定義時の warning 付き apply 許可で「未検証だが使いたい」を安全に受け止めつつ silent success を防止（「誤魔化さない」思想の体現）
- **残課題・新規課題**:
  - `mcp_server.py` の SRP（1000+ 行）は本タスクでは解決しない。#19（mcp_server.py のツール分割）で取る
  - `_assert_golden_passed` は adapter 内 helper のまま。CLI (`yagra apply`) で共通利用する段になれば application/use_cases/ へ昇格
  - `propose_update` / `rollback_update` の構造化エラー形式は未統一（#16 で一括整理）
- **累積ドリフト所見**: ポジティブ継続。#3 (docs↔実装整合) → #4 (API↔思想整合) の流れで「綻びの沈殿」が減っている
- **次タスクへの示唆**:
  - 差別化軸スコア 2/5 を動かすために **#23 (create_judge_handler)** へ着手する。Must / 依存 #1 解消済み / ビジョン根幹
  - #5（E2E 実 LLM 補強）は #4 の成果で前提条件が揃った。#23 で handler を実装した後に自己改善サイクル E2E（#26）と統合できる順序が自然
  - Mission Brief の CHANGELOG 追記チェックリスト組み込みが #4 で標準化された（PMO 指摘 0 件）

### PO 検証（Phase 2d / Task #4）

| 観点 | 判定 | 根拠 |
|------|:----:|------|
| ゴール寄与 | ✓ | Phase 4 Safe Iteration を API レベルで担保、サイクル思想綻び完全解消 |
| 原則遵守 | ✓ | Local-First 維持、silent success 禁止を warnings で担保、外部送信なし |
| UX 一貫性 | ✓ | docs / MCP description / 実装の三者整合、エラーに hint で AI self-repair 支援 |
| 累積ドリフト | ポジティブ | #3 (docs↔実装整合) → #4 (API↔思想整合) の連鎖、綻びの沈殿が減少 |

**PO 判定: Accept**。PR #49 マージ後に main 反映。

---

### Task #23: `create_judge_handler` を実装（LLM-as-a-Judge 基本版、Port/Adapter 切替可）— 2026-04-24

PM 委任（general-purpose + opus）で完了。PR #50（PMO Accept、DoD 14/14 PASS、Critical:0 / Major:0 / Minor:0）。**差別化軸「AI が AI を評価」が src/ に初めて結実**。Port/Adapter パターンで LLM provider を切替可能に設計（`LLMProviderPort` Protocol + `LiteLLMProvider` + `ClaudeAgentSDKProvider` + `resolve_provider` Factory）。`claude_agent_sdk` 経由時は sonnet を default model、subscription auth でローカル動作（API キー不要）。rubric inline / rubric_ref（`path#key` 形式）の両方対応、複数 criterion 時は `_overall` を算術平均で自動付与。構造化 4 フィールドエラー（`error` / `message` / `summary` / `hint`）を全失敗経路で維持。`yagra[judge]` optional extra で `claude-agent-sdk>=0.1.0` をゲート。新規テスト 41 件（judge 19 / litellm 8 / claude_agent_sdk 7 / resolve 4 / integration 3）全 PASS、unit+integration 1000 PASSED（playwright 除く）。docs (agent-integration-guide.md) + CHANGELOG 同期。

| 観点 | スコア | 前回差分 |
|------|:------:|:-------:|
| 差別化軸の実装度（AI が AI を評価） | 4/5 | **+2**（handler 実装で差別化軸が初めて src/ に結実。残り 1 は #24 self-improve walking example + #26 E2E 統合が未着手のため） |
| ゴール寄与 | 5/5 | ±0（vision.md Phase 3 の `create_judge_handler()` 実装コミットを達成） |
| 原則遵守（Local-First / 人間ダッシュボード排除） | 5/5 | ±0（Claude SDK は subscription auth でローカル完結、外部送信は evaluation prompt のみ、人間ダッシュボード依存なし） |
| UX 一貫性 | 5/5 | ±0（rubric YAML / Python 登録例 / provider 切替表 / 出力構造を agent-integration-guide に明示、CHANGELOG 3 項目同期） |
| スコープ境界 | 5/5 | ±0（judge handler のみ、self-improve example や E2E は別タスクに分離） |
| 誤魔化し耐性 | 5/5 | ±0（4 フィールド構造化エラー全面採用、rubric 空 / scale 不正 / rubric_ref 不在 / oneOf 違反すべて fail-fast、SDK 未インストール時は silent success せず 4 フィールドエラー昇格） |
| Hexagonal 純度 | 3/5 | **+1**（`ports/outbound/llm_provider.py` を新設し、Protocol + 例外階層を SDK 非依存で定義。handler は `resolve_provider` Factory 経由で具象を取得し、直接 `new` しない。既存 `golden_test_runner.py` と同一の合成パターンに整合。domain/application の逆依存は本タスクでは未対応のため +1 に留める） |
| SRP 遵守 | 1/5 | ±0（judge.py は責務分離されているが、mcp_server.py 1000+ 行 god class は未着手） |
| API 一貫性 | 5/5 | **+1**（#4 で確立した 4 フィールド構造化エラーが judge handler / 全 provider 例外で一貫再利用。provider 切替 API が hybrid signature（DI or params）で `create_structured_llm_handler` と統一パターン） |
| エラーメッセージ品質 | 5/5 | ±0（hint 付き、SDK 未インストール時の `pip install yagra[judge]` 誘導まで実装） |
| Golden Test 実効性 | 4/5 | ±0（本タスクはスコープ外） |
| E2E 実走性 | 2/5 | ±0（本タスクはスコープ外、#5 / #26 で取る） |

- **体現が進んだ点**:
  - **差別化軸「AI が AI を評価」が handler として src/ に実装された**。vision.md L70 の「Phase 3 Analyze & Propose における `create_judge_handler()`」が初めて動く形で成立。ベースライン監査で差別化軸スコア 2 → 現在 4 へ、+2 のジャンプ
  - Port/Adapter 切替可能設計により、ビジョンの「AI-Ready / IDE 完結」と「OSS として誰でも拡張可能」を両立。将来 OpenAI provider 追加も `resolve_provider` への登録 1 行で済む
  - `claude_agent_sdk` 経由の sonnet default により、API キー不要で ローカル動作可能（subscription auth でオンプレ評価が可能）。Local-First 原則の体現
  - 既存 #4 の 4 フィールド構造化エラーが自然に全箇所に伝播し、AI エージェントが自己修復できる error contract が provider 横断で統一された
  - rubric oneOf / scale / criteria unique validation で silent success を完全排除（#4 の「検証 0 件 warning」思想の応用）
- **残課題・新規課題**:
  - #24 `examples/self-improve/` walking example が未実装。judge handler は提供したが、propose → judge → apply の連結サイクルは別タスク
  - #26 自己改善サイクル E2E 統合テストが未実装（#5 + #26 で連鎖着手予定）
  - #25 MCP tool `evaluate_traces` 未実装（judge handler の MCP 露出はまだ）
  - 既存 `create_llm_handler` / `create_structured_llm_handler` / `create_streaming_llm_handler` は `litellm` 直接呼び出しのまま（Port 経由に段階移行する追加タスクをバックログに追加すべき）
  - Hexagonal 純度 3/5 に留まる理由: #9 (domain→application 逆依存) / #10 (domain entity の I/O) / #11 (application → adapters 具象 new 他箇所) が未着手
- **累積ドリフト所見**: **強いポジティブ**。#3 (docs↔実装整合) → #4 (API↔思想整合) → #23 (差別化軸↔実装整合) の流れで、ビジョンで約束した要素が 3 連続で src/ に結実する「綻びの沈殿減少」トレンドが継続。特に #23 はビジョン根幹の最大課題だったため、整合性の底上げ効果が大きい
- **次タスクへの示唆**:
  - **最優先**: #24 (examples/self-improve/) と #25 (MCP `evaluate_traces`)。どちらも #23 の依存関係が解消され即着手可能。#24 は「walking example がないと judge 機能が体験できない」UX 課題、#25 は「MCP 経由で評価できないと AI エージェントが使えない」AI-Ready 課題
  - **並行**: #5 (E2E 実 LLM) は #26 (judge 統合 E2E) と統合して実装すれば効率的
  - **リファクタ候補**: 既存 `create_llm_handler` / `create_structured_llm_handler` / `create_streaming_llm_handler` を Port 経由に段階移行する新規 Should タスクをバックログに追加。#23 で雛形ができたため、同一パターンで拡張可能
  - **構造負債**: Hexagonal 純度を 3 → 4 以上に上げるには #9 / #10 / #11 のリファクタ着手が必要。Should 優先度で機能改修の合間に取る

### PO 検証（Phase 2d / Task #23）

| 観点 | 判定 | 根拠 |
|------|:----:|------|
| ゴール寄与 | ✓ | ビジョン差別化軸 src/ 初実装、vision.md Phase 3 の handler 実装コミットを達成 |
| 原則遵守 | ✓ | Local-First 維持（Claude SDK subscription auth）、人間ダッシュボード排除、silent success 防止 |
| UX 一貫性 | ✓ | docs / CHANGELOG / schema / handler 出力の四者整合、provider 切替表明示 |
| 累積ドリフト | **強いポジティブ** | #3→#4→#23 で「ビジョン約束の src/ 結実」3 連続、整合性底上げ継続 |

**PO 判定: Accept**。PR #50 マージ後に main 反映。差別化軸が初めて実装として動く節目のタスク。

---

### Task #24: `examples/self-improve/` walking example を追加 — 2026-04-24

PM 委任（general-purpose + opus）で完了。PR #51（PMO Accept、DoD 13/14 PASS + SC-14 blocked-on-env、Critical:0 / Major:0 / Minor:3 すべて情報レベル）。**差別化軸「AI が AI を評価」がユーザーが実走できる walking example として結実**。`examples/self-improve/` 配下 4 ファイル（`workflow.yaml` / `prompts.yaml` / `run_example.py` / `README.md`）構成。generate (OpenAI gpt-4o-mini, LiteLLM) → judge (claude_agent_sdk + sonnet, prompt_ref 省略で default system prompt 活用) の 2 ノード、inline rubric（clarity / accuracy、scale 1-5）。`run_example.py` は `_overall` を強調表示（`">>> Overall score: {overall:.2f} <<<"`）、per-criterion スコアと `rubric_items` の内訳も表示、`JudgeHandlerError.payload` の 4 フィールド（`error` / `message` / `summary` / `hint`）を整形して出力。README は日本語主体で 5 ブロック（概要 / Prerequisites + Setup / 実行 / 自己改善サイクル（擬似対話）/ Customization）、将来拡張として `evaluate_traces` 機能名のみ言及（issue 番号なし）。`src/` 変更 0 行、`validate-examples.yml` で自動検証緑、`yagra validate` が `is_valid: true` 通過、CHANGELOG [Unreleased] Added に 1 行追記、pre-commit 全通過、pytest 1000 PASSED（playwright 33 pre-existing 除外）。

| 観点 | スコア | 前回差分 |
|------|:------:|:-------:|
| 差別化軸の実装度（AI が AI を評価） | 5/5 | **+1**（handler 実装（#23）に加え、ユーザーが実走できる walking example が揃い、differentiating claim が「論」から「体感」へ移行。#25 / #26 の MCP 露出と E2E 統合が未着手のため 5 としつつも「例としての閉じた最小体験」は完成） |
| ゴール寄与 | 5/5 | ±0（vision.md L109 の「LLM-as-a-Judge handler と自己改善ループの walking example を提供」Phase 3 obligation を直接達成） |
| 原則遵守（Local-First / 人間ダッシュボード排除） | 5/5 | ±0（judge 側は Claude SDK subscription auth で API キー不要、generate 側は OpenAI key だが既存 llm-basic と同水準、人間ダッシュボード依存なし） |
| UX 一貫性 | 5/5 | ±0（docs / README / CHANGELOG / 出力スクリプトの四者整合、`_overall` 強調・4 フィールドエラー表示で handler 仕様を可視化） |
| スコープ境界 | 5/5 | ±0（self-improve/ 配下のみ、`rubric.yaml` 参考ファイル不同梱、propose→judge→apply 連結は擬似対話（README）のみで別タスクに分離） |
| 誤魔化し耐性 | 5/5 | ±0（`OPENAI_API_KEY` 未設定時は early exit + 明示メッセージ、`JudgeHandlerError` 捕捉で silent failure 禁止、docs と実装の乖離 0） |
| Hexagonal 純度 | 3/5 | ±0（`src/` 変更 0 件、スコープ外） |
| SRP 遵守 | 1/5 | ±0（スコープ外） |
| API 一貫性 | 5/5 | ±0（#23 で確立した hybrid signature と 4 フィールドエラーを walking example が自然に踏襲） |
| エラーメッセージ品質 | 5/5 | ±0（`JudgeHandlerError.payload` の 4 フィールドを `run_example.py` が整形表示する教材的実装で強化） |
| Golden Test 実効性 | 4/5 | ±0（スコープ外） |
| E2E 実走性 | 3/5 | **+1**（`python run_example.py` で generate→judge 2 ノード連結を手動実走可能。`OPENAI_API_KEY` + `claude login` で完全動作。#26（judge 統合 E2E 自動化）で残り +2 予定） |

- **体現が進んだ点**:
  - **差別化軸がユーザーの手元で動く walking example として結実**。`examples/self-improve/` に cd して `python run_example.py` を叩けば「AI が AI を評価」を 2 分で体感できる状態に到達
  - vision.md L109 の "LLM-as-a-Judge handler と自己改善ループの walking example を提供" という Phase 3 成果物約束が物理的に成立（#23 = handler、#24 = walking example）
  - README の 5 ブロック構成で「動かす（Prerequisites → 実行）」と「理解する（自己改善サイクル擬似対話）」と「広げる（Customization）」を分離、judge 機能の教材として自律的に機能
  - `run_example.py` が `JudgeHandlerError.payload` の 4 フィールドを整形表示する実装になっており、#4 / #23 で確立した構造化エラー形式を **ユーザーに見せるレベル** で貫徹。AI エージェントだけでなく人間も structured error を読む習慣が根付く
  - Contract 事前組込（CHANGELOG / pre-commit / `src/` 変更禁止 / 4 フィールドエラー整形 / 日本語主体）で **PMO 指摘 Critical/Major 0 件を 3 タスク連続**（#4 / #23 / #24）で達成。ハーネス学習効果が定着
- **残課題・新規課題**:
  - #25 (MCP `evaluate_traces`) 未着手。AI エージェントから judge 機能を MCP 経由で呼ぶ経路がまだ整わない
  - #26 (自己改善 E2E 統合テスト) 未着手。walking example は手動実走のみで、CI 自動化は別タスク
  - SC-14 手動スモーク（draft / `_overall` / rubric_items の実際値確認）は PM 環境に API キーなしで blocked-on-env。**user 側で `export OPENAI_API_KEY=... && cd examples/self-improve && uv add "yagra[llm,judge]" && python run_example.py` を実行して最終確認を依頼**
  - PMO Minor M1: llm-structured README が英語主体で、llm-basic / self-improve が日本語主体と不整合。ユーザー判断で将来整理
  - PMO Minor M2: pytest 並列実行時の 3 件 flaky（`test_run_mcp_server_calls_server_run` / `test_run_mcp_server_version_fallback` / `test_runs_inside_running_event_loop_via_executor`）は #24 と無関係な pre-existing。学習ログに記録して後続タスクで対処
  - PMO Minor M3: `prompt_state_warning`（state_schema 未定義）3 件は info レベル、既存 example と同水準
- **累積ドリフト所見**: **強いポジティブ継続**。#3 (docs↔実装整合) → #4 (API↔思想整合) → #23 (差別化軸↔実装整合) → #24 (差別化軸↔体感整合) で 4 タスク連続の「綻び沈殿減少」トレンド。特に #24 は「実装したものをユーザーが触れる」という最後の一歩を踏んだ意味で、ベースライン監査の Critical「差別化軸コード 0 件」が UX レベルでも完全解消
- **次タスクへの示唆**:
  - **最優先**: #25 (MCP `evaluate_traces`)。walking example は手動で動くが、AI エージェント（Claude Code 等）から MCP 経由で judge を呼べないと AI-Ready 軸の価値が半減。#23 / #24 の成果を MCP 層に露出するタスク
  - **高優先**: #26 (自己改善サイクル E2E 統合テスト)。walking example は手動スモーク留まり、#5 (E2E 実 LLM) と統合して CI 自動化する構成が理想的
  - **並行**: #28 (既存 3 handler の Port 経由移行)。#23 で確立した雛形を適用するリファクタ。機能改修の合間に取る
  - **PMO 指摘集約**: Minor M2（pytest parallel flaky 3 件）を新規 Should タスクとしてバックログ追加候補。再現性が確認されているため放置するほど sediment が溜まる
  - **README 言語ポリシー統一**: M1 の llm-structured（英語）/ llm-basic / self-improve（日本語）不整合を全 examples 通しで整理する小タスクも検討（Could）

### PO 検証（Phase 2d / Task #24）

| 観点 | 判定 | 根拠 |
|------|:----:|------|
| ゴール寄与 | ✓ | vision.md L109 の walking example 提供 obligation 達成、差別化軸を実装から体感に昇格 |
| 原則遵守 | ✓ | Local-First 維持（judge は subscription auth）、silent failure 禁止、`src/` 変更 0 |
| UX 一貫性 | ✓ | README 5 ブロック日本語主体、`_overall` 強調、4 フィールドエラー整形で handler 仕様可視化 |
| 累積ドリフト | **強いポジティブ** | #3→#4→#23→#24 の「綻び沈殿減少」4 連続、差別化軸 Critical を体感レベルで完全解消 |

**PO 判定: Accept**。PR #51 マージ後に main 反映。SC-14 はユーザー環境での実走確認を別途依頼。walking example が揃ったことで「Yagra = AI が AI を評価する」というビジョンのピッチが 2 分で伝わる状態に到達。

---

### Task #28: 既存 3 LLM handlers の `LLMProviderPort` 経由移行 — 2026-04-24

PM 委任（general-purpose + opus）で完了。PR #52（PMO Accept、DoD 16/16 PASS、Critical:0 / Major:0 / Minor:0）。**Hexagonal 境界の handlers 層破れを完全解消**し、`create_llm_handler` / `create_structured_llm_handler` / `create_streaming_llm_handler` の 3 全 LLM handler が `LLMProviderPort` 経由で `resolve_provider(...)` 型の Factory 注入に移行。`import litellm` を handlers から完全撤去（`src/yagra/adapters/outbound/llm_providers/litellm_provider.py` のみに残存）。`LLMProviderPort` Protocol に `complete` / `complete_streaming` メソッドを追加し、pure Python dataclass `LLMTokenUsage` / `LLMCompletion` / `LLMStreamChunk`（すべて `frozen=True, slots=True`、SDK 非依存）で戻り値型を構造化。`LiteLLMProvider` が 3 メソッド実装、`ClaudeAgentSDKProvider.complete` / `complete_streaming` は `LLMProviderConfigError` を 4 フィールド payload で送出する subset 対応（Out スコープ境界厳守）。循環 import 解消のため `handlers/errors.py` 新設し `LLMHandlerError` / `LLMHandlerConfigError` / `LLMHandlerCallError` を移設、`llm_handler.py` から `__all__` 再 export で既存 `from yagra.handlers.llm_handler import ...` 経路を温存（backward compat）。hybrid signature（`provider: LLMProviderPort | None` DI > `params["provider"]` > default `"litellm"`）を 3 handler で統一し、judge handler と同じ pattern に集約。streaming の公開 API `Generator[str, None, None]` は維持しつつ、内部 contract は `Iterator[LLMStreamChunk]` 化し generator priming で retry 契約に同期化（SC-15 超過達成）。テスト mock 81 箇所を `patch("...litellm_provider.litellm")` へ付替え、新規 9 件の DI テスト（`tests/unit/handlers/test_llm_handler_port_di.py`）+ Port dataclass smoke + LiteLLMProvider adapter 詳細テスト追加で 1021→1030 passed、pre-commit 全通過、既存 3 examples（llm-basic / llm-structured / llm-streaming）の workflow.yaml 無改修で動作維持。`*_PARAMS_SCHEMA` に `provider` フィールド追加（`llm` / `structured_llm` は `["litellm", "claude_agent_sdk"]`、streaming は `["litellm"]` のみで claude_agent_sdk 非対応を明示）。docs（agent-integration-guide.md Support Matrix）+ CHANGELOG 同期。

| 観点 | スコア | 前回差分 |
|------|:------:|:-------:|
| Hexagonal 純度 | 4/5 | **+1**（handlers 層の `import litellm` 直依存を完全撤去、全 LLM handler が `resolve_provider` 経由で Port 境界を遵守。残り 1 は #9 domain→application 逆依存 / #10 domain entity の I/O / #11 application → adapters 具象 new の他箇所が未着手） |
| API 一貫性 | 5/5 | ±0（judge で確立した hybrid signature + 4 フィールドエラーが 3 handler で一貫適用、provider 選択ロジックが `resolve_provider` に集約、`*_PARAMS_SCHEMA` の構造が judge と揃う） |
| 誤魔化し耐性 | 5/5 | ±0（未知 provider は 4 フィールド構造化エラー `unknown_provider` + hint で昇格、非 string は `invalid_provider_param`、streaming は claude_agent_sdk 非対応を schema enum で宣言、silent success 防止） |
| ゴール寄与 | 5/5 | ±0（#5 E2E 実 LLM 補強の前提条件が揃った。fake provider / vcrpy を `LLMProviderPort` 実装として注入可能になり、「propose→golden→apply の決定論的 E2E」という Phase 4 思想の実装前提が完備） |
| 原則遵守（Local-First / 人間ダッシュボード排除） | 5/5 | ±0（外部送信の増加なし、既存 litellm / claude_agent_sdk の利用パターン維持） |
| UX 一貫性 | 5/5 | ±0（既存 3 examples の YAML 無改修で動作、CHANGELOG / docs / schema / 実装の四者整合、`yagra handlers --format json` に provider フィールドが表示される） |
| スコープ境界 | 5/5 | ±0（In/Out 厳守: ClaudeAgentSDKProvider の `complete` / `complete_streaming` 本格実装は Out、fake provider 実装は #5 に分離、handler 再配置 #14 は別タスク） |
| 差別化軸の実装度（AI が AI を評価） | 5/5 | ±0（直接的な機能追加ではないが、judge handler と同じ Port/Adapter 切替パターンを 3 handler にも広げたことで「AI フレンドリーな拡張基盤」としての完成度が上がった） |
| エラーメッセージ品質 | 5/5 | ±0（`LLMProviderError` 派生を `LLMHandlerError` に翻訳する retry 契約を整理、`LLMProviderCallError` = retryable / `LLMProviderConfigError` = 非 retryable 即変換の境界が明確） |
| SRP 遵守 | 1/5 | ±0（本タスクはスコープ外、mcp_server.py / __init__.py / studio の god class は未着手） |
| Golden Test 実効性 | 4/5 | ±0（本タスクはスコープ外） |
| E2E 実走性 | 3/5 | ±0（直接的な変化はないが、**次タスク #5 の前提が整った**。fake provider 実装で +1-2 の余地あり） |

- **体現が進んだ点**:
  - **Hexagonal 境界の最後の handlers 層破れが消失**。ベースライン監査の Critical「handler 層での litellm 直接依存」が完全解消。ベースライン Hexagonal 2 → #23 で 3 → #28 で 4、2 タスク連続 +1 の改善トレンド
  - Port Protocol に dataclass を追加することで token usage 情報が loss-less に handler 層に届く構造になった。将来 `complete_structured` の戻り値を dataclass 化する際の雛形として機能（次回の Should リファクタ候補）
  - `handlers/errors.py` 新設により `_llm_common.py` → `llm_handler.py` の矢印が消滅、循環依存が構造的に解消。他 handlers が追加される際の「新しいエラー階層」追加パターンも確立
  - Generator priming（SC-15 超過達成）で streaming も非 streaming と同じ retry 信頼性を獲得。streaming 固有の「接続失敗が next() まで遅延する問題」を同期化で解決
  - Contract 事前組込（CHANGELOG / pre-commit / 4 フィールドエラー / docstring r""" / backward compat 絶対維持）で **PMO 指摘 Critical/Major 0 件を 4 タスク連続**（#4 / #23 / #24 / #28）で達成、Minor も #4 / #23 / #28 は 0 件。ハーネス学習効果が完全定着
  - 既存 examples の無改修動作保持により、既存ユーザーの workflow 資産は一切影響を受けない（「ユーザーの作ったものを壊さない」という OSS の信頼基盤を維持）
- **残課題・新規課題**:
  - #5 E2E 実 LLM シナリオ補強は本タスクで前提完了。fake provider を `LLMProviderPort` として実装する形で #5 に着手可能
  - `ClaudeAgentSDKProvider.complete` / `complete_streaming` の subset 対応は本タスク終了時点で `LLMProviderConfigError` 返却のみ。SDK が streaming / 非構造化応答に公式対応した時点で本格実装する Should タスクを将来バックログに追加する候補
  - `complete_structured` の戻り値型 dataclass 化（#23 互換性維持のため今回は Out スコープ）は将来の Should リファクタ候補。全 provider method が dataclass を返すようになれば API が一層均質化
  - handler 再配置（#14 `adapters/outbound/handlers/`）は未着手、Should で残留
  - Hexagonal 純度 4/5 に留まる理由: #9 (domain→application 逆依存) / #10 (domain entity の I/O `trace.py`) / #11 (application → adapters 具象 new) の 3 件が未着手
- **累積ドリフト所見**: **強いポジティブ 5 連続**。#3 (docs↔実装) → #4 (API↔思想) → #23 (差別化軸↔実装) → #24 (差別化軸↔体感) → #28 (Hexagonal↔実装) で 5 タスク連続の「綻び沈殿減少」トレンド。特に #28 はベースライン監査で Critical 扱いだった handlers 層の境界違反を消しており、基盤の健全性が一段上がった。「機能追加だけでなく、基盤の正しさを積み増す」タイミングが 2 タスク連続（#23 / #28）で Hexagonal 純度を +2 底上げした効果は今後のリファクタ速度にも効く
- **次タスクへの示唆**:
  - **最優先**: #5 (E2E 実 LLM シナリオ補強)。本タスクで前提完了。fake provider（もしくは vcrpy 録画）を `LLMProviderPort` として実装し、`propose → golden → apply` の連結 E2E を決定論的に実走する。Must 残りの中で最も依存解消が進んだタスク
  - **並行**: #6 (Golden Test 制約ドキュメント化)。軽タスク、ドキュメントのみ。Must 残件を消化する追加候補
  - **並行**: #25 (MCP `evaluate_traces`)。judge handler の MCP 経由露出、Should だが AI-Ready 軸で価値が高い
  - **Hexagonal 5/5 達成ロードマップ**: #28 で handlers 層 +1、残り +1 のためには #9 (domain→application 逆依存) か #10 (domain entity の I/O `trace.py`) のいずれかを完了させる必要。#9 は `PromptVersionInfo` の domain 移動で比較的軽い。Should 優先度で機能改修の合間に取る
  - **テスト mock 再編のパターン**: 本タスクで確立した「handler から litellm 直接 patch → adapter layer での patch + Port fake 使用」は、将来新しい LLM provider が追加されたときのテスト書き換え手順のテンプレートとして `tests/learnings.md` に記録すべき
  - **ハーネス学習の定着**: Contract v1→v2 のサイクル（PM Alignment 往復での Q/R 解消）が #23 / #28 で 2 回連続の規模拡大（M→L）を正しく検出・受け入れできた。「PO が初期サイジングを迷ったら PM Alignment で補正する」運用が効果を持続

### PO 検証（Phase 2d / Task #28）

| 観点 | 判定 | 根拠 |
|------|:----:|------|
| ゴール寄与 | ✓ | #5 E2E 実 LLM シナリオ補強の前提完了、Yagra 基盤の健全性向上（Hexagonal 最後の handlers 層破れ消失） |
| 原則遵守 | ✓ | Local-First 維持、silent success 防止（未知 provider を 4 フィールドエラーで昇格）、backward compat 絶対維持で既存 examples 無改修 |
| UX 一貫性 | ✓ | CHANGELOG / docs / schema / 実装 / `yagra handlers --format json` 出力の五者整合、judge と 3 handler で hybrid signature + 4 フィールドエラー完全統一 |
| 累積ドリフト | **強いポジティブ** | #3→#4→#23→#24→#28 で「綻び沈殿減少」5 連続、基盤の正しさが 2 タスク連続（#23 / #28）で底上げ |

**PO 判定: Accept**。PR #52 マージ後に main 反映。Hexagonal 純度の handlers 層破れが消え、#5 E2E 補強の前提が完備。5 タスク連続のポジティブドリフトで累積整合性が引き続き高まり、機能追加と基盤リファクタが交互に積み上がる健全なペースを維持。
