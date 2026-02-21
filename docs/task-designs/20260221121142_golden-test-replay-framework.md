# タスク設計書: ワークフロー回帰テスト・リプレイフレームワーク（Golden Test）

最終更新: 2026-02-21
- ステータス: 完了(done)
- 作成者: Claude Code
- レビュー: shogohasegawa
- 対象コンポーネント: backend
- 関連: `docs/product/vision.md`, `docs/product/goals.md`, `docs/product/milestones.md`
- チケット/リンク: 該当なし
- 関連ゴールID: G-20（新規）
- 関連マイルストーンID: M-49, M-50, M-51, M-52（すべて新規）

## 0. TL;DR

- 実行トレース（NodeTrace の input/output_snapshot）をゴールデンケースとして `.yagra/golden/` に保存し、ワークフロー YAML 変更後の回帰検証基盤を提供する。
- LLM ハンドラーをゴールデンケースの応答でモックすることで、API 呼び出しなし・決定論的にワークフロー構造（ルーティング・データフロー）の正当性を検証する。
- CLI（`yagra golden save` / `yagra golden test`）と MCP ツール（`run_golden_tests`）の 2 経路で利用可能にし、人間とコーディングエージェントの双方が回帰検証を実行できる。
- エージェントの最適化サイクルを `propose_update → run_golden_tests → apply_update` に拡張し、変更前の品質担保を自動化する。

## 1. 背景 / 課題

- **回帰検証の不在**: 現在の Yagra は Build → Run & Observe → Analyze → Approve & Update の最適化サイクルを提供するが、ワークフロー YAML 変更後に「以前動作していたケースが壊れていないか」を検証する仕組みがない。
- **LLM 非決定性の壁**: ワークフローに LLM ノードが含まれるため、同一入力でも出力が毎回変わり、単純な再実行比較では回帰テストが成立しない。
- **エージェント最適化の安全性**: `propose_update → apply_update` のサイクルで、エージェントが提案した変更が既存の動作を壊さないことを変更適用前に確認する手段がない。
- **手動確認の限界**: ワークフローが複雑化するにつれ、変更影響を人間が目視で確認することが困難になる。

## 2. ゴール / 非ゴール

### 2.1 ゴール

- **G-20（新規）: ワークフロー変更後にゴールデンケースベースの回帰検証ができる**
  - 到達判定: 既存トレースからゴールデンケースを保存し、ワークフロー YAML 変更後に `yagra golden test` で実行パス・ノード入出力の回帰を検証できる。LLM ノードはモック応答で決定論的にテストされ、API 呼び出しが不要である。コーディングエージェントが MCP 経由で `run_golden_tests` を実行し、`propose_update → run_golden_tests → apply_update` のサイクルを回せる。

### 2.2 非ゴール

- LLM 出力の品質評価（LLM-as-a-Judge による意味的比較）は本タスクのスコープ外。将来の拡張として検討する。
- プロンプト変更に対する出力品質の A/B テストは対象外。
- ゴールデンケースの自動生成・自動更新は対象外。ゴールデンケースは人間またはエージェントの明示的な操作で保存する。
- WebUI からのゴールデンテスト操作は対象外。CLI と MCP ツールに限定する。
- リモートストレージ（S3 等）へのゴールデンケース保存は対象外。ローカルファイルシステムに限定する。

## 3. スコープ / 影響範囲

- **変更対象**: ドメインエンティティ、ユースケース、アダプタ（CLI / MCP）、テスト
- **影響範囲**: 既存の CLI / MCP / トレース機構に追加。既存 API の後方互換を維持する。
- **互換性**: 破壊的変更なし。新規コマンド・ツールの追加のみ。
- **依存関係**:
  - 内部: `WorkflowRunTrace`（`src/yagra/domain/entities/trace.py`）、`TraceCollector`、`LocalTraceSink`、MCP サーバー、`Yagra.invoke()`
  - 外部: 追加ライブラリ不要（標準ライブラリ + 既存依存のみ）

## 4. 要件

