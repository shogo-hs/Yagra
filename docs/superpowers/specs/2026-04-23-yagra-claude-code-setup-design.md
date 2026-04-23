# Yagra Claude Code セットアップ — 設計仕様

- **作成日**: 2026-04-23
- **ステータス**: Draft（ユーザーレビュー待ち）
- **対象リポジトリ**: `/workspace/Yagra`
- **関連スキル**: `superpowers:brainstorming` → `superpowers:writing-plans`

---

## 1. 背景

### 1.1 Yagra プロジェクトの特性

- **アーキテクチャ**: Hexagonal Architecture（`adapters / application / domain / ports`）
- **スタック**: Python 3.12+ / `uv` / `ruff` / `mypy` / `pytest` / `pre-commit` / LangGraph / MCP Server
- **チーム体制**: business / team プロジェクト（複数エンジニアによる共同開発）
- **既存ドキュメント**: `CONTRIBUTING.md`（312行、包括的）、`docs/rules/code_architecture`、`docs/rules/solid`、`docs/adr`

### 1.2 現状（変更前）

yagra は従来、**canonical model + 配布パターン**で複数の AI コーディングエージェントに対応していた：

- `docs/ai/canonical/`: エージェント非依存の正本ドキュメント（`global-policies.md`, `task-routing.md`, `coding-standards.md`）
- `docs/ai/playbooks/*.md`（6 本）: タスク別プレイブック
- `docs/ai/playbook-assets/<name>/`: 各プレイブックの補助資料
- `scripts/sync_ai_context.py`（317行）: canonical から各エージェント向けに配布
- `.cursor/rules/*.mdc`: Cursor 向け生成物
- `AGENTS.md`: 汎用エージェント向け生成物（`CLAUDE.md` はシンボリックリンクで参照）

### 1.3 方針転換の理由

- **Claude Code 専用運用に統一**（ユーザー明言）
- 他エージェント対応の生成物・配布スクリプトが**二重管理の温床**になっている
- `knowledge_base` (kb) に蓄積された **Claude Code ベストプラクティス**（CLAUDE.md 200行制限、`@` 参照、Skills/Rules/Agents 分離、4 層防御等）を反映した最適化を行う

### 1.4 既存 AGENTS.md に含まれる重要運用規約（移行時の保全対象）

現行 `AGENTS.md` は canonical から生成されたメタファイルだが、**実質的な運用規約**を含む。これらは新構造にマッピングして保全する：

| 運用規約 | 新しい配置先 |
|----------|--------------|
| `uv add / uv remove / uv sync` 強制、`pip install` 禁止 | `CONTRIBUTING.md`（既存）+ `CLAUDE.md` で強調 |
| 秘密情報（APIキー・`.env.keys` 等）の出力・コミット禁止 | `.claude/rules/security.md` |
| 想定外の大量差分・履歴破壊操作は停止しユーザー再確認 | `.claude/rules/security.md` + `CLAUDE.md` |
| タスク設計書に `関連ゴールID` / `関連マイルストーンID` を必ず記載 | `.claude/skills/task-design-gate/SKILL.md` |
| プロダクト方針（`docs/product/vision.md` 等）を正本管理 | `CLAUDE.md`（参照として `@docs/product/`） |
| `README.md` vs `CLAUDE.md` の役割分離（人間向け vs エージェント向け） | `CLAUDE.md` の冒頭に明記 |
| CI 必須・品質ゲート不一致許容しない | `CONTRIBUTING.md`（既存） |
| `.env.development` / `.env.production` + dotenvx `encrypted:` 形式管理 | `CONTRIBUTING.md`（既存）、`.claude/rules/security.md` で参照 |
| バージョンリリース時の 3 箇所同期（`CHANGELOG.md` 日本語・`docs/sphinx/source/changelog.md` 英語・GitHub Release 英語） | `.claude/skills/release-ops/SKILL.md` + `CLAUDE.md` |
| Keep a Changelog 形式（Added / Changed / Deprecated / Removed / Fixed / Security） | `.claude/skills/release-ops/SKILL.md` |
| Semantic Versioning と `pyproject.toml` の `version` 一致 | `.claude/skills/release-ops/SKILL.md` + `CLAUDE.md` |
| ADR / アーキテクチャ判断記録 | `.claude/skills/adr-management/SKILL.md` |

