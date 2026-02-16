"""Yagra パッケージの公開 API。"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from collections.abc import Mapping
from os import PathLike
from pathlib import Path
from typing import Any

from langgraph.graph.state import CompiledStateGraph

from yagra.adapters.inbound import create_workflow_studio_server
from yagra.adapters.outbound import InMemoryNodeRegistry
from yagra.application.services.template_initializer import (
    FileAlreadyExistsError,
    TemplateNotFoundError,
    initialize_from_template,
    list_templates,
)
from yagra.application.use_cases import (
    build_from_workflow_path,
    format_validation_report,
    render_workflow_visualization_html,
    validate_workflow_for_ui,
)
from yagra.domain.entities import GraphSpec
from yagra.ports.outbound import NodeHandler, NodeRegistryPort


class Yagra:
    """ワークフロー YAML から構築した LangGraph を実行するラッパー。"""

    def __init__(self, compiled_graph: CompiledStateGraph) -> None:
        """コンパイル済みグラフを保持して初期化する。

        Args:
            compiled_graph: `build_state_graph` により生成されたコンパイル済みグラフ。
        """
        self._compiled_graph = compiled_graph

    @classmethod
    def from_workflow(
        cls,
        workflow_path: str | PathLike[str],
        registry: NodeRegistryPort | Mapping[str, NodeHandler],
        bundle_root: str | PathLike[str] | None = None,
        state_schema: Any = dict,
    ) -> Yagra:
        """ワークフローファイルから `Yagra` インスタンスを生成する。

        Args:
            workflow_path: 入口となる `workflow.yaml` のパス。
            registry: handler 名を callable へ解決するレジストリ実装、または handler マッピング。
            bundle_root: 分割参照の解決に使う基準ディレクトリ。未指定時は workflow 親ディレクトリ。
            state_schema: LangGraph の状態スキーマ。既定は `dict`。

        Returns:
            コンパイル済みグラフを内包した `Yagra` インスタンス。
        """
        normalized_registry = _normalize_registry(registry)
        compiled = build_from_workflow_path(
            workflow_path=workflow_path,
            registry=normalized_registry,
            bundle_root=bundle_root,
            state_schema=state_schema,
        )
        return cls(compiled)

    @property
    def compiled_graph(self) -> CompiledStateGraph:
        """保持しているコンパイル済みグラフを返す。"""
        return self._compiled_graph

    def invoke(self, state: Mapping[str, Any]) -> dict[str, Any]:
        """初期状態を入力してグラフを実行する。

        Args:
            state: 実行開始時の状態辞書。

        Returns:
            実行後の状態辞書。

        Raises:
            TypeError: グラフ実行結果が辞書互換ではない場合。
        """
        result = self._compiled_graph.invoke(dict(state))
        if not isinstance(result, Mapping):
            raise TypeError("compiled graph returned non-mapping result")
        return dict(result)


def main() -> None:
    """Yagra の CLI エントリーポイント。"""
    parser = _build_cli_parser()
    args = parser.parse_args()

    if args.command == "init":
        exit_code = _run_init_command(args)
        raise SystemExit(exit_code)
    if args.command == "schema":
        exit_code = _run_schema_command(args)
        raise SystemExit(exit_code)
    if args.command == "validate":
        exit_code = _run_validate_command(args)
        raise SystemExit(exit_code)
    if args.command == "visualize":
        exit_code = _run_visualize_command(args)
        raise SystemExit(exit_code)
    if args.command == "studio":
        exit_code = _run_studio_command(args)
        raise SystemExit(exit_code)
    raise SystemExit(2)


def _normalize_registry(registry: NodeRegistryPort | Mapping[str, NodeHandler]) -> NodeRegistryPort:
    """Registry 引数を `NodeRegistryPort` 実装へ正規化する。

    Args:
        registry: レジストリ実装、または handler のマッピング。

    Returns:
        `NodeRegistryPort` 実装。

    Raises:
        TypeError: 受け付けない型が渡された場合。
    """
    if isinstance(registry, NodeRegistryPort):
        return registry
    if isinstance(registry, Mapping):
        return InMemoryNodeRegistry(registry)
    raise TypeError("registry must be NodeRegistryPort or mapping[str, NodeHandler]")


def _run_init_command(args: argparse.Namespace) -> int:
    """`init` サブコマンドを実行する。

    Args:
        args: 解析済みの CLI 引数。

    Returns:
        終了コード。成功時は 0。
    """
    # テンプレート一覧表示
    if args.list:
        templates = list_templates()
        if not templates:
            print("利用可能なテンプレートがありません。")
            return 1
        print("利用可能なテンプレート:")
        for template in templates:
            print(f"  - {template}")
        return 0

    # テンプレート名が指定されていない場合はエラー
    if args.template is None:
        print(
            "エラー: --template または --list のいずれかを指定してください。",
            file=sys.stderr,
        )
        return 2

    output_dir = Path(args.output).expanduser().resolve()

    try:
        initialize_from_template(
            template_name=args.template,
            output_dir=output_dir,
            force=args.force,
        )
    except TemplateNotFoundError as e:
        print(str(e), file=sys.stderr)
        return 1
    except FileAlreadyExistsError as e:
        print(str(e), file=sys.stderr)
        return 1

    print(f"テンプレート '{args.template}' から初期化しました: {output_dir}")

    # 生成されたワークフローを検証
    workflow_path = output_dir / "workflow.yaml"
    if workflow_path.exists():
        print(f"\nワークフローを検証しています: {workflow_path}")
        report = validate_workflow_for_ui(
            workflow_path=str(workflow_path),
            bundle_root=None,
        )
        if report.is_valid:
            print("✓ ワークフローは valid です。")
        else:
            print("✗ ワークフローに問題があります:", file=sys.stderr)
            print(format_validation_report(report), file=sys.stderr)
            return 1

    return 0


def _build_cli_parser() -> argparse.ArgumentParser:
    """CLI パーサーを構築する。

    Returns:
        `argparse.ArgumentParser` のインスタンス。
    """
    parser = argparse.ArgumentParser(prog="yagra")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser(
        "init",
        help="テンプレートからワークフローを初期化する",
    )
    init.add_argument(
        "--template",
        default=None,
        help="使用するテンプレート名（例: branch, loop, rag）",
    )
    init.add_argument(
        "--list",
        action="store_true",
        help="利用可能なテンプレート一覧を表示する",
    )
    init.add_argument(
        "--force",
        action="store_true",
        help="既存ファイルを上書きする",
    )
    init.add_argument(
        "--output",
        default=".",
        help="出力先ディレクトリ（デフォルト: カレントディレクトリ）",
    )

    schema = subparsers.add_parser(
        "schema",
        help="workflow YAML の JSON Schema を出力する",
    )
    schema.add_argument(
        "--output",
        default=None,
        help="出力ファイルパス（未指定時は標準出力）",
    )

    validate = subparsers.add_parser(
        "validate",
        help="workflow YAML を検証する",
    )
    validate.add_argument(
        "--workflow",
        required=True,
        help="検証対象 workflow YAML のパス",
    )
    validate.add_argument(
        "--bundle-root",
        default=None,
        help="分割参照解決の基準ディレクトリ",
    )
    validate.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="出力フォーマット (デフォルト: text)",
    )

    visualize = subparsers.add_parser(
        "visualize",
        help="workflow を Read Only HTML として可視化する",
    )
    visualize.add_argument(
        "--workflow",
        required=True,
        help="可視化対象 workflow YAML のパス",
    )
    visualize.add_argument(
        "--bundle-root",
        default=None,
        help="分割参照解決の基準ディレクトリ",
    )
    visualize.add_argument(
        "--output",
        default="workflow-visualization.html",
        help="生成する HTML ファイルパス",
    )
    visualize.add_argument(
        "--title",
        default=None,
        help="可視化ページのタイトル",
    )

    studio = subparsers.add_parser(
        "studio",
        help="workflow 編集用のローカル WebUI/API を起動する",
    )
    studio.add_argument(
        "--workflow",
        default=None,
        help="編集対象 workflow YAML のパス（未指定時は起動後にUIで選択/作成）",
    )
    studio.add_argument(
        "--bundle-root",
        default=None,
        help="分割参照解決の基準ディレクトリ",
    )
    studio.add_argument(
        "--ui-state",
        default=None,
        help="UI サイドカー JSON のパス（未指定時は <workflow>.workflow-ui.json）",
    )
    studio.add_argument(
        "--workspace-root",
        default=None,
        help=(
            "Studio が workflow を探索/作成するワークスペースルート"
            "（未指定時は workflow がカレント配下ならカレント、"
            "それ以外は workflow 親、workflow 未指定時はカレント）"
        ),
    )
    studio.add_argument(
        "--backup-dir",
        default=".yagra/backups",
        help="バックアップ格納ディレクトリ",
    )
    studio.add_argument(
        "--host",
        default="127.0.0.1",
        help="バインドホスト",
    )
    studio.add_argument(
        "--port",
        type=int,
        default=8787,
        help="バインドポート",
    )

    return parser


def _run_schema_command(args: argparse.Namespace) -> int:
    """`schema` サブコマンドを実行する。

    GraphSpec の JSON Schema を出力する。
    コーディングエージェントが正確なワークフロー YAML を生成するためのスキーマ情報を提供する。

    Args:
        args: 解析済みの CLI 引数。

    Returns:
        終了コード。成功時は 0。
    """
    schema = GraphSpec.model_json_schema()
    schema_json = json.dumps(schema, indent=2, ensure_ascii=False)

    if args.output:
        output_path = Path(args.output).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(schema_json + "\n", encoding="utf-8")
        print(f"schema exported: {output_path}")
    else:
        print(schema_json)
    return 0


def _run_validate_command(args: argparse.Namespace) -> int:
    """`validate` サブコマンドを実行する。

    ワークフロー YAML を検証し、結果を text または JSON 形式で出力する。
    JSON 形式はコーディングエージェントによるエラー修正ループに利用できる。

    Args:
        args: 解析済みの CLI 引数。

    Returns:
        終了コード。valid → 0, invalid → 1。
    """
    report = validate_workflow_for_ui(
        workflow_path=args.workflow,
        bundle_root=args.bundle_root,
    )

    if args.format == "json":
        report_dict = {
            "is_valid": report.is_valid,
            "issues": [dataclasses.asdict(issue) for issue in report.issues],
        }
        print(json.dumps(report_dict, indent=2, ensure_ascii=False))
    else:
        print(
            format_validation_report(report), file=sys.stderr if not report.is_valid else sys.stdout
        )

    return 0 if report.is_valid else 1


def _run_visualize_command(args: argparse.Namespace) -> int:
    """`visualize` サブコマンドを実行する。

    Args:
        args: 解析済みの CLI 引数。

    Returns:
        終了コード。成功時は 0。
    """
    report = validate_workflow_for_ui(
        workflow_path=args.workflow,
        bundle_root=args.bundle_root,
    )
    if not report.is_valid:
        print(format_validation_report(report), file=sys.stderr)
        return 1

    html_text = render_workflow_visualization_html(
        workflow_path=args.workflow,
        bundle_root=args.bundle_root,
        title=args.title,
    )

    output_path = Path(args.output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_text, encoding="utf-8")

    print(f"workflow visualization generated: {output_path}")
    return 0


def _run_studio_command(args: argparse.Namespace) -> int:
    """`studio` サブコマンドを実行する。

    Args:
        args: 解析済みの CLI 引数。

    Returns:
        終了コード。成功時は 0。
    """
    if args.workflow is None and args.ui_state is not None:
        print(
            "--ui-state は --workflow 指定時のみ利用できます。",
            file=sys.stderr,
        )
        return 2

    server = create_workflow_studio_server(
        workflow_path=args.workflow,
        bundle_root=args.bundle_root,
        ui_state_path=args.ui_state,
        workspace_root=args.workspace_root,
        backup_dir=args.backup_dir,
        host=args.host,
        port=args.port,
    )
    base_url = f"http://{args.host}:{args.port}"
    print(f"workflow studio started: {base_url}")
    print("press Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


__all__ = ["Yagra", "main"]