### 4.1 機能要件

| ID | 要件 | 優先度 |
| --- | --- | --- |
| FR-01 | 成功した WorkflowRunTrace からゴールデンケースを生成・保存できる | Must |
| FR-02 | ゴールデンケースに名前・説明を付与できる | Must |
| FR-03 | ワークフロー YAML を変更後、ゴールデンケースに対してリプレイテストを実行できる | Must |
| FR-04 | リプレイ時、LLM ハンドラーをゴールデンケースの output_snapshot でモックし、API 呼び出しを発生させない | Must |
| FR-05 | 実行パス（ノード訪問順序）の一致を検証できる | Must |
| FR-06 | 各ノードの input_snapshot の一致を検証できる | Must |
| FR-07 | 非 LLM ノードの output_snapshot の一致を検証できる | Must |
| FR-08 | ノード単位で比較戦略（exact / structural / skip）を指定できる | Should |
| FR-09 | CLI コマンド `yagra golden save` / `yagra golden test` / `yagra golden list` を提供する | Must |
| FR-10 | MCP ツール `run_golden_tests` を提供する | Must |
| FR-11 | テスト結果を構造化 JSON で出力できる | Must |
| FR-12 | 複数のゴールデンケースを一括でテスト実行できる | Should |

### 4.2 非機能要件 / 制約

- ゴールデンケース 1 件あたりの保存・読み込みが 1 秒以内で完了すること。
- テスト実行時に外部 API 呼び出し（LLM 等）を一切行わないこと。
- 既存のテスト（`pytest`）実行時間に影響を与えないこと。
- Hexagonal Architecture の責務分離（domain / application / ports / adapters）を遵守すること。
- Python 3.12+、型ヒント必須、`ruff` / `mypy` クリアを維持すること。

## 5. 仕様 / 設計

### 5.1 全体方針

ゴールデンテストの核心は **「LLM をモックした決定論的リプレイ」** である。

1. **保存フェーズ**: 成功した `WorkflowRunTrace` から、ノードごとの `input_snapshot` / `output_snapshot` と実行パスを抽出し、ゴールデンケースとして永続化する。
2. **リプレイフェーズ**: ゴールデンケースの `initial_state` でワークフローを再実行する。LLM ハンドラー（`llm` / `structured_llm` / `streaming_llm`）はゴールデンケースの `output_snapshot` を返すモックハンドラーに差し替える。
3. **比較フェーズ**: リプレイ結果とゴールデンケースを比較し、実行パス・ノード入出力の差分を報告する。

```
                     ┌─────────────┐
                     │  Trace JSON │  (既存の .yagra/traces/)
                     └──────┬──────┘
                            │ yagra golden save
                            ▼
                     ┌─────────────┐
                     │ Golden Case │  (.yagra/golden/{workflow}/{name}.json)
                     └──────┬──────┘
                            │ yagra golden test
                            ▼
               ┌────────────────────────┐
               │   Golden Test Runner   │
               │  ┌──────────────────┐  │
               │  │ Mock LLM Handler │  │ ← ゴールデンケースの output で応答
               │  └──────────────────┘  │
               │  ┌──────────────────┐  │
               │  │ Real Non-LLM     │  │ ← 実際に実行
               │  └──────────────────┘  │
               └────────────┬───────────┘
                            │
                            ▼
                     ┌─────────────┐
                     │ Test Report │  (pass/fail + diffs)
                     └─────────────┘
```

### 5.2 変更点一覧