---

## 2. ゴールと非ゴール

### 2.1 ゴール

1. Claude Code ベストプラクティス（kb 実装）を反映した `.claude/` 構造を確立
2. canonical model を解体し、Claude Code ネイティブの構成に移行
3. チーム開発における**可逆性と品質**を確保する段階的マイグレーションを実施
4. `CONTRIBUTING.md` との責務重複を排除し、単一情報源を担保

### 2.2 非ゴール（今回のスコープ外）

- **PreToolUse フック（Layer 2 防御）**: 運用パターン蓄積後の後続タスク
- **`git-analyst` 等の追加サブエージェント**: 必要性が明確化した時点で追加
- **`.claude/rules/python-code.md`, `tests.md`, `adr.md` 等の path-specific rule**: 繰り返し指摘パターンが見えた時点で追加
- **スキルの統合（`python-setup` 等）**: 運用データ蓄積後の判断
- **グローバルインストール対応（`~/.claude/skills/` への切出）**: yagra 運用定着後

---

## 3. 主要設計決定

対話的合意事項（Q2-1〜Q3-6）を総括する。

### 3.1 CLAUDE.md 構造（Q2-1, Q2-2, Q2-3）

| 決定 | 内容 |
|------|------|
| **分量** | 80-100 行（kb の 128 行を参考） |
| **重複排除** | `CONTRIBUTING.md` 既存内容は `@CONTRIBUTING.md` 参照で再利用 |
| **スキル一覧** | `.claude/rules/skill-catalog.md` に外出し（kb パターン踏襲） |
| **セキュリティ** | Layer 1（permissions.deny）+ Layer 4（CLAUDE.md/rules）で開始、Layer 2 は後続 |

### 3.2 ファイル整理（Q3-1）

- `AGENTS.md`: **削除**
- `CLAUDE.md`: シンボリックリンク解除し**実体化**（新規執筆）
- `.cursor/`: **削除**

### 3.3 Skills（Q3-2, Q3-3）

- **命名**: プレフィックスなし（既存 playbook 名を踏襲: `task-design-gate`, `git-commit` 等）
- **粒度**: 1:1 移行（6 playbook + `release-ops` = **7 スキル**）
- **構造**: `.claude/skills/<name>/SKILL.md` + `references/`（Progressive Disclosure）

### 3.4 Agents（Q3-4）

初期は `architecture-reviewer.md` の **1 個のみ**（Hexagonal / SOLID 違反検出専用）。

### 3.5 Rules（Q3-5）

最小構成の **3 ファイル**:

| ファイル | paths | 役割 |
|----------|-------|------|
| `skill-catalog.md` | `["**"]` | スキル表と選択指針 |
| `security.md` | `["**"]` | Layer 4 運用規範 |
| `architecture.md` | `["src/yagra/**"]` | Hexagonal 境界規律（`@docs/rules/` 参照） |

### 3.6 マイグレーション（Q3-6）

**3 フェーズ段階マイグレーション**（各フェーズを独立 PR として運用）。

---

## 4. 最終ディレクトリ構造

