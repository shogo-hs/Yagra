"""Defines the base schema for Yagra YAML."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class NodeSpec(BaseModel):
    """Represents a node definition in the graph."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(
        min_length=1,
        description="ノードの一意識別子。edges の source/target および start_at/end_at から参照する。英数字とアンダースコアを推奨",
        examples=["translate", "summarize", "classify"],
    )
    handler: str = Field(
        min_length=1,
        description="このノードで実行するハンドラー名。組み込みハンドラー: 'llm'（テキスト出力）, 'structured_llm'（Pydantic 構造化出力）, 'streaming_llm'（ストリーミング出力）。カスタムハンドラーは Registry に登録した名前を指定する",
        examples=["llm", "structured_llm", "streaming_llm", "my_custom_handler"],
    )
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="ハンドラーに渡すパラメータ辞書。llm ハンドラー: prompt_ref または prompt（必須）, model（必須）, output_key（省略時は 'output'）。structured_llm ハンドラー: 上記に加え schema_yaml（'name: str\\nage: int' 形式）。streaming_llm ハンドラー: 上記に加え stream（bool, デフォルト true）",
        examples=[
            {
                "prompt_ref": "prompts/translate.txt",
                "model": "gpt-4o-mini",
                "output_key": "translation",
            },
            {
                "prompt": {"role": "user", "content": "要約してください: {text}"},
                "model": "gpt-4o-mini",
            },
        ],
    )


class EdgeSpec(BaseModel):
    """Represents an edge definition for transitions between nodes."""

    model_config = ConfigDict(extra="forbid")

    source: str = Field(
        min_length=1,
        description="遷移元ノードの id。nodes リストに存在するノード ID を指定する",
        examples=["translate", "classify"],
    )
    target: str = Field(
        min_length=1,
        description="遷移先ノードの id。nodes リストに存在するノード ID を指定する。条件分岐なし（condition なし）の場合は必ずこのノードへ遷移する",
        examples=["summarize", "END"],
    )
    condition: str | None = Field(
        default=None,
        description="条件分岐の条件式。ノードの state['__next__'] の値と比較する文字列、または条件関数名。省略時は無条件遷移",
        examples=["approve", "reject", None],
    )


class GraphSpec(BaseModel):
    """Represents the complete Yagra YAML definition."""

    model_config = ConfigDict(extra="forbid")

    version: str = Field(
        min_length=1,
        description="YAML スキーマのバージョン。現在は '1.0' を指定する",
        examples=["1.0"],
    )
    start_at: str = Field(
        min_length=1,
        description="ワークフロー開始時に最初に実行するノードの id。nodes リストのいずれかの id を指定する",
        examples=["translate", "input_node"],
    )
    end_at: list[str] = Field(
        min_length=1,
        description="ワークフロー終了ノードの id リスト。これらのノードが完了するとワークフローが終了する。複数指定可能",
        examples=[["translate"], ["approve", "reject"]],
    )
    nodes: list[NodeSpec] = Field(
        min_length=1,
        description="ワークフローを構成するノードの定義リスト。各ノードは id, handler, params を持つ",
        examples=[
            [
                {
                    "id": "translate",
                    "handler": "llm",
                    "params": {"prompt_ref": "prompts/translate.txt", "model": "gpt-4o-mini"},
                }
            ]
        ],
    )
    edges: list[EdgeSpec] = Field(
        min_length=0,
        description="ノード間の遷移定義リスト。source から target へのエッジを列挙する。条件分岐は condition フィールドで指定する",
        examples=[
            [
                {"source": "classify", "target": "approve", "condition": "approved"},
                {"source": "classify", "target": "reject", "condition": "rejected"},
            ]
        ],
    )
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="ワークフローレベルのグローバルパラメータ。現在は使用されていないが将来の拡張のために予約されている",
        examples=[{}],
    )
    interrupt_before: list[str] = Field(
        default_factory=list,
        description="指定したノードの実行前に処理を中断するノード ID リスト。HITL（Human-in-the-Loop）で人間のレビュー・承認を挟むために使用する。`Yagra.resume()` で再開できる",
        examples=[["review_node"], []],
    )
    interrupt_after: list[str] = Field(
        default_factory=list,
        description="指定したノードの実行後に処理を中断するノード ID リスト。HITL（Human-in-the-Loop）で人間が出力を確認・修正するために使用する。`Yagra.resume()` で再開できる",
        examples=[["generate_node"], []],
    )