| 対象 | 変更内容 | 影響 | 備考 |
| --- | --- | --- | --- |
| `src/yagra/domain/entities/golden_case.py` | GoldenCase / GoldenTestResult / NodeComparisonResult エンティティ新規作成 | なし | 新規ファイル |
| `src/yagra/domain/entities/comparison.py` | ComparisonStrategy enum / 比較関数の定義 | なし | 新規ファイル |
| `src/yagra/ports/outbound/golden_case_repository.py` | GoldenCaseRepositoryPort インターフェース定義 | なし | 新規ファイル |
| `src/yagra/adapters/outbound/local_golden_case_store.py` | ファイルベースのゴールデンケース保存・読み込み実装 | なし | 新規ファイル |
| `src/yagra/application/use_cases/golden_test_runner.py` | リプレイ実行 + 比較ロジック | なし | 新規ファイル |
| `src/yagra/application/use_cases/golden_case_manager.py` | ゴールデンケースの保存・一覧・削除ユースケース | なし | 新規ファイル |
| `src/yagra/__init__.py` | `yagra golden` サブコマンド追加 | CLI 拡張 | 既存コマンドに影響なし |
| `src/yagra/adapters/inbound/mcp_server.py` | `run_golden_tests` ツール追加 | MCP 拡張 | 既存ツールに影響なし |
| `tests/unit/domain/test_golden_case.py` | ドメインエンティティのテスト | なし | 新規ファイル |
| `tests/unit/application/test_golden_test_runner.py` | リプレイ・比較ロジックのテスト | なし | 新規ファイル |
| `tests/unit/adapters/test_local_golden_case_store.py` | ファイル I/O のテスト | なし | 新規ファイル |
| `tests/integration/test_golden_test_e2e.py` | E2E テスト（保存 → YAML 変更 → テスト実行） | なし | 新規ファイル |

### 5.3 詳細

#### API

**CLI: `yagra golden` サブコマンド群**

```
yagra golden save --trace <trace-file-path> --name <case-name> [--description <text>] [--golden-dir <dir>]
yagra golden test --workflow <yaml-path> [--name <case-name>] [--golden-dir <dir>] [--bundle-root <dir>] [--format text|json]
yagra golden list [--workflow <name>] [--golden-dir <dir>] [--format text|json]
```

- `golden save`: 指定したトレースファイルからゴールデンケースを生成・保存する。
- `golden test`: 指定ワークフローに対してゴールデンケースを実行する。`--name` 省略時は該当ワークフローの全ケースを実行する。
- `golden list`: 保存済みゴールデンケースの一覧を表示する。
- `--golden-dir` のデフォルトは `.yagra/golden/`。

**MCP ツール: `run_golden_tests`**

```json
{
  "name": "run_golden_tests",
  "description": "Run golden test cases against a workflow to verify regression",
  "inputSchema": {
    "type": "object",
    "properties": {
      "workflow_path": { "type": "string", "description": "Path to workflow YAML" },
      "case_name": { "type": "string", "description": "Specific case name (optional, runs all if omitted)" },
      "golden_dir": { "type": "string", "description": "Golden case directory (default: .yagra/golden/)" }
    },
    "required": ["workflow_path"]
  }
}
```

返却値: `GoldenTestResult` の JSON 表現（全テスト結果のリスト + サマリ）。

**最適化サイクルの拡張**:

```
propose_update (差分プレビュー)
    → run_golden_tests (回帰テスト)
    → apply_update (変更適用) or rollback
```

エージェントは `run_golden_tests` の結果が全件 `passed` であることを確認してから `apply_update` を呼び出す。失敗があれば提案を修正して再度 `propose_update` する。

**ポートインターフェース**

**GoldenCaseRepositoryPort** (`src/yagra/ports/outbound/golden_case_repository.py`):

```python
class GoldenCaseRepositoryPort(ABC):
    @abstractmethod
    def save(self, case: GoldenCase) -> str: ...  # Returns file path

    @abstractmethod
    def load(self, workflow_name: str, case_name: str) -> GoldenCase: ...

    @abstractmethod
    def list(self, workflow_name: str | None = None) -> list[GoldenCase]: ...

    @abstractmethod
    def delete(self, workflow_name: str, case_name: str) -> bool: ...

    @abstractmethod
    def exists(self, workflow_name: str, case_name: str) -> bool: ...
```

**LocalGoldenCaseStore** (`src/yagra/adapters/outbound/local_golden_case_store.py`):

