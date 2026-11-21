"""Run one registered operation and preserve its inputs, coverage and artifact references."""
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path

from filelock import FileLock

from seo_analysis import __version__
from seo_analysis.app.operations import OPERATIONS
from seo_analysis.core.artifacts import write_json
from seo_analysis.core.network import HttpOrigin
from seo_analysis.core.tools import ToolSpec
from seo_analysis.core.workspace import Workspace
from seo_analysis.web.crawl import CrawlConfig
from seo_analysis.storage.history import History


def timestamp():
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ToolContext:
    directory: Path
    log: Callable
    prompt: Callable | None

    def ask(self, question):
        if self.prompt is None:
            raise ValueError("This operation needs an interactive decision.")
        return self.prompt(question)


@dataclass
class ToolResult:
    run_id: str
    tool_id: str
    out_dir: str
    parameters: dict
    project: str | None
    saved_target: str | None
    started_at: str = field(default_factory=timestamp)
    finished_at: str | None = None
    status: str = "running"
    counts: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)
    artifacts: list = field(default_factory=list)
    data_egress: list = field(default_factory=list)
    schema_version: int = 1
    tool_version: str = __version__


class ToolRunner:
    def __init__(self, workspace: Workspace):
        self.workspace = workspace

    def run(self, spec: ToolSpec, request, *, project=None, saved_target=None, log=print, prompt=None):
        expected, operation = OPERATIONS[spec]
        if not isinstance(request, expected):
            raise TypeError(f"{spec.id} requires {expected.__name__}")
        history = History(self.workspace)
        selection = history.selection(project, saved_target)
        if selection and (not isinstance(request, CrawlConfig) or request.sitemap != selection["url"]
                          or request.kind != selection["kind"]):
            raise ValueError("Run input differs from the selected target.")
        directory = self.workspace.create_run_directory()
        parameters = asdict(request)
        if isinstance(request, CrawlConfig):
            parameters.pop("out_dir")
            seeds = parameters.pop("seeds")
            if seeds:
                parameters["seed_file"] = "seeds.json"
                parameters["seed_count"] = len(seeds)
                write_json(directory / "seeds.json", seeds)
        result = ToolResult(directory.name, spec.id, str(directory), parameters, project, saved_target)
        ctx = ToolContext(directory, log, prompt)
        manifest = directory / "run.json"
        with FileLock(str(directory / ".active.lock")):
            write_json(manifest, asdict(result))
            history.index(directory)
            try:
                outcome = operation(ctx, request)
                result.status = outcome.get("status", "succeeded")
                result.counts = outcome["counts"]
                result.warnings = outcome.get("warnings", [])
            except KeyboardInterrupt:
                result.status = "cancelled"
                result.warnings.append("Cancelled by user.")
            except (ValueError, RuntimeError, OSError, EOFError) as exc:
                result.status = "failed"
                result.warnings.append(str(exc))
            finally:
                if result.status == "running":
                    result.status = "failed"
                    result.warnings.append("Operation stopped unexpectedly.")
                crawl_manifest = directory / "crawl_manifest.json"
                if not result.counts and crawl_manifest.is_file():
                    result.counts = json.loads(crawl_manifest.read_text(encoding="utf-8"))["counts"]
                if spec.uses_network and (directory / "requests.json").exists():
                    result.data_egress = [{"method": "GET", "origin": asdict(HttpOrigin.from_url(request.sitemap)),
                                           "attempt_log": "requests.json"}]
                result.finished_at = timestamp()
                result.artifacts = sorted(p.name for p in directory.iterdir()
                                          if p.is_file() and p != manifest and not p.name.startswith("."))
                write_json(manifest, asdict(result))
                history.index(directory)
        return result
