# タスク間学習ログ

**最終更新**: 2026-04-24（Task #4 完了時）
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

## プロジェクト固有パターン

| Task | パターン | 適用場面 |
|------|---------|---------|
| #3 | 新 GitHub Actions workflow を追加する際は既存 `ci.yml` のバージョンラインを継承する（`actions/checkout@v6` / `actions/setup-python@v6` / `astral-sh/setup-uv@v7`） | 新 workflow ファイル作成時 |
| #3 | `main` ブランチには branch protection あり（REVIEW_REQUIRED）。直接 push / マージ不可。全変更は feature branch → PR → user 承認マージの経路を通る | 全タスク、特に PO 側の tracking 文書更新時の commit 運用 |
| #3 | 新 workflow には必ず `concurrency: group: <wf-name>-${{ github.ref }}` + `cancel-in-progress: true` を入れる（PMO 指摘で標準化） | 全 CI workflow |
| #3, #4 | 機能追加・修正は CHANGELOG.md の `[Unreleased]` セクションに Added / Changed / Fixed 等のカテゴリで追記する。**Mission Brief のチェックリスト標準項目として昇格済み**（#3 で PMO 指摘 → #4 で Contract 事前組込で指摘 0 件を実現） | すべての user-visible 変更 |
| #4 | `adapters/inbound/mcp_server.py` 内で tool 間の呼び出しをする際は private helper（`_assert_golden_passed` 等）に抽出して SRP を維持する。将来 CLI からも同一仕様を使う場合は application/use_cases/ への昇格を検討 | MCP tool 間で共通ロジックが発生した場合 |
| #4 | MCP tool の Pydantic `inputSchema` description と docs（agent-integration-guide.md）は同一内容で同期させる。AI エージェントが両方を参照する可能性があるため、挙動テーブル形式で docs にも書く | 新 MCP tool 追加 / 既存 tool API 変更時 |

## PMO指摘パターン分析

| 指摘カテゴリ | 頻度 | 対策 | ステータス |
|-------------|:----:|------|----------|
| concurrency 制御の追加（#3 で 1 回） | 1 | 2 回目以降出たら Developer Spec の CI workflow テンプレートに必須項目として昇格 | 監視中 |
| 0-match 時の silent success 防止（#3 で 1 回） | 1 | 2 回目以降出たら同様に昇格 | 監視中（#4 で類似パターン「no-case warning」を先取り実装。明示 warning 付き許可で無指摘） |
| CHANGELOG 追記（#3 で 1 回 → #4 で事前組込み無指摘） | 1 | **#4 で Contract に事前組込 → Mission Brief チェックリスト標準項目に昇格済み** | **昇格完了**（#4 PMO 指摘 0 件で効果確認） |

> #4 の PMO レビュー結果: Critical 0 / Major 0 / Minor 0。Contract 段階で前回 PMO 指摘パターンを事前に反映する運用が有効であることが確認できた。
> 「2 回以上繰り返したら昇格」の原則は、「1 回出たら次タスクの Contract で先回り反映」で実質的に先取りできる（ハーネス改善）。

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