- 保存先: `.yagra/golden/{workflow_name}/{case_name}.json`
- `GoldenCase.model_dump(mode="json")` で JSON シリアライズ
- ディレクトリ自動作成（`mkdir -p` 相当）

**ユースケースインターフェース**

**GoldenCaseManager** (`src/yagra/application/use_cases/golden_case_manager.py`):

```python
class GoldenCaseManager:
    def __init__(self, repository: GoldenCaseRepositoryPort) -> None: ...

    def save_from_trace(
        self,
        trace: WorkflowRunTrace,
        case_name: str,
        description: str = "",
        comparison_overrides: dict[str, ComparisonStrategy] | None = None,
    ) -> GoldenCase:
        """Create a golden case from a successful trace.

        Args:
            trace: A successful WorkflowRunTrace to use as reference.
            case_name: Name for the golden case (kebab-case).
            description: Optional human-readable description.
            comparison_overrides: Per-node comparison strategy overrides.

        Returns:
            The saved GoldenCase.

        Raises:
            ValueError: If trace has failed status or case_name is invalid.
        """

    def list_cases(self, workflow_name: str | None = None) -> list[GoldenCase]: ...

    def delete_case(self, workflow_name: str, case_name: str) -> bool: ...
```

**GoldenTestRunner** (`src/yagra/application/use_cases/golden_test_runner.py`):

```python
class GoldenTestRunner:
    def __init__(self, repository: GoldenCaseRepositoryPort) -> None: ...

    def run(
        self,
        golden_case: GoldenCase,
        workflow_path: str | Path,
        registry: NodeRegistryPort | None = None,
        bundle_root: str | Path | None = None,
    ) -> GoldenTestResult:
        """Execute a golden test against the current workflow YAML.

        Args:
            golden_case: The reference golden case to test against.
            workflow_path: Path to the current workflow YAML.
            registry: Optional custom registry. If None, uses default
                with golden mock handlers.
            bundle_root: Optional bundle root for prompt_ref resolution.

        Returns:
            GoldenTestResult with per-node comparison details.
        """

    def run_all(
        self,
        workflow_name: str,
        workflow_path: str | Path,
        registry: NodeRegistryPort | None = None,
        bundle_root: str | Path | None = None,
    ) -> list[GoldenTestResult]:
        """Run all golden cases for a workflow."""
```

**リプレイ実行の詳細手順**:

1. ゴールデンケースをロードする。
2. 現在のワークフロー YAML をパース・バリデーションする。
3. ゴールデンケースの LLM ノード（`is_llm_handler=True`）に対して、`output_snapshot` を返すモックハンドラーを生成する。
4. モックハンドラーを登録したレジストリでワークフローをビルドする。
5. `initial_state` でワークフローを `invoke()` する（`trace=True`）。
6. 実行結果のトレースとゴールデンケースを比較する:
   - 実行パスの一致を検証
   - 各ノードの `input_snapshot` を比較（`comparison_strategy` に従う）
   - 非 LLM ノードの `output_snapshot` を比較
7. `GoldenTestResult` を返却する。

#### UI

該当なし（WebUI からのゴールデンテスト操作は非ゴール。CLI と MCP ツールに限定する。）

#### データモデル / 永続化

**GoldenCase** (`src/yagra/domain/entities/golden_case.py`):

```python
class NodeSnapshot(BaseModel):
    """Captured input/output for a single node execution."""
    node_id: str
    handler: str
    is_llm_handler: bool  # True for llm/structured_llm/streaming_llm
    input_snapshot: dict[str, Any]
    output_snapshot: dict[str, Any]
    comparison_strategy: ComparisonStrategy = ComparisonStrategy.AUTO
    # AUTO: exact for non-LLM, structural for LLM

class GoldenCase(BaseModel):
    """A saved reference execution for regression testing."""
    schema_version: str = "1.0"
    case_name: str  # Human-readable name (kebab-case)
    description: str = ""
    workflow_name: str
    workflow_path: str  # Relative path to workflow YAML
    created_at: datetime
    source_run_id: str  # run_id of the originating WorkflowRunTrace
    initial_state: dict[str, Any]  # State passed to Yagra.invoke()
    final_state: dict[str, Any]  # Final state after execution
    execution_path: list[str]  # Ordered list of executed node_ids
    node_snapshots: dict[str, NodeSnapshot]  # node_id -> snapshot
    metadata: dict[str, Any] = {}
```

