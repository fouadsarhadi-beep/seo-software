"""Offline agent operations accept existing workspace run IDs only."""
from pathlib import Path
from uuid import UUID

from seo_analysis.analysis.checks import CHECKS, CompareInput, SnapshotInput
from seo_analysis.app.operations import AnalysisInput
from seo_analysis.app.runner import ToolRunner
from seo_analysis.core import tools
from seo_analysis.storage.history import History


def run_snapshot_tool(workspace, tool_id, run_id, *, previous=None, check="all"):
    history = History(workspace)
    def snapshot(rid):
        if not isinstance(rid, str) or UUID(rid).hex != rid:
            raise ValueError("A workspace run ID is required.")
        item = history.show(rid)
        path = Path(item["directory"])
        if (path.resolve() != workspace.runs_dir.resolve() / rid
                or "snapshot.jsonl" not in item["manifest"]["artifacts"]
                or any((path / name).is_symlink() for name in
                       ("snapshot.jsonl", "crawl_manifest.json", "persian_variants.json"))):
            raise ValueError("Select a managed crawl snapshot.")
        return str(path)
    current = snapshot(run_id)
    if tool_id == tools.CHECK.id and previous is None and check in (*CHECKS, "all"):
        spec, request = tools.CHECK, SnapshotInput(current, check)
    elif tool_id == tools.COMPARE.id and previous and check == "all":
        spec, request = tools.COMPARE, CompareInput(snapshot(previous), current)
    elif tool_id == tools.ANALYZE.id and previous is None and check == "all":
        spec, request = tools.ANALYZE, AnalysisInput(current)
    else:
        raise ValueError("Unsupported offline tool or arguments.")
    return ToolRunner(workspace).run(spec, request, log=lambda _: None)
