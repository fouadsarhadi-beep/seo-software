"""Shared CLI execution, export and run summaries."""

from dataclasses import asdict
import json
from pathlib import Path
import sys

from seo_analysis.app.runner import ToolRunner
from seo_analysis.core.artifacts import publish_files


def execute(args, spec, request, prompt=None, export=None, export_names=None):
    workspace = args.workspace
    json_mode = getattr(args, "json", False)
    log = lambda message: print(message, file=sys.stderr)
    result = ToolRunner(workspace).run(spec, request, log=log, prompt=None if json_mode else prompt,
                                       project=getattr(args, "project", None),
                                       saved_target=getattr(args, "target", None))
    directory = Path(result.out_dir)
    if export and result.status in {"succeeded", "partial"}:
        names = result.artifacts if export_names is None else export_names
        destination = publish_files(directory, export, names, include_observations=spec.uses_network)
        log(f"Export directory: {destination}")
    return print_run_result(result, json_mode)


def print_run_result(result, json_mode):
    if json_mode:
        summary = asdict(result)
        summary["warning_count"] = len(result.warnings)
        summary["warnings"] = result.warnings[:20]
        print(json.dumps(summary, ensure_ascii=False))
    else:
        print(f"{result.tool_id} {result.status} | {result.run_id}")
        print(f"Run directory: {result.out_dir}")
        print("Coverage:", json.dumps(result.counts, ensure_ascii=False))
        for warning in result.warnings[:20]:
            print(warning)
        if len(result.warnings) > 20:
            print("See run.json for all warnings.")
    return {"succeeded": 0, "partial": 3, "cancelled": 130}.get(result.status, 2)