**ComparisonStrategy** (`src/yagra/domain/entities/comparison.py`):

```python
class ComparisonStrategy(str, Enum):
    EXACT = "exact"          # 完全一致（キーと値の両方）
    STRUCTURAL = "structural"  # キー一致 + 型一致（値は無視）
    SKIP = "skip"            # 比較をスキップ
    AUTO = "auto"            # LLM ノード → structural、非 LLM → exact
```

**GoldenTestResult** (`src/yagra/domain/entities/golden_case.py`):

```python
class NodeComparisonResult(BaseModel):
    """Comparison result for a single node."""
    node_id: str
    status: Literal["pass", "fail", "skip", "missing", "unexpected"]
    strategy_used: ComparisonStrategy
    input_match: bool | None = None  # None if skipped
    output_match: bool | None = None
    input_diff: dict[str, Any] | None = None  # Only on mismatch
    output_diff: dict[str, Any] | None = None
    message: str = ""

class GoldenTestResult(BaseModel):
    """Result of running a golden test case."""
    case_name: str
    workflow_name: str
    passed: bool
    executed_at: datetime
    execution_path_match: bool
    expected_path: list[str]
    actual_path: list[str]
    node_results: list[NodeComparisonResult]
    summary: str  # Human-readable summary
```

**ゴールデンケースの保存形式（JSON）**:

```json
{
  "schema_version": "1.0",
  "case_name": "happy-path-translate",
  "description": "Normal EN→JA translation flow",
  "workflow_name": "translate",
  "workflow_path": "workflows/translate.yaml",
  "created_at": "2026-02-21T12:00:00Z",
  "source_run_id": "a1b2c3d4-...",
  "initial_state": { "input_text": "Hello, world!" },
  "final_state": { "input_text": "Hello, world!", "translated": "こんにちは、世界！" },
  "execution_path": ["translate_node", "format_node"],
  "node_snapshots": {
    "translate_node": {
      "node_id": "translate_node",
      "handler": "llm",
      "is_llm_handler": true,
      "input_snapshot": { "input_text": "Hello, world!" },
      "output_snapshot": { "translated": "こんにちは、世界！" },
      "comparison_strategy": "auto"
    },
    "format_node": {
      "node_id": "format_node",
      "handler": "custom_formatter",
      "is_llm_handler": false,
      "input_snapshot": { "translated": "こんにちは、世界！" },
      "output_snapshot": { "formatted": "【翻訳結果】こんにちは、世界！" },
      "comparison_strategy": "auto"
    }
  },
  "metadata": {}
}
```

**ディレクトリ構成**:

```
.yagra/
├── traces/          # 既存のトレース出力先
│   └── translate/
│       └── translate_20260221T120000_a1b2c3d4.json
└── golden/          # 新規：ゴールデンケース保存先
    └── translate/
        ├── happy-path-translate.json
        └── error-handling-case.json
```

#### 設定 / 環境変数

- 追加の環境変数は不要。
- `--golden-dir` オプションで保存先を変更可能（デフォルト: `.yagra/golden/`）。

### 5.4 代替案と不採用理由

- **代替案A: LLM を実際に呼び出して出力を比較する**
  - 不採用理由: LLM 出力は非決定論的であり、テストの安定性が確保できない。また、テスト実行のたびに API コストが発生する。
- **代替案B: LLM-as-a-Judge で意味的比較を行う**
  - 不採用理由: 判定自体に LLM 呼び出しが必要でコストと非決定性が残る。v1 では決定論的な構造比較に限定し、意味的比較は将来の拡張とする。
