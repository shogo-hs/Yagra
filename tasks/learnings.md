# タスク間学習ログ

**最終更新**: 2026-04-24（Task #24 完了時）
**蓄積開始**: 2026-04-24（Task #3 完了時）

> agent-company-v2 Phase 2f の知見蓄積ルールに従う。PMの結果レポートから「技術的発見 / プロジェクト固有パターン / PMO指摘パターン / 環境的発見」を体系的に記録する。2回以上繰り返されるパターンは Developer Spec のデフォルトに昇格する。

---

## 技術的発見

| Task | 知見 | 影響範囲 |
|------|------|---------|
| #3 | `yagra validate --workflow <path>` に `--bundle-root "$(dirname "$f")"` を付けないと `examples/*/workflow.yaml` の `prompt_ref` 解決に失敗する | examples/ 配下を検証する CI / スクリプト / MCP `validate_workflow` 利用箇所すべて |
| #3 | GitHub Actions で examples 検証する場合は `for f in examples/*/workflow.yaml; do ... done` + `shopt -s nullglob` + 0-match ガード（`if [ -z "$files" ]; then exit 1; fi`）が必要。silent success を防ぐため | CI workflow を書くとき / Yagra 以外のワークフロー CI にも応用可能 |
| #3 | `uv sync --locked --dev` は PyPI 公開版ではなく開発中のコードで検証する。`uv pip install --system yagra` は false negative/positive のリスクあり | CI における Yagra 自身のドッグフーディング |
| #4 | `_tool_run_golden_tests` の戻り値はフラット `{total, passed, failed, results, ...}`（`summary` ラップなし）。`last_golden_result` 再利用 API を作る場合は runtime contract を一次読解で確認すること | MCP tool 間でのデータ再利用 API 設計全般 |
| #4 | Option C ハイブリッド設計: 「事前実行結果 dict を明示渡し」と「未指定時の内部実行」を両立する API パラメータ設計。backward-compat と「ゼロ設定で安全側」を同時に満たせる | MCP tool / CLI の「検証→適用」系 API（今後の `yagra apply` CLI 等） |
| #4 | 構造化エラー 4 フィールド `{error, message, summary, hint}`: `error` = マシン可読コード、`message` = 人間向け要約、`summary` = 数値コンテキスト、`hint` = 次のアクション提案。AI エージェントの自己修復サイクルを回すための最小フィールド集合 | 全 MCP tool（#16 で全体統一する際の雛形）/ 他プロジェクトの AI-Ready API |
| #4 | 「検証対象 0 件」時は `warnings: ["no_<entity>_defined"]` 付きで success を返すパターン。silent success を防ぎながら過度に blocking しない中庸解 | 全 MCP tool / CI workflow / 検証系 API 全般 |
| #23 | Hybrid signature パターン: `provider: LLMProviderPort \| None = None` で DI を受け付けつつ、`params["provider"]` 文字列でも resolve 可能にする。DI > params の優先順位を固定。`create_structured_llm_handler` と同一の設計 | 複数の解決経路を持つ handler ファクトリ全般 |
| #23 | Lazy SDK import + 構造化 ImportError 昇格: `resolve_provider("claude_agent_sdk")` は SDK 未インストールでも成功、実際の `complete_structured` 呼出時に 4 フィールド構造化エラー (`claude_agent_sdk_not_installed` + `pip install yagra[judge]` hint) を返す。silent failure 防止 + 遅延検査で factory が optional deps のゲートで失敗しない | optional extras を持つ全 provider adapter |
| #23 | Async→sync bridge via ThreadPoolExecutor: SDK の `query()` が async 専用の場合、event loop running 時は dedicated worker thread で `asyncio.run(...)` を実行。Jupyter / pytest-asyncio 配下からの呼出も透過対応 | async-only SDK を sync handler から呼ぶケース全般 |
| #23 | `patch.dict(sys.modules, {...})` で pydantic サブモジュール（`root_model` など）を差し替えると、test 後に import キャッシュが汚染され後続テストが失敗する。`sys.modules.setdefault(name, mock)` に置換し、既存 pydantic モジュールを尊重しつつ欠落分のみ補う | mock を `sys.modules` に差し込む全テスト |
| #24 | walking example で inline rubric + `prompt_ref` 省略（default system prompt 活用）はペダゴジカルに有効: 「最小構成で動かす」「prompt_ref の有無による両方の正当性を示す」「rubric の詳細宣言だけで judge が機能することを体感させる」の 3 点をまとめて教える。結果的に README 5 ブロック全体が 1 つのストーリーになる | 教育系 walking example（handler 系機能紹介）全般 |
| #24 | `JudgeHandlerError.payload` の 4 フィールド（`error` / `message` / `summary` / `hint`）をユーザー向けスクリプト（`run_example.py`）で整形表示する実装パターン。AI エージェントの自己修復だけでなく、人間ユーザーにも structured error を見せて「Yagra は構造化エラーを返す」ことを教材化できる | structured error を返す全 handler の walking example / CLI ツール |
| #24 | `validate-example.yml` CI は `yagra validate --workflow <path>` でスキーマ検証のみ行う（実 LLM 呼出なし）ため、optional extras（`yagra[judge]` 等）に依存する handler を使う example も **CI 自動検証対象に含められる**。実走は手動スモークに分離する構成が現実的 | optional extras を使う全 example の CI 統合 |
| #24 | generate 側（LiteLLM 体系、`model.provider = "openai"` 等）と judge 側（judge 専用 provider 体系、`params.provider = "claude_agent_sdk"` 等）はスキーマが別物。README で「judge の provider を LiteLLM provider に差し替え可能」と誤読させないよう明示的に注意書きが必要（Contract 事前組込で #24 は無指摘達成） | LLM provider を扱う全 example / docs |
| #24 | pytest 並列実行（`-n auto` 等）時に 3 件 flaky が再現: `test_run_mcp_server_calls_server_run` / `test_run_mcp_server_version_fallback` / `test_runs_inside_running_event_loop_via_executor`。個別実行では全 PASS。モジュール import のグローバル状態や asyncio event loop 干渉が疑われる。#24 と無関係な pre-existing | 並列実行対応テストの整備タスク検討時 / CI 不安定化調査 |