```
Yagra/
├── CLAUDE.md                           # 新規実体（~80-100行）
├── CONTRIBUTING.md                     # 現状維持（312行）
├── .gitignore                          # .claude/ 除外解除、.claude/settings.local.json のみ除外
├── .claude/
│   ├── settings.json                   # Layer 1 (permissions.allow/deny)
│   ├── settings.local.json.example     # ローカル設定テンプレ
│   ├── skills/
│   │   ├── task-design-gate/
│   │   │   ├── SKILL.md
│   │   │   └── references/             # 旧 playbook-assets から
│   │   ├── python-uv-ci-setup/
│   │   │   ├── SKILL.md
│   │   │   └── references/
│   │   ├── python-project-bootstrap/
│   │   │   ├── SKILL.md
│   │   │   └── references/
│   │   ├── api-spec-sync/
│   │   │   ├── SKILL.md
│   │   │   └── references/
│   │   ├── adr-management/
│   │   │   ├── SKILL.md
│   │   │   └── references/
│   │   ├── git-commit/
│   │   │   ├── SKILL.md
│   │   │   └── references/
│   │   └── release-ops/                # 新設
│   │       └── SKILL.md
│   ├── rules/
│   │   ├── skill-catalog.md            # paths: ["**"]
│   │   ├── security.md                 # paths: ["**"]
│   │   └── architecture.md             # paths: ["src/yagra/**"]
│   ├── agents/
│   │   └── architecture-reviewer.md
│   └── scripts/
│       └── .gitkeep
└── docs/
    ├── agent-integration-guide.md      # docs/ai/ から移動（内容精査後判断）
    ├── ci-integration-guide.md         # 同上
    ├── adr/                            # 現状維持
    ├── api/                            # 現状維持
    ├── architecture/                   # 現状維持
    ├── product/                        # 現状維持
    ├── rules/                          # 現状維持
    ├── sphinx/                         # 現状維持
    ├── task-designs/                   # 現状維持
    └── superpowers/
        └── specs/
            └── 2026-04-23-yagra-claude-code-setup-design.md   # 本ファイル

削除対象:
- Yagra/AGENTS.md
- Yagra/.cursor/
- Yagra/docs/ai/canonical/
- Yagra/docs/ai/playbooks/
- Yagra/docs/ai/playbook-assets/
- Yagra/docs/ai/（空化後）
- Yagra/scripts/sync_ai_context.py
```

---

## 5. CLAUDE.md 設計

### 5.1 内容骨子（~85 行）

```markdown
# CLAUDE.md — Yagra

Yagra は〈1 行プロジェクトサマリ ※実装時にユーザー確認の上記入〉。
本ファイルは Claude Code 向けの運用規約。人間向けの入口は `@README.md`。

## プロジェクト要点
- Hexagonal Architecture（adapters / application / domain / ports）
- Python 3.12+ / uv / LangGraph / MCP Server
- 詳細: @README.md / @CONTRIBUTING.md / @docs/architecture/

## 役割分離
- `README.md`: 人間が最初に理解するための入口（目的・全体像・セットアップ）
- `CLAUDE.md`（本ファイル）: エージェントが実行時に守る規約
- 同じ内容を両方に重複記載しない

## 作業モード（運用規範）
1. 計画優先: 3ステップ以上 or 設計判断を伴うタスクは必ず計画を提示し承認を得る
2. サブエージェント優先: 調査・探索・並列分析はサブエージェント化
3. 完了前検証: テスト実行・ログ確認を行い「スタッフエンジニアが承認するか」を自問
4. 根本原因優先: 場当たり修正禁止
5. 最小変更: 必要箇所のみ変更
6. 想定外の大量差分・履歴破壊操作・広範囲削除が必要な場合は作業を停止しユーザー再確認

## タスクルーティング
- スキル一覧と選択指針: @.claude/rules/skill-catalog.md
- タスク設計書には `関連ゴールID` / `関連マイルストーンID` を必ず記載（@.claude/skills/task-design-gate/SKILL.md）

## 開発コマンド・コーディング標準
- セットアップ、テスト、lint、pre-commit、パッケージ管理: @CONTRIBUTING.md
- Python パッケージ操作は `uv add / uv remove / uv sync` のみ。`pip install` / `uv pip install` 禁止
- アーキテクチャ・SOLID規約: @docs/rules/code_architecture/ / @docs/rules/solid/
- ADR: @docs/adr/（`/adr-management` で作成）

## プロダクト文脈
- ビジョン・ゴール・マイルストーン: @docs/product/（正本）
- API 仕様: @docs/api/

## リリース規範
- Semantic Versioning、`pyproject.toml` の `version` と一致
- 3 箇所同期: CHANGELOG.md（日本語正本）/ docs/sphinx/source/changelog.md（英語）/ GitHub Release（英語）
- Keep a Changelog 形式（Added / Changed / Deprecated / Removed / Fixed / Security）
- 具体手順: @.claude/skills/release-ops/SKILL.md

## セキュリティ（4層防御）
- Layer 1: .claude/settings.json の permissions.deny（.env*, credentials, secret 読取禁止）
- Layer 2: PreToolUse フック（将来実装予定）
- Layer 3: MCP/サンドボックス境界
- Layer 4: 本 CLAUDE.md + @.claude/rules/security.md の運用規範
- 環境変数: `.env.development` / `.env.production` + dotenvx `encrypted:` 形式。`.env.keys` コミット禁止

## Claude Code 運用ノート
- コミュニケーション言語: 日本語
- 計画・タスクは tasks/todo.md、教訓は tasks/lessons.md
- Skills は .claude/skills/<name>/SKILL.md（`commands/` は非推奨）

## 参照
- 詳細ガイド: @CONTRIBUTING.md / @docs/agent-integration-guide.md / @docs/ci-integration-guide.md
```