- **代替案C: pytest プラグインとして実装する**
  - 不採用理由: Yagra の CLI / MCP 統合と一貫したインターフェースを維持するため、独自コマンドとして提供する。ただし、`conftest.py` で `yagra golden test` を呼び出す pytest fixture は将来検討可能。
- **代替案D: トレースファイルを直接ゴールデンケースとして利用する**
  - 不採用理由: トレースは実行時のメタデータ（タイミング、コスト等）を含み、ゴールデンケースとしては情報過多。専用のスキーマで必要最小限の情報を抽出・保存する方が保守性が高い。

## 6. 移行 / ロールアウト

- 新規機能の追加のみであり、既存機能への影響はない。段階的リリースは不要。
- マイルストーン M-49 → M-50 → M-51 → M-52 の順に実装し、各マイルストーン完了時点で PR を作成する。
- ロールバック条件: CI テスト失敗、既存テストの破壊。
- ロールバック手順: 該当 PR を revert する。

## 7. テスト計画

- **単体テスト**:
  - `tests/unit/domain/test_golden_case.py`: GoldenCase / NodeSnapshot / GoldenTestResult / ComparisonStrategy のシリアライズ・バリデーション
  - `tests/unit/domain/test_comparison.py`: 比較関数の exact / structural / skip 各戦略
  - `tests/unit/application/test_golden_case_manager.py`: save_from_trace / list / delete のロジック
  - `tests/unit/application/test_golden_test_runner.py`: モックハンドラー生成・リプレイ実行・比較ロジック
  - `tests/unit/adapters/test_local_golden_case_store.py`: JSON 読み書き・ディレクトリ管理
- **結合テスト**:
  - `tests/integration/test_golden_test_e2e.py`: トレース保存 → ゴールデンケース作成 → YAML 変更 → テスト実行 → 結果検証の E2E フロー
- **手動テスト**:
  - `yagra golden save` / `yagra golden test` / `yagra golden list` の CLI 動作確認
  - MCP サーバー経由での `run_golden_tests` 実行確認
- **LLM / 外部依存**:
  - LLM ハンドラーはゴールデンケースの output_snapshot でモックする。テスト実行時に外部 API 呼び出しは一切行わない。
  - 既存テストのモック方針（`unittest.mock.patch`）を踏襲する。
- **合格条件**:
  - 新規テスト全件パス
  - 既存テスト全件パス（回帰なし）
  - `ruff` / `mypy` クリア
  - カバレッジが既存水準（96%）を下回らない

## 8. 受け入れ基準

1. `yagra golden save --trace .yagra/traces/translate/translate_20260221T120000_a1b2c3d4.json --name happy-path` を実行すると、`.yagra/golden/translate/happy-path.json` にゴールデンケースが保存される。
2. `yagra golden list` を実行すると、保存済みゴールデンケースの一覧（ケース名・ワークフロー名・作成日時・説明）が表示される。
3. ワークフロー YAML を変更せずに `yagra golden test --workflow workflows/translate.yaml` を実行すると、全ケースが `passed` になる。
4. ワークフロー YAML のノード接続を変更して `yagra golden test` を実行すると、実行パスの不一致が検出され `failed` が報告される。
5. ワークフロー YAML の非 LLM ノードのロジック変更後に `yagra golden test` を実行すると、output_snapshot の差分が検出される。
6. MCP ツール `run_golden_tests` をエージェントが呼び出し、結果を JSON で取得できる。
7. `propose_update → run_golden_tests → apply_update` のサイクルが MCP 経由で完結する。

## 9. リスク / 対策