## プロジェクト固有パターン

| Task | パターン | 適用場面 |
|------|---------|---------|
| #3 | 新 GitHub Actions workflow を追加する際は既存 `ci.yml` のバージョンラインを継承する（`actions/checkout@v6` / `actions/setup-python@v6` / `astral-sh/setup-uv@v7`） | 新 workflow ファイル作成時 |
| #3 | `main` ブランチには branch protection あり（REVIEW_REQUIRED）。直接 push / マージ不可。全変更は feature branch → PR → user 承認マージの経路を通る | 全タスク、特に PO 側の tracking 文書更新時の commit 運用 |
| #3 | 新 workflow には必ず `concurrency: group: <wf-name>-${{ github.ref }}` + `cancel-in-progress: true` を入れる（PMO 指摘で標準化） | 全 CI workflow |
| #3, #4 | 機能追加・修正は CHANGELOG.md の `[Unreleased]` セクションに Added / Changed / Fixed 等のカテゴリで追記する。**Mission Brief のチェックリスト標準項目として昇格済み**（#3 で PMO 指摘 → #4 で Contract 事前組込で指摘 0 件を実現） | すべての user-visible 変更 |
| #4 | `adapters/inbound/mcp_server.py` 内で tool 間の呼び出しをする際は private helper（`_assert_golden_passed` 等）に抽出して SRP を維持する。将来 CLI からも同一仕様を使う場合は application/use_cases/ への昇格を検討 | MCP tool 間で共通ロジックが発生した場合 |
| #4 | MCP tool の Pydantic `inputSchema` description と docs（agent-integration-guide.md）は同一内容で同期させる。AI エージェントが両方を参照する可能性があるため、挙動テーブル形式で docs にも書く | 新 MCP tool 追加 / 既存 tool API 変更時 |
| #23 | 新 Port は `ports/outbound/<noun>.py` に 1 ファイル 1 Port + 専用例外階層の構成で配置する（`llm_provider.py` が `LLMProviderPort` + `LLMProviderError` / `LLMProviderConfigError` / `LLMProviderCallError` の 3 段）。config error（即時 raise）と call error（retry 可）を境界で振り分けできる | 新規 Port 追加時の標準構成 |
| #23 | Port 実装 adapter は `adapters/outbound/<noun>s/` にパッケージ化し、`__init__.py` に `resolve_provider(name: str) -> Port` Factory を同居させる。unknown name は `ValueError` + hint、毎回新規インスタンス返却（mutable state 回避） | 新規 Port を複数 adapter で実装する場合 |
| #23 | Claude Agent SDK の Python SDK は subscription auth（`claude login` 済み）で動作。API key 不要でローカル実行可能。default model は `"sonnet"` を採用（Yagra のビジョン「ローカル動作」と整合） | Claude SDK 経由の handler 追加時 |
| #23 | `pyproject.toml` の optional extra は `yagra[judge]` のように機能単位で切り分ける。`claude-agent-sdk>=0.1.0` のような重量依存は base から分離し、core install を軽量に保つ | 新規 optional 依存追加時 |
| #24 | walking example は 4 ファイル構成（`workflow.yaml` / `prompts.yaml` / `run_example.py` / `README.md`）を基本とする。参考 `rubric.yaml` 等の extra は同梱しない（理解の集中を保つ）。`llm-basic` / `llm-structured` / `llm-streaming` / `self-improve` で統一 | 新規 handler 系 walking example 追加時 |
| #24 | README ブロック構成の標準: (1) 概要 — 何を体感するサンプルか 1-2 文 / (2) Prerequisites + Setup — 依存 / API キー / auth 手順 / (3) 実行 — コマンド 1 行 + 期待出力の要素 / (4) 自己改善サイクル等のロジック説明（擬似対話形式も可） / (5) Customization — rubric / model / prompt 等の差し替え方 | 新規 walking example / advanced example 全般 |
| #24 | walking example で将来機能（`evaluate_traces` 等）に言及する場合は **機能名のみ**、issue 番号（#25 等）や絶対日付を書かない。バックログの状態変化で README が陳腐化するのを防ぐ | 全 README / docs 内の未実装機能言及 |
| #24 | 既存 examples の README 言語ポリシーが不統一（`llm-basic` / `self-improve` 日本語主体、`llm-structured` 英語主体）。統一するなら別タスクで全体整理。混在を許容するなら Contract / Mission Brief で「今回は日本語主体」のように都度明示する | 新規 example README 言語選択 / 既存不整合整理タスク |

