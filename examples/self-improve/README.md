# Self-Improve Walking Example

## 概要

このサンプルは、Yagra の差別化軸である「**AI が AI を評価する**」サイクルを体感するための walking example です。

2 ノードのワークフロー:

1. **`generate` ノード** — `create_llm_handler` + LiteLLM (`openai gpt-4o-mini`) で文章を生成
2. **`judge` ノード** — `create_judge_handler` + `claude_agent_sdk` (`sonnet`) で宣言的 rubric に照らして評価

`judge` ノードは出力を `{score: {<criterion>: int, _overall: float}, reasoning: str, rubric_items: [...]}` の構造で返します。`_overall` は rubric の全 criterion スコアの平均で、「この出力はどの程度 rubric を満たしたか」を 1 数値で要約します。

ビジョン `docs/product/vision.md` で Yagra は「propose → judge → apply の自己改善ループ」の基盤を提供すると謳っており、本 example はその入口（judge 部分）を自己完結で示します。

## Prerequisites

- Python 3.12+
- `yagra[llm,judge]` extra
  - `llm` extra が LiteLLM（generate ノード用）を提供
  - `judge` extra が `claude-agent-sdk`（judge ノード用）を提供
- `OPENAI_API_KEY` 環境変数（generate ノード、`gpt-4o-mini` 呼び出し用）
- **`claude login` 済み**（judge ノードの `claude_agent_sdk` が Claude subscription で認証するため。**別途の API キーは不要**）

## セットアップ

```bash
# 1. Yagra を LLM + Judge サポート付きでインストール
uv add "yagra[llm,judge]"

# 2. OpenAI API key を設定（generate ノード用）
export OPENAI_API_KEY="your-openai-key"

# 3. Claude CLI でログイン（judge ノード用、subscription 認証）
claude login
```

> **Note**: `generate` ノードは LiteLLM 経由なので OpenAI の API キー（または `anthropic` / `azure` / `gemini` 等、LiteLLM の provider）が必要です。`judge` ノードは `claude_agent_sdk` 経由の subscription 認証のため、ログイン済みの Claude CLI があれば API キー不要です。

## 実行

```bash
cd examples/self-improve
python run_example.py
```

期待される stdout（構造抜粋、具体的な数値や文言は実行ごとに変動します）:

```
Creating LLM handler (generate node, LiteLLM / openai gpt-4o-mini)...
Creating Judge handler (judge node, claude_agent_sdk / sonnet)...
Loading workflow from: .../examples/self-improve/workflow.yaml

Executing workflow with input: {'topic': 'Hexagonal Architecture', 'length': 3}

============================================================
Draft (generate node, gpt-4o-mini)
============================================================
Hexagonal Architecture, also known as Ports and Adapters, ...

============================================================
Judge Result (judge node, claude_agent_sdk / sonnet)
============================================================
  >>> Overall score: 4.00  <<<

  Per-criterion scores:
    - clarity: 4
    - accuracy: 4

  Reasoning: The draft covers three key points about Hexagonal Architecture.
  **Clarity:** The structure is logical and easy to follow ...
  **Accuracy:** All three statements are factually sound ...

  Rubric items:
    - clarity (4): The three-point structure is well-ordered ...
    - accuracy (4): All three statements are factually correct ...
============================================================
```

> `_overall` は rubric の全 criterion スコアの算術平均。上記は draft 3 文の典型的な評価例で、LLM 出力は非決定的なので実際は `3.5〜4.5` 程度の範囲でばらつきます。

## ファイル構成

```
examples/self-improve/
├── workflow.yaml       # ワークフロー定義（generate → judge）
├── prompts.yaml        # generate ノードのプロンプト（judge 側は default を活用）
├── run_example.py      # 実行スクリプト
└── README.md           # このファイル
```

### `workflow.yaml`

`generate` → `judge` の 2 ノード workflow。`judge` ノードの特徴:

- **`rubric` を inline で宣言**（`clarity` / `accuracy` の 2 criterion、scale 1-5）
- **system prompt は rubric から default が自動生成**されるため `prompts.yaml#judge` には `user` のみ書けば済む
- **`prompt_ref: "prompts.yaml#judge"`** で user prompt を参照。walking example では `generate` の `output_key: "draft"` を受けて `"Evaluate the following draft:\n\n{draft}"` と記述し、state の `draft` を judge に流し込む
- `output_key: "judge_result"` に評価結果（スコア・根拠・rubric_items）を書き込む

> Yagra 全体のルールとして inline `prompt` は許可されず、必ず `prompt_ref` 経由で外部 YAML を参照する必要がある。judge ノードも同じ制約下で動くため、user prompt を書くときは `prompts.yaml` の `judge` セクションを使う。

### `prompts.yaml`

`generate` ノードの system/user に加えて、`judge` ノードの user prompt を定義する。judge の system は省略（rubric から自動生成）。

```yaml
generate:
  system: "You are a concise technical writer."
  user: "Write a {length}-sentence introduction about {topic}. Keep it factual and accessible."

judge:
  user: "Evaluate the following draft:\n\n{draft}"
```

### `run_example.py`

- `OPENAI_API_KEY` 未設定時は早期 exit
- `create_llm_handler` と `create_judge_handler` を registry に登録
- `JudgeHandlerError`（`{error, message, summary, hint}` の 4 フィールド構造化エラー）を try/except で整形表示
- stdout で **`score._overall` を強調**（差別化軸の体験ポイント）