### 5.2 記述原則

- **普遍的内容のみ**（頻繁に変わる情報は `@` 参照先へ）
- **重複排除**（`CONTRIBUTING.md` との重複禁止）
- **行動指向**（「何をする／しない」で記述、背景説明は参照先へ）

---

## 6. セキュリティ設計（Layer 1 + Layer 4）

### 6.1 Layer 1: `.claude/settings.json` の permissions

```json
{
  "permissions": {
    "allow": [
      "Read", "Glob", "Grep",
      "Bash(git status)", "Bash(git diff*)", "Bash(git log*)", "Bash(git show*)",
      "Bash(uv *)", "Bash(pytest*)", "Bash(ruff*)", "Bash(mypy*)",
      "Bash(ls*)", "Bash(cat*)",
      "Skill", "Edit", "Write",
      "mcp__*"
    ],
    "deny": [
      "Read(.env)", "Read(.env.*)",
      "Read(**/.env)", "Read(**/.env.*)",
      "Read(**/credentials*)", "Read(**/*secret*)",
      "Bash(rm -rf *)",
      "Bash(git push --force*)",
      "Bash(git reset --hard*)"
    ]
  },
  "model": "claude-opus-4-7",
  "effortLevel": "high"
}
```

- `allow` は**最小許可**を基本とし、運用で追加判断する
- `deny` は**絶対防御線**（秘密情報読取 + 破壊操作）

### 6.2 `settings.local.json.example`

```json
{
  "permissions": {
    "defaultMode": "bypassPermissions",
    "allow": []
  },
  "enabledMcpjsonServers": ["yagra"]
}
```

実ファイル `settings.local.json` は `.gitignore` で除外し、各開発者が自身のローカル設定をコピーして使う。

### 6.3 Layer 4: `.claude/rules/security.md`

```markdown
---
paths: ["**"]
---

# セキュリティ運用規範

## 秘密情報の取扱い
- .env, credentials, secret を含むファイルの読取は permissions.deny で禁止
- 読取できても外部送信（WebFetch / MCP / curl 等）を行わない
- 秘密情報がソースに含まれる疑いがある場合は作業を停止し、ユーザーに確認する

## 破壊的操作
- rm -rf, git reset --hard, git push --force は deny 済み
- それ以外の取消困難操作（DB truncate, ファイル上書き等）は実行前に確認
- 未追跡ファイルの削除前に git status を確認

## 外部通信
- WebFetch / WebSearch の利用時は、送信内容に秘密情報が含まれないことを確認
- MCP サーバ経由の外部送信も同等に扱う
```

---

## 7. Skills 設計

### 7.1 共通フロントマター方針

```yaml
---
name: <skill-name>
description: <1 行説明>
when_to_use: <発動条件>
argument-hint: <引数ヒント>
allowed-tools: [Read, Edit, Write, Bash, Grep, Glob]
---
```

