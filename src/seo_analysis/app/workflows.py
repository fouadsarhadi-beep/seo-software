"""Execute saved audit settings from the workbench or a scheduler."""

from uuid import UUID

from filelock import FileLock, Timeout

from seo_analysis.app.runner import ToolRunner
from seo_analysis.core import tools
from seo_analysis.web.crawl import CrawlConfig


def run_saved_audit(workspace, saved, *, allow_local=False, log=print, cancel=None):
    workflow_id = saved["id"]
    if UUID(workflow_id).hex != workflow_id:
        raise ValueError("Invalid audit workflow ID.")
    config = CrawlConfig(saved["url"], "", source=saved["url"], kind=saved["kind"], limit=saved["page_limit"],
                         link_crawl=bool(saved["link_crawl"]), allow_local=allow_local)
    lock = FileLock(str(workspace.data_dir / f".audit-workflow-{workflow_id}.lock"), timeout=0)
    try:
        lock.acquire()
    except Timeout as exc:
        raise ValueError("This audit workflow is already running.") from exc
    try:
        return ToolRunner(workspace).run(tools.AUDIT, config, project=saved["project"], saved_target=saved["target"],
                                         log=log, cancel=cancel, workflow={"id": workflow_id, "name": saved["name"]})
    finally:
        lock.release()
