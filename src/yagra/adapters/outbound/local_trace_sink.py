"""Local file system implementation of TraceSinkPort (G-14)."""

from __future__ import annotations

import json
from pathlib import Path

from yagra.domain.entities.trace import WorkflowRunTrace
from yagra.ports.outbound.trace_sink import TraceSinkError, TraceSinkPort


class LocalTraceSink(TraceSinkPort):
    """Writes WorkflowRunTrace as a JSON file to a local directory.

    File naming convention:
        {workflow_name}_{started_at:%Y%m%dT%H%M%S}_{run_id[:8]}.json

    Directory structure:
        {base_dir}/                          # default: .yagra/traces/
        └── {workflow_name}/
            └── {workflow_name}_{ts}_{id8}.json

    Args:
        base_dir: Root directory for trace output.
            Defaults to Path(".yagra/traces") relative to cwd.
        indent: JSON indentation spaces. Default 2. Set to None for compact output.

    Examples:
        .yagra/traces/
        └── translate/
            └── translate_20260220T143022_a1b2c3d4.json
    """

    def __init__(
        self,
        base_dir: str | Path = Path(".yagra/traces"),
        indent: int | None = 2,
    ) -> None:
        """Initializes the local trace sink.

        Args:
            base_dir: Root directory for trace output files.
            indent: JSON indentation for human readability. None for compact.
        """
        self._base_dir = Path(base_dir)
        self._indent = indent

    def write(self, trace: WorkflowRunTrace) -> str:
        """Writes the trace to a JSON file and returns the file path.

        Args:
            trace: The completed workflow run trace.

        Returns:
            Absolute path to the written JSON file.

        Raises:
            TraceSinkError: If directory creation or file writing fails.
        """
        workflow_dir = self._base_dir / trace.workflow_name
        try:
            workflow_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise TraceSinkError(
                f"Failed to create trace directory '{workflow_dir}': {exc}"
            ) from exc

        ts = trace.started_at.strftime("%Y%m%dT%H%M%S")
        run_id_short = str(trace.run_id).replace("-", "")[:8]
        filename = f"{trace.workflow_name}_{ts}_{run_id_short}.json"
        file_path = workflow_dir / filename

        try:
            # model_dump(mode="json") converts UUID/datetime to JSON-serializable types
            payload = trace.model_dump(mode="json")
            file_path.write_text(
                json.dumps(payload, indent=self._indent, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            raise TraceSinkError(f"Failed to write trace file '{file_path}': {exc}") from exc

        return str(file_path.resolve())

    def flush(self) -> None:
        """No-op for synchronous file writes.

        Returns:
            None
        """