- `context: fork` は重いリサーチ系のみ検討
- `user-invocable: true` はユーザー明示呼出を許可する場合のみ

### 7.2 7 スキル一覧

| スキル | 由来 | 新規/移行 | references/ 必要性 |
|--------|------|-----------|---------------------|
| `task-design-gate` | `docs/ai/playbooks/task-design-gate.md` | 移行 | ⚪ |
| `python-uv-ci-setup` | 同 | 移行 | ⚪ |
| `python-project-bootstrap` | 同 | 移行 | ⚪ |
| `api-spec-sync` | 同 | 移行 | ⚪ |
| `adr-management` | 同 | 移行 | ⚪ |
| `git-commit` | 同 | 移行 | ⚪ |
| `release-ops` | 新設（SemVer, CHANGELOG, タグ） | 新規 | ⚪ |

各スキルの内容詳細は実装フェーズで決定（本設計では枠組みのみ定義）。

---

## 8. Agents 設計

### 8.1 `architecture-reviewer.md`

```markdown
---
name: architecture-reviewer
description: Hexagonal / SOLID 違反を検出する yagra 専用レビュアー
tools: [Read, Glob, Grep, Bash]
---

# Architecture Reviewer

## 責務
- Hexagonal 境界違反（adapters → domain 逆依存、application の I/O 混入）を検出
- SOLID 原則違反（単一責任、依存性逆転 等）を指摘
- docs/rules/code_architecture/ と docs/rules/solid/ のルールに基づく

## 使用方法
- src/yagra/ 配下の変更後に呼び出す
- import 関係、モジュール境界、副作用の局在性を機械的にチェック

## 参照
- @docs/rules/code_architecture/
- @docs/rules/solid/
- @docs/architecture/
```

---

## 9. Rules 設計

### 9.1 `.claude/rules/skill-catalog.md`

```markdown
---
paths: ["**"]
---

# Yagra スキルカタログ

## スキル一覧

| コマンド | 用途 |
|---------|------|
| /task-design-gate | タスク設計ゲート |
| /python-uv-ci-setup | Python + uv + CI 設定 |
| /python-project-bootstrap | Python プロジェクト初期化 |
| /api-spec-sync | API 仕様同期 |
| /adr-management | ADR 作成・管理 |
| /git-commit | 規約に沿った git commit |
| /release-ops | SemVer・CHANGELOG・タグ |

## 使い分け
- タスク設計を確認したい → /task-design-gate
- 新規 Python プロジェクトを作る → /python-project-bootstrap
- CI を設定したい → /python-uv-ci-setup
- API を変更した → /api-spec-sync
- 設計判断を記録 → /adr-management
- コミットを作成 → /git-commit
- リリース作業 → /release-ops
```

### 9.2 `.claude/rules/architecture.md`

```markdown
---
paths: ["src/yagra/**"]
---

# Yagra Architecture Rules

## Hexagonal 境界
- domain は外部（adapters, ports 実装）を参照しない
- application は domain と ports のみを参照する
- adapters は ports インターフェースを実装する
- ports はインターフェース定義のみ（実装は adapters で行う）

## チェックポイント
- import 文を確認（逆方向の依存禁止）
- domain 内に I/O コード（HTTP, DB, ファイル読書き）を置かない
- application 層での外部 API 呼出は ports 経由で

## 参照
- @docs/rules/code_architecture/
- @docs/rules/solid/
```

---

## 10. `.gitignore` 変更

**変更前**（229行目）:
```
.claude/
```

**変更後**:
```
.claude/settings.local.json
.claude/logs/
.claude/scripts/*.log
```

`.claude/` 本体は git 追跡、ローカル設定・ログのみ除外する。

---

## 11. マイグレーション計画（3 フェーズ）

### Phase 1: 加算（非破壊）

**目的**: 新構造を追加し、旧構造と並行稼働させる。

**前提**: セクション 1.4「既存 AGENTS.md に含まれる重要運用規約」のマッピング表を参照しつつ各ファイルを執筆する。

