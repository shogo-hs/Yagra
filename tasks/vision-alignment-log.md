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