## 自己改善サイクル（Claude Code + MCP 対話）

この walking example は propose → judge → apply の自己改善ループの「**判定（judge）**」部分を自己完結で示すものです。実運用では、Claude Code の Yagra MCP server 経由で以下のような対話を通じて propose / apply を行います。

### 擬似対話（6 ステップ）

**Step 1** — 自己改善ワークフローを動かして判定結果を見る

> **You**: `self-improve` のワークフローを実行して judge の結果を教えて。
>
> **Claude**: `python examples/self-improve/run_example.py` を実行しました。
> - `draft`: "Hexagonal Architecture is a software design pattern ..."
> - `judge_result.score._overall`: 3.50（`clarity: 4`, `accuracy: 3`）
> - `reasoning`: "The draft is readable, but omits the ports/adapters distinction ..."

**Step 2** — 低スコア criterion を深掘り

> **You**: `accuracy` が低い。`rubric_items` を見せて。
>
> **Claude**: `rubric_items[1]` = `{name: "accuracy", score: 3, reasoning: "Missing the explicit mention of ports and adapters."}`

**Step 3** — 改善案を提案してもらう

> **You**: accuracy を上げるために prompt を改善して。
>
> **Claude**: `propose_update` MCP tool で diff を提案します。
> ```diff
>  generate:
> -  user: "Write a {length}-sentence introduction about {topic}. Keep it factual and accessible."
> +  user: "Write a {length}-sentence introduction about {topic}. Mention the key concepts (e.g., ports and adapters for Hexagonal Architecture) and keep it factual."
> ```

**Step 4** — diff を確認して承認

> **You**: OK、差分を適用して。
>
> **Claude**: `apply_update` を実行しました（`golden_pass_required=True` でリグレッション未検出）。

**Step 5** — 再実行して改善を検証

> **You**: もう一度実行して。
>
> **Claude**: `judge_result.score._overall`: 4.50（`clarity: 5`, `accuracy: 4`）に改善しました。

**Step 6** — 問題があればロールバック

> **You**: 前のバージョンに戻したい。
>
> **Claude**: `rollback_update` で 1 つ前のバージョンに復元しました。

### 将来拡張

現時点では propose / apply は MCP の `propose_update` / `apply_update` tool 経由で 1 回ずつ操作します。将来、実行トレース全体を LLM で一括評価する `evaluate_traces` 等の MCP tool の追加を予定しています。追加されると、複数ランの trace を集約して「この workflow は全体としてどこが弱いか」を自動要約できるようになります。

## カスタマイズ

### rubric を外部ファイルに切り出す

inline rubric は手早く書けますが、複数 example で共有したいときは `rubric_ref` で外部 YAML を参照できます。

```yaml
# workflow.yaml の判定ノード
- id: "judge"
  handler: "judge"
  params:
    rubric_ref: "rubric.yaml#default"
    output_key: "judge_result"
```

```yaml
# rubric.yaml
default:
  description: "Evaluate clarity and accuracy"
  criteria:
    - name: "clarity"
      scale: { min: 1, max: 5 }
    - name: "accuracy"
      scale: { min: 1, max: 5 }
```

### generate の provider を切替

`generate` ノードは LiteLLM 経由なので、LiteLLM が対応する provider 名に差し替えられます（`openai` / `anthropic` / `azure` / `gemini` など）。

```yaml
# workflow.yaml の generate ノード
model:
  provider: "anthropic"
  name: "claude-3-5-sonnet-20241022"
```

> `generate` ノードの provider 系統（LiteLLM）と `judge` ノードの provider 系統（`claude_agent_sdk` / `litellm`）は別レイヤーです。judge handler の provider 名として `claude_agent_sdk` と `litellm` の 2 つが選択できます。

### judge の custom system prompt

default では rubric から system prompt を自動生成しますが、独自の判定観点を持たせたい場合は `prompts.yaml#judge` に `system` キーを追加します。

```yaml
# prompts.yaml
judge:
  system: "You are a strict reviewer focused on technical accuracy."
  user: "Evaluate the following draft:\n\n{draft}"
```

`workflow.yaml` 側は変更不要です（`prompt_ref: "prompts.yaml#judge"` のまま）。

### judge のモデル差し替え

`sonnet` は Claude Agent SDK の alias です。フルモデル ID を使いたい場合は `claude-sonnet-4-xxx` 等に差し替えてください（SDK のリリースノート参照）。

## トラブルシューティング

### `JudgeHandlerConfigError: claude_agent_sdk is not installed`

```bash
uv add "yagra[judge]"
```

### `JudgeHandlerCallError: Provider call failed`

- `claude login` が完了していることを確認（`claude` CLI で `claude login` を実行）
- サブスクリプションが有効であることを確認
- ネットワーク接続を確認

### `OPENAI_API_KEY` が未設定

```bash
export OPENAI_API_KEY="your-api-key"
```

## 次のステップ

- [LLM 基本ハンドラー](../llm-basic/) — `create_llm_handler` の最小例
- [構造化出力](../llm-structured/) — `create_structured_llm_handler` で型安全な出力
- [マルチエージェント](../multi-agent/) — 複数ノードの orchestration
- [公式ドキュメント](https://shogo-hs.github.io/Yagra/)