**作業**:
1. `.claude/settings.json` 作成（Layer 1 permissions）
2. `.claude/settings.local.json.example` 作成
3. `.claude/skills/<name>/` 7 個を作成
   - 6 移行スキルは `docs/ai/playbooks/*.md` の手順を基に `SKILL.md` フロントマター付与
   - `task-design-gate` には `関連ゴールID` / `関連マイルストーンID` 記載要件を明記
   - `release-ops` は新規執筆（3 箇所同期・Keep a Changelog・SemVer 規約を内包）
4. `.claude/skills/<name>/references/` を作成（`docs/ai/playbook-assets/<name>/` をコピー）
5. `.claude/rules/skill-catalog.md`, `security.md`, `architecture.md` 作成
   - `security.md` には 1.4 の秘密情報・破壊操作・env 運用規約を集約
6. `.claude/agents/architecture-reviewer.md` 作成
7. `.claude/scripts/.gitkeep` 作成
8. `CLAUDE.md` シンボリックリンク解除 → 実体ファイル化（新規執筆、~85行、1.4 マッピング反映）
9. `.gitignore` 調整
10. `CONTRIBUTING.md` を確認し、1.4 マッピングで CONTRIBUTING.md に割当てた項目が既に記載されているか検証（欠落があれば追記提案）

**検証**:
- Claude Code セッション再起動で `CLAUDE.md` が注入されること
- `.claude/rules/skill-catalog.md` が全域で参照可能なこと
- `.claude/rules/architecture.md` が `src/yagra/**` 編集時に注入されること
- `.claude/skills/*/SKILL.md` が `/<skill-name>` で呼び出せること
- `architecture-reviewer` サブエージェントが `src/yagra/` への変更レビューで発動すること

**ロールバック**:
- 旧 `AGENTS.md`, `docs/ai/canonical/`, `docs/ai/playbooks/` は残置されているため、`CLAUDE.md` を symlink に戻すだけで旧状態に復帰可能

### Phase 2: 移動

**目的**: 旧 `docs/ai/` 配下の保持対象を整理。

**作業**:
1. `docs/ai/agent-integration-guide.md`（469行）の内容精査
   - **判断基準**:
     - (a) `scripts/sync_ai_context.py` のソース一覧に含まれる → canonical 生成物 → 削除
     - (b) ファイル冒頭に「自動生成」「do not edit」等の注記がある → 生成物 → 削除
     - (c) 内容が canonical（`docs/ai/canonical/*.md`）と重複 → 生成物 → 削除
     - (d) (a)〜(c) のいずれでもなく、運用知識・ガイドラインが含まれる → 手書き → `docs/agent-integration-guide.md` へ移動
   - 内容の重要部分が新 `CLAUDE.md` / `CONTRIBUTING.md` / 各スキルに既にカバーされている場合は移動不要と判断できる
2. `docs/ai/ci-integration-guide.md`（215行）も同じ基準で精査
3. 他に `docs/ai/` 直下で保持すべきファイルがないことを確認

**検証**:
- 移動後、リポジトリ内の他ドキュメントからの参照（相対パス）が壊れていないことを `grep -r "docs/ai/"` で確認
- GitHub Wiki / README からの外部リンクが壊れていないか確認

### Phase 3: 削除

**目的**: 旧構造を一掃する。

**作業**（いずれも Phase 1-2 完了後の前提）:
1. `AGENTS.md` 削除
2. `.cursor/` 削除
3. `docs/ai/canonical/` 削除
4. `docs/ai/playbooks/` 削除
5. `docs/ai/playbook-assets/` 削除
6. `docs/ai/` 削除（空化確認後）
7. `scripts/sync_ai_context.py` 削除
8. 関連する README / CI 記述があれば更新（grep で特定）

**検証**:
- `grep -rn "sync_ai_context\|docs/ai/canonical\|docs/ai/playbooks\|AGENTS.md\|\.cursor" .` の結果が空（またはコミット履歴以外）
- pre-commit / CI / pytest が全てパス
- Claude Code セッションで全スキルが期待通り動作