| リスク | 影響 | 対策 |
| --- | --- | --- |
| ゴールデンケースのスナップショットが大きすぎてファイルサイズが肥大化する | ストレージ消費、読み込み速度低下 | `_safe_snapshot()` の既存のトランケーション（repr 500 文字）を活用。将来的に `snapshot_keys` フィルタリングを検討 |
| ワークフロー構造の大幅な変更でゴールデンケースが無効化される | テストが常に失敗し、保守コストが増大 | ゴールデンケースの `workflow_path` / `execution_path` から変更検知し、更新を促すメッセージを表示する |
| 条件分岐のあるワークフローでリプレイの実行パスが分岐する | 同一入力でもモック応答により異なるパスを通る可能性 | モックハンドラーが返す応答をゴールデンケースと同一にすることで、同一の条件分岐結果を再現する |
| カスタムハンドラーの副作用（ファイル書き込み等）がリプレイ時に実行される | テスト環境を汚染する | v1 ではカスタムハンドラーはそのまま実行する。ドキュメントで副作用のあるハンドラーには `skip` 戦略の使用を推奨する |

## 10. オープン事項 / 要確認

該当なし

## 11. 実装タスクリスト

### M-49: ゴールデンケースのドメインモデルと保存機構を実装する

- [x] `src/yagra/domain/entities/golden_case.py` を新規作成（GoldenCase, NodeSnapshot, GoldenTestResult, NodeComparisonResult）
- [x] `src/yagra/domain/entities/comparison.py` を新規作成（ComparisonStrategy enum, 比較関数）
- [x] `src/yagra/ports/outbound/golden_case_repository.py` を新規作成（GoldenCaseRepositoryPort）
- [x] `src/yagra/adapters/outbound/local_golden_case_store.py` を新規作成（LocalGoldenCaseStore）
- [x] `src/yagra/application/use_cases/golden_case_manager.py` を新規作成（save_from_trace, list, delete）
- [x] `tests/unit/domain/test_golden_case.py` を新規作成
- [x] `tests/unit/domain/test_comparison.py` を新規作成
- [x] `tests/unit/adapters/test_local_golden_case_store.py` を新規作成
- [x] `tests/unit/application/test_golden_case_manager.py` を新規作成
- [x] `ruff` / `mypy` / `pytest` クリア確認

### M-50: ゴールデンテスト実行エンジンと比較戦略を実装する

- [x] `src/yagra/application/use_cases/golden_test_runner.py` を新規作成（GoldenTestRunner, モックハンドラー生成, 比較ロジック）
- [x] 比較戦略（exact / structural / skip / auto）の実装
- [x] モック LLM ハンドラー生成ロジックの実装
- [x] `tests/unit/application/test_golden_test_runner.py` を新規作成
- [x] `ruff` / `mypy` / `pytest` クリア確認

### M-51: `yagra golden` CLI コマンドを実装する

- [x] `src/yagra/__init__.py` に `golden` サブコマンド（save / test / list）を追加
- [x] `golden save`: トレースファイル → ゴールデンケース保存
- [x] `golden test`: ワークフロー YAML に対するゴールデンテスト実行
- [x] `golden list`: 保存済みケース一覧表示
- [x] `tests/unit/test_cli.py` にゴールデンテスト CLI のテストを追加
- [x] `tests/integration/test_golden_test_e2e.py` を新規作成（E2E フロー）
- [x] `ruff` / `mypy` / `pytest` クリア確認

### M-52: MCP ツール `run_golden_tests` と最適化サイクル統合

- [x] `src/yagra/adapters/inbound/mcp_server.py` に `run_golden_tests` ツールを追加
- [x] `propose_update → run_golden_tests → apply_update` サイクルの動作確認
- [x] MCP ツールのテスト追加
- [x] `ruff` / `mypy` / `pytest` クリア確認

## 12. ドキュメント更新

- [x] `docs/product/goals.md` に G-20 を追加
- [x] `docs/product/milestones.md` に M-49〜M-52 を追加
- [x] `docs/agent-integration-guide.md` にゴールデンテスト MCP ツールの利用方法を追記
- [x] `README.md` にゴールデンテスト機能の概要を追記（必要に応じて）
- [x] `CHANGELOG.md` に変更履歴を追記

## 13. 承認ログ

- 承認者: （未承認）
- 承認日時: —
- 承認コメント: —

## 実装開始条件

- [ ] ステータスが `承認済み(approved)` である
- [ ] 10. オープン事項が空である
- [ ] 受け入れ基準とテスト計画に合意済み