## PMO指摘パターン分析

| 指摘カテゴリ | 頻度 | 対策 | ステータス |
|-------------|:----:|------|----------|
| concurrency 制御の追加（#3 で 1 回） | 1 | 2 回目以降出たら Developer Spec の CI workflow テンプレートに必須項目として昇格 | 監視中 |
| 0-match 時の silent success 防止（#3 で 1 回） | 1 | 2 回目以降出たら同様に昇格 | 監視中（#4 で類似パターン「no-case warning」を先取り実装。明示 warning 付き許可で無指摘） |
| CHANGELOG 追記（#3 で 1 回 → #4 で事前組込み無指摘 → #23 でも事前組込み無指摘 → #24 でも事前組込み無指摘） | 1 | **#4 で Contract に事前組込 → Mission Brief チェックリスト標準項目に昇格済み** | **昇格完了・効果持続**（#4 / #23 / #24 で 3 連続 PMO 指摘 0 件） |
| pytest 並列実行時の flaky 3 件（#24 で pre-existing として観測） | 1 | 未対策 — 新規 Should タスクとしてバックログ追加候補（MCP server / asyncio 系 3 件の並列安全化） | 監視中（#24 で環境的発見としても記録） |

> #4 / #23 / #24 の PMO レビュー結果: いずれも Critical 0 / Major 0。**Minor も #4 / #23 は 0 件、#24 は 3 件すべて情報レベル**（言語ポリシー統一 / 並列 flaky / warning 水準は既存同水準）。Contract 段階で前回 PMO 指摘パターンを事前に反映する運用が **4 タスク連続で効果を維持**。
> 「2 回以上繰り返したら昇格」の原則は、「1 回出たら次タスクの Contract で先回り反映」で実質的に先取りできる（ハーネス改善）。
> #23 で確認された追加の標準事項: 「optional deps の構造化 ImportError 昇格」「Port + 専用例外階層」「rubric/schema の oneOf 排他検証」「4 フィールドエラーの全失敗経路採用」を #24 以降の LLM 機能拡張タスクの Contract に事前組込する。
> #24 で確認された追加の標準事項: 「walking example 4 ファイル構成 + README 5 ブロック + 将来機能は機能名のみ」「structured error の user-facing 整形表示」「validate-example CI は optional extras handler でもスキーマ検証として成立」を #25-#27 の差別化軸拡張タスクの Contract に事前組込する。

## 環境的発見

| 項目 | 内容 | 対処 |
|------|------|------|
| PM Agent 内の Task(Agent) ツール不在（#3 / #4 で 2 回連続再現） | Claude Code Agent（general-purpose opus）から起動した PM 相当 Agent は、さらなる subagent（Task/Agent）を起動できない環境制約あり | PM が Developer/PMO 工程を sequentially 代行（ロール境界を出力で明確化、検証証拠を分離記録）。agent-company-v2 skill の `references/architecture.md` が推奨する自律選択が物理的に取れないケース。**#3 と #4 で連続再現・Contract 付記で事前明示することで PMO Accept まで到達可能であることが確認された** |
| playwright chromium 欠落 | `tests/integration/test_studio_js_utils.py` の 33 テストが `BrowserType.launch: Executable doesn't exist` で失敗する pre-existing 状態 | 今回の変更と無関係。`playwright install chromium` を実行すれば解消するが、現状では未影響テストとして記録・スキップ判断。pytest 全体カウント時は「952 passed / 33 skipped(playwright)」と明示する |

---

## 運用メモ

- **PM Agent 起動時**: 上記「技術的発見 / プロジェクト固有パターン」から、今回のタスクに該当するものを抽出して渡す（全文は渡さない）
- **Developer Spec へ昇格する閾値**: PMO 指摘カテゴリが 2 回以上繰り返されたら対策列を Developer Spec のデフォルトに昇格する
- **環境制約の扱い**: PM Agent 内 subagent 不在のような制約は、スキル側（agent-company-v2）の harness 更新候補として ssr にフィードバックする可能性あり