---

## 12. リスクと緩和

| リスク | 影響 | 緩和策 |
|--------|------|--------|
| 既存 playbook 内容を読まず統合するとスキル機能が壊れる | 高 | Phase 1 で 1:1 移行を徹底、統合は後続タスクで判断 |
| `sync_ai_context.py` が CI から呼ばれていて削除で CI が落ちる | 中 | Phase 3 前に CI 設定（`.github/workflows/*`）を grep 検査 |
| agent-integration-guide.md に重要な運用知識があり消失 | 中 | Phase 2 で必ず内容精査、不明瞭なら `docs/` 直下に保持 |
| `.claude/` を git 追跡に変えたことで `settings.local.json` が誤コミット | 中 | `.gitignore` に明示除外、`.example` ファイルで誘導 |
| CLAUDE.md 実体化後に symlink 前提のツール（あれば）が壊れる | 低 | 事前に `ls -la AGENTS.md` の参照元を特定、参照があれば個別対応 |
| チーム開発で PR 分割による設定不整合期間が発生 | 低 | Phase 1-3 を短期間（1-2 スプリント以内）で完了 |
| CONTRIBUTING.md に 1.4 マッピング上の項目が実は未記載で CLAUDE.md から参照切れ | 中 | Phase 1 の作業 10 で CONTRIBUTING.md を精査し欠落を明示。必要なら CONTRIBUTING.md 更新を別 PR で提案 |
| `settings.json` の allow リストが実プロジェクトで不足し開発が阻害 | 中 | 初期は最小許可で出し、運用で追加する。`effortLevel: high` の許可要求ログを見て漸次拡張 |

---

## 13. 成功基準

1. Claude Code セッションで `CLAUDE.md` + `.claude/rules/*` が正常注入される
2. 7 スキル全てが `/<skill-name>` で呼び出し可能
3. `architecture-reviewer` が `src/yagra/` 配下の変更レビューで機能する
4. `.env` 読取試行が Layer 1 で deny される
5. 既存 `pytest` / `ruff` / `mypy` / `pre-commit` が全てパス
6. `docs/ai/`, `.cursor/`, `AGENTS.md`, `scripts/sync_ai_context.py` への参照がリポジトリ内から全て除去される
7. `CONTRIBUTING.md` との情報重複が `CLAUDE.md` 内に存在しない

---

## 14. 本設計が前提とする未解決事項

以下は**実装計画（writing-plans スキル）で具体化**する：

1. 既存 6 playbook（`docs/ai/playbooks/*.md`）の具体内容と SKILL.md 化時の書換範囲
2. `agent-integration-guide.md` / `ci-integration-guide.md` の内容精査結果
3. `release-ops` スキルの具体手順（SemVer バンプ、CHANGELOG 自動生成、タグ打ち）
4. `architecture-reviewer` エージェントが用いる具体的な検出ロジック
5. `settings.json` の `allow` リストの yagra 固有項目（uv / pytest / ruff / mypy 以外）

---

## 15. 参考資料

- kb: `/workspace/knowledge_base/30_Learning/Articles/20260304_claude-code-CLAUDE-md-best-practices.md`
- kb: `/workspace/knowledge_base/30_Learning/Articles/20260304_claude-code-skills-best-practices.md`
- kb: `/workspace/knowledge_base/30_Learning/Articles/20260413_claude-code-credential-guard-multi-layer-defense.md`
- kb: `/workspace/knowledge_base/CLAUDE.md`（128行の実装参考）
- kb: `/workspace/knowledge_base/.claude/settings.json`（4 層防御実装参考）
- kb: `/workspace/knowledge_base/.claude/rules/*.md`（path-specific rule 実装参考）
- 既存: `/workspace/Yagra/CONTRIBUTING.md`（312行、開発規範の参照先）
- 既存: `/workspace/Yagra/docs/rules/code_architecture/`, `/workspace/Yagra/docs/rules/solid/`
