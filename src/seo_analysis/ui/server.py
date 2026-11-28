"""Loopback workbench over the same application runner as the CLI."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from functools import partial
import json
import logging
from pathlib import Path, PureWindowsPath
from secrets import compare_digest, token_urlsafe
import sqlite3
from threading import Event, Lock
from urllib.parse import parse_qs, unquote, urlencode
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, RedirectResponse
from filelock import Timeout
from jinja2 import Environment, PackageLoader, select_autoescape
from starlette.concurrency import run_in_threadpool

from seo_analysis.analysis import review
from seo_analysis.analysis.browserqa import BrowserQAInput
from seo_analysis.analysis.checks import CHECKS
from seo_analysis.analysis.siteqa import SiteQAInput
from seo_analysis.app.agent import run_snapshot_tool
from seo_analysis.app.runner import ToolRunner
from seo_analysis.app.workflows import run_saved_audit
from seo_analysis.core import tools
from seo_analysis.core.network import HttpOrigin
from seo_analysis.reporting.workbook import WorkbookInput
from seo_analysis.research.intelligence import ResearchInput
from seo_analysis.research.sources import FeedInput, redact_url
from seo_analysis.storage.history import History, workspace_access_error
from seo_analysis.storage.removal import RemovalConflict, pending_removals, remove_saved_data, retry_removals
from seo_analysis.ui.uploads import export_form, export_input, import_upload
from seo_analysis.web.crawl import CrawlConfig

LOG = logging.getLogger("uvicorn.error")
DELETE_SCOPES = {
    "audits": ("Delete all audits", "Includes archived audits, their reports and page evidence. Reports from other tools may lose links to this evidence."),
    "runs": ("Delete all runs", "Removes saved audits, reports, imported datasets, research and other runs, including archived runs."),
    "workspace": ("Clear workspace data", "Removes saved runs, projects, targets, workflows, review decisions, local connection selections and publication records."),
}

FINDING_LABELS = {
    "content.extraction": "Text extraction", "content.overlap": "Content overlap",
    "seo.redirect": "URL redirects", "seo.multiple-h1": "Multiple H1 headings",
    "seo.noindex": "Page marked noindex", "seo.missing-title": "Missing title",
    "seo.missing-meta": "Missing meta description", "seo.missing-h1": "Missing H1 heading",
    "seo.canonical": "Canonical URL", "crawl.fetch_error": "Fetch failed",
    "crawl.robots_disallowed": "Blocked by robots.txt", "crawl.non_html": "Response was not HTML",
    "crawl.redirect_blocked_external": "Redirect leaves the selected origin",
}
CHECK_LABELS = {"technical": "Technical SEO", "sitemap": "Sitemap coverage", "links": "Internal links",
                "broken-links": "Broken links", "canonicals": "Canonicals", "schema": "Structured data",
                "hreflang": "Hreflang", "assets": "Assets"}
OBSERVATION_LABELS = {"unobserved": "Unknown (target not observed)", "observed-http-error": "Observed HTTP error"}
DECISION_LABELS = {"merge_a_into_b": "Merge A into B", "merge_b_into_a": "Merge B into A",
                   "canonical_a_to_b": "Canonical A to B", "canonical_b_to_a": "Canonical B to A",
                   "differentiate": "Differentiate the pages", "ignore": "No action needed"}
REVERSED_DECISIONS = {"merge_a_into_b": "merge_b_into_a", "merge_b_into_a": "merge_a_into_b",
                      "canonical_a_to_b": "canonical_b_to_a", "canonical_b_to_a": "canonical_a_to_b"}
REPORT_PROVIDERS = {"gsc": "Search Console", "ga4": "Google Analytics 4"}
CONNECTED_REPORT_TOOLS = {tools.SEARCH_ANALYTICS.id: "gsc", tools.GA4_LANDING_PAGES.id: "ga4"}
RESEARCH_SOURCE_TOOLS = {tools.PUBLIC_FEED.id: "community", tools.BRAVE_SEARCH.id: "serp"}
RESEARCH_DATASETS = {"serp": "Search results (SERP)", "keywords": "Keywords", "gsc": "Search Console",
                     "backlinks": "Backlinks", "community": "Community"}
RESEARCH_SECTIONS = {"keywords": "Keywords", "competitors": "Competitor gaps", "serp_overlap": "SERP overlap",
                     "rank_history": "Rank samples", "keyword_clusters": "Keyword clusters",
                     "content_briefs": "Content briefs", "backlinks": "Backlinks",
                     "questions": "Community topics"}
# Task names replace internal tool identifiers wherever an operator reads a run.
TOOL_LABELS = {
    "seo.audit": "Website audit", "web.crawl": "Crawl", "seo.check": "Technical checks",
    "seo.compare": "Audit comparison", "seo.analyze-snapshot": "Content analysis",
    "content.review-pairs": "Content review", "content.calibrate": "Calibration",
    "content.spelling-variants": "Spelling variants", "research.import": "Data import",
    "research.opportunities": "Research report", "research.feed": "Feed import",
    "research.brave-search": "Brave search sample", "report.workbook": "Excel report",
    "report.export-dataset": "Dataset export", "quality.build": "Site QA",
    "quality.browser": "Browser QA", "performance.lighthouse": "Lighthouse report",
    "performance.lighthouse-run": "Lighthouse run", "google.search-analytics": "Search Console pull",
    "google.inspect-url": "URL inspection", "google.pagespeed": "PageSpeed test",
    "google.crux": "CrUX report", "google.publish-sheets": "Sheets publication",
    "cms.wordpress-inventory": "WordPress inventory", "system.doctor": "System check",
}


def matches_query(term, *values):
    return any(term in unquote(str(value)).casefold() for value in values)


def full_local_path(path):
    return Path(path).is_absolute() and not path.startswith(("//", "\\\\"))


@dataclass
class Job:
    status: str = "queued"
    detail: str = ""
    run_id: str = ""
    cancel: Event = field(default_factory=Event)


def create_app(workspace, port=8765):
    host = f"127.0.0.1:{port}"
    origin = "http://" + host
    token = token_urlsafe()
    history = History(workspace)
    templates = Environment(loader=PackageLoader("seo_analysis.ui", "."), autoescape=select_autoescape())
    templates.policies["json.dumps_kwargs"] = {"sort_keys": True, "ensure_ascii": False}
    pool = ThreadPoolExecutor(max_workers=1)
    jobs = {}
    guard = Lock()

    @asynccontextmanager
    async def lifespan(app):
        yield
        for job in jobs.values():
            job.cancel.set()
        pool.shutdown(wait=True)

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)

    @app.middleware("http")
    async def boundary(request, next_handler):
        if request.headers.get("host") != host:
            return PlainTextResponse("Unknown host", status_code=403)
        if request.method == "POST" and request.headers.get("origin") != origin:
            return PlainTextResponse("Unknown origin", status_code=403)
        response = await next_handler(request)
        response.headers.update({"X-Content-Type-Options": "nosniff", "Cache-Control": "no-store",
                                 "Content-Security-Policy": "default-src 'none'; img-src 'self'; style-src 'self' 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'"})
        return response

    def verify_token(value):
        if not isinstance(value, str) or not compare_digest(value.encode(), token.encode()):
            raise HTTPException(403)

    async def form(request, *, repeated=()):
        if request.headers.get("content-type", "").split(";")[0] != "application/x-www-form-urlencoded":
            raise HTTPException(415)
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 8192:
                raise HTTPException(413)
        fields = parse_qs(body.decode())
        verify_token(fields.pop("token", [""])[0])
        return {name: values if name in repeated else values[0] for name, values in fields.items()}

    def nav_projects():
        try:
            return history.projects()
        except (sqlite3.Error, OSError):
            return []

    def render(view, *, status_code=200, **fields):
        return HTMLResponse(templates.get_template("workbench.html").render(
            view=view, token=token, nav_projects=nav_projects(), tool_labels=TOOL_LABELS, **fields),
            status_code=status_code)

    async def storage_error(request: Request, exc: Exception):
        LOG.error("Workspace storage error for %s %s", request.method, request.url.path, exc_info=exc)
        if workspace_access_error(exc):
            message = ("The workbench cannot write to its saved data. On Windows, close this server and open "
                       "Start SEO Workbench.cmd from a writable checkout to use the project workspace.")
        elif isinstance(exc, Timeout) or getattr(exc, "sqlite_errorcode", 0) & 0xff in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED):
            message = "The workspace is busy. Wait for the other operation to finish and try again."
        else:
            message = "The workbench could not access its saved data. Check the launcher log or server console for details."
        return render("storage_error", message=message, path=workspace.data_dir, status_code=503)

    app.add_exception_handler(sqlite3.Error, storage_error)
    app.add_exception_handler(PermissionError, storage_error)
    app.add_exception_handler(Timeout, storage_error)

    def detail(rid):
        try:
            return history.show(rid)
        except ValueError as exc:
            raise HTTPException(404, "Unknown run") from exc

    def artifact_path(data, name):
        path = Path(data["directory"]) / name
        run_dir = workspace.runs_dir.resolve() / data["manifest"]["run_id"]
        if (name not in data["manifest"]["artifacts"] or path.is_symlink()
                or path.parent.resolve() != run_dir or not path.is_file()):
            raise HTTPException(404, "Run file unavailable")
        return path

    def source_run(run_id, stored_path):
        if not run_id and stored_path:
            path = Path(stored_path)
            if path.parent.resolve() == workspace.runs_dir.resolve():
                run_id = path.name
        if run_id:
            try:
                return history.show(run_id)
            except ValueError:
                return None

    def read_observation(data, row):
        path = Path(data["directory"]) / row["path"]
        if not path.resolve().is_relative_to(workspace.runs_dir.resolve() / data["manifest"]["run_id"]) or not path.is_file():
            raise HTTPException(404, "Page evidence unavailable")
        return json.loads(path.read_text(encoding="utf-8"))

    @app.get("/")
    def home(project: str = ""):
        projects = history.projects()
        selected = next((item for item in projects if item["name"] == project), None)
        if selected is None and projects:
            selected = projects[0]
        recent = history.list_runs(limit=12, archived=False)
        project_runs = [item for item in recent if selected and item["project"] == selected["name"]][:5]
        ad_hoc_runs = [item for item in recent if not item["project"]][:5]
        latest = None
        if project_runs:
            try:
                latest = detail(project_runs[0]["id"])["manifest"]
            except (HTTPException, OSError, ValueError):
                latest = None
        return render("overview", projects=projects, selected=selected,
                      targets=history.targets(selected["name"]) if selected else [],
                      workflows=history.audit_workflows(selected["name"]) if selected else [],
                      project_runs=project_runs, ad_hoc_runs=ad_hoc_runs, latest=latest)

    @app.get("/audit/new")
    def audit_new(project: str = ""):
        projects = history.projects()
        chosen = next((item["name"] for item in projects if item["name"] == project), "")
        selected = next((item for item in projects if item["name"] == chosen), None)
        return render("audit_new", projects=projects, chosen=chosen, selected=selected)

    @app.get("/tools/search-traffic")
    def search_traffic():
        return render("search_traffic")

    @app.get("/history")
    def runs(page: int = 1, archived: bool = False):
        page = max(1, page)
        records = history.list_runs(limit=31, offset=(page - 1) * 30, archived=archived)
        return render("history", runs=records[:30], page=page, more=len(records) > 30, archived=archived)

    @app.get("/history/data")
    def saved_data(updated: bool = False):
        return render("saved_data", pending=pending_removals(history), updated=updated, scopes=DELETE_SCOPES,
                      path=workspace.data_dir)

    @app.get("/history/data/{scope}")
    def confirm_clear(scope: str):
        if scope not in DELETE_SCOPES:
            raise HTTPException(404, "Unknown deletion option.")
        title, message = DELETE_SCOPES[scope]
        return render("confirm_delete", title=title, message=message, back="/history/data", path=workspace.data_dir)

    @app.get("/runs/{rid}/delete")
    def confirm_run_delete(rid: str):
        item = detail(rid)["manifest"]
        return render("confirm_delete", title="Delete saved run", run=item, back="/history",
                      message="Deletes this run, its reports and page evidence. Other runs may lose links to this evidence.")

    async def delete_saved(request, scope, *, run_id=None):
        fields = await form(request)
        if fields.get("confirm") != "delete":
            raise HTTPException(400, "Confirm the permanent deletion first.")
        with guard:
            if any(job.status in ("queued", "running") for job in jobs.values()):
                raise HTTPException(409, "Wait for the active audit to finish before deleting data.")
        try:
            _, pending = await run_in_threadpool(remove_saved_data, history, scope, run_id=run_id)
        except RemovalConflict as exc:
            raise HTTPException(409, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc
        if scope == "single" and not pending:
            return RedirectResponse("/history", 303)
        return RedirectResponse("/history/data?updated=true", 303)

    @app.post("/history/data/retry")
    async def retry_data_cleanup(request: Request):
        await form(request)
        await run_in_threadpool(retry_removals, history)
        return RedirectResponse("/history/data?updated=true", 303)

    @app.post("/history/data/{scope}")
    async def delete_data(scope: str, request: Request):
        if scope not in DELETE_SCOPES:
            raise HTTPException(404, "Unknown deletion option.")
        return await delete_saved(request, scope)

    @app.post("/runs/{rid}/delete")
    async def delete_run(rid: str, request: Request):
        return await delete_saved(request, "single", run_id=rid)

    @app.get("/compare")
    def comparison_form():
        return render("compare", snapshots=history.runs_with_artifact("snapshot.jsonl"))

    @app.post("/compare")
    async def run_comparison(request: Request):
        fields = await form(request)
        before, after = fields.get("before", ""), fields.get("after", "")
        if not before or not after or before == after:
            raise HTTPException(400, "Choose two different saved audits or crawls.")
        for rid in (before, after):
            artifact_path(detail(rid), "snapshot.jsonl")
        try:
            compared = await run_in_threadpool(run_snapshot_tool, workspace, tools.COMPARE.id, after, previous=before)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        return RedirectResponse("/runs/" + compared.run_id, 303)

    @app.post("/runs/{rid}/archive")
    async def archive_run(rid: str, request: Request):
        fields = await form(request)
        archived = fields.get("action")
        if archived not in ("archive", "restore"):
            raise HTTPException(400, "Choose archive or restore.")
        try:
            history.set_archived(rid, archived == "archive")
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc
        return RedirectResponse("/history?archived=true" if archived == "restore" else "/history", 303)

    @app.get("/projects")
    def projects(project: str | None = None):
        if project is None:
            return render("projects", projects=history.projects())
        try:
            history.selection(project, None)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc
        return render("project", project=project, targets=history.targets(project), workflows=history.audit_workflows(project))

    @app.post("/projects")
    async def create_project(request: Request):
        f = await form(request)
        try:
            history.add_project(f.get("name", ""), website=f.get("url", ""))
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        return RedirectResponse("/projects", 303)

    @app.post("/targets")
    async def create_target(request: Request):
        f = await form(request)
        project = f.get("project", "")
        try:
            history.add_target(project, f.get("name", ""), "website", f.get("url", ""))
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        return RedirectResponse("/projects?" + urlencode({"project": project}), 303)

    def launch(job, operation):
        def progress(message):
            job.detail = str(message)[:500]
        try:
            job.status = "running"
            result = operation(log=progress, cancel=job.cancel)
            job.run_id, job.status = result.run_id, result.status
        except Exception as exc:
            job.status, job.detail = "failed", str(exc)

    def start_audit(operation):
        with guard:
            if any(j.status in ("queued", "running") for j in jobs.values()):
                raise HTTPException(409, "An audit is already running.")
            if len(jobs) >= 50:
                jobs.pop(next(iter(jobs)))
            jid = uuid4().hex
            jobs[jid] = Job()
            pool.submit(launch, jobs[jid], operation)
        return RedirectResponse("/jobs/" + jid, 303)

    def page_limit(value):
        try:
            limit = int(value)
            if 1 <= limit <= 500:
                return limit
        except ValueError:
            pass
        raise ValueError("Choose between 1 and 500 pages.")

    def workflow_detail(workflow_id):
        try:
            return history.audit_workflow(workflow_id)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc

    def workflow_form(project, values, *, workflow_id=None, error=""):
        try:
            history.selection(project, None)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc
        return render("workflow_form", project=project, targets=history.targets(project), values=values,
                      workflow_id=workflow_id, error=error)

    @app.get("/workflows/new")
    def new_workflow(project: str):
        return workflow_form(project, {})

    @app.get("/workflows/{workflow_id}/edit")
    def edit_workflow(workflow_id: str):
        saved = workflow_detail(workflow_id)
        return workflow_form(saved["project"], saved, workflow_id=workflow_id)

    async def save_workflow(request, workflow_id=None):
        fields = await form(request)
        project = workflow_detail(workflow_id)["project"] if workflow_id else fields.get("project", "")
        values = dict(name=fields.get("name", ""), target=fields.get("target", ""),
                      page_limit=fields.get("page_limit", "100"), link_crawl=fields.get("links") == "on")
        try:
            history.save_audit_workflow(workflow_id or uuid4().hex, project, values["target"], values["name"],
                                        page_limit(values["page_limit"]), values["link_crawl"], editing=workflow_id is not None)
        except ValueError as exc:
            return workflow_form(project, values, workflow_id=workflow_id, error=str(exc))
        return RedirectResponse("/projects?" + urlencode({"project": project}), 303)

    @app.post("/workflows")
    async def create_workflow(request: Request):
        return await save_workflow(request)

    @app.post("/workflows/{workflow_id}/edit")
    async def update_workflow(workflow_id: str, request: Request):
        return await save_workflow(request, workflow_id)

    @app.post("/workflows/{workflow_id}/run")
    async def run_workflow(workflow_id: str, request: Request):
        fields = await form(request)
        saved = workflow_detail(workflow_id)
        return start_audit(partial(run_saved_audit, workspace, saved, allow_local=fields.get("local") == "on"))

    @app.post("/audit")
    async def audit(request: Request):
        f = await form(request)
        url, project, saved = f.get("url", ""), f.get("project") or None, f.get("target") or None
        try:
            selection = history.selection(project, saved)
            if selection:
                url = selection["url"]
            HttpOrigin.from_url(url)
            pages = page_limit(f.get("pages", 100))
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        cfg = CrawlConfig(url, "", source=url, kind=selection["kind"] if selection else "website",
                          limit=pages, link_crawl=f.get("links") == "on", allow_local=f.get("local") == "on")
        return start_audit(partial(ToolRunner(workspace).run, tools.AUDIT, cfg, project=project, saved_target=saved))

    @app.get("/jobs/{jid}")
    def status(jid: str):
        job = jobs.get(jid)
        if job is None:
            raise HTTPException(404)
        if job.run_id:
            return RedirectResponse("/runs/" + job.run_id, 303)
        return render("job", job=job, jid=jid)

    @app.post("/jobs/{jid}/cancel")
    async def cancel(jid: str, request: Request):
        await form(request)
        if jid not in jobs:
            raise HTTPException(404)
        jobs[jid].cancel.set()
        return RedirectResponse("/jobs/" + jid, 303)

    @app.post("/runs/{rid}/checks")
    async def run_checks(rid: str, request: Request):
        check = (await form(request)).get("check", "all")
        if check not in ("all", *CHECKS):
            raise HTTPException(400, "Choose a supported technical check.")
        artifact_path(detail(rid), "snapshot.jsonl")
        try:
            checked = await run_in_threadpool(run_snapshot_tool, workspace, tools.CHECK.id, rid, check=check)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        return RedirectResponse("/runs/" + checked.run_id, 303)

    def dataset_kind(run, sources):
        if run["tool_id"] == tools.IMPORT.id:
            return run["parameters"].get("kind")
        return sources.get(run["tool_id"])

    def saved_datasets(kinds, sources):
        for run in history.runs_with_artifact("dataset.json"):
            tool = run["tool_id"]
            kind = dataset_kind(run, sources)
            if kind not in kinds:
                continue
            params = run["parameters"]
            item = dict(id=run["run_id"], kind=kind, status=run["status"], rows=run["counts"].get("rows", 0))
            if tool == tools.IMPORT.id:
                filename = params.get("source_filename") or PureWindowsPath(params.get("file", "")).name
                yield params | item | {"name": filename}
            elif tool in CONNECTED_REPORT_TOOLS:
                source = run["project"] or "Workspace connection"
                name = f"{REPORT_PROVIDERS[kind]} API · {source}"
                if params.get("origin"):
                    name += " · " + params["origin"]
                yield item | dict(name=name, observed=params.get("end", ""), period_start=params.get("start", ""))
            elif tool == tools.PUBLIC_FEED.id:
                yield item | dict(name=params["url"], provider="Public RSS/Atom", observed=run["finished_at"][:10])
            elif tool == tools.BRAVE_SEARCH.id:
                yield item | dict(name=params["query"], provider="Brave Search", observed=run["finished_at"][:10],
                                  locale=f"{params['language']}-{params['country'].upper()}")

    def report_form(rid, selected, error=""):
        data = detail(rid)
        artifact_path(data, "snapshot.jsonl")
        datasets = {kind: [] for kind in REPORT_PROVIDERS}
        for item in saved_datasets(datasets, CONNECTED_REPORT_TOOLS):
            datasets[item["kind"]].append(item)
        return render("report_form", rid=rid, crawl=data["manifest"], datasets=datasets, selected=selected,
                      providers=REPORT_PROVIDERS, error=error)

    @app.get("/runs/{rid}/report")
    def report_options(rid: str, gsc: str = "", ga4: str = ""):
        return report_form(rid, {"gsc": gsc, "ga4": ga4})

    @app.post("/runs/{rid}/report/import/{kind}")
    async def report_import(rid: str, kind: str, request: Request):
        if kind not in REPORT_PROVIDERS:
            raise HTTPException(404)
        data = detail(rid)
        artifact_path(data, "snapshot.jsonl")
        async with export_form(request) as fields:
            verify_token(fields.get("token"))
            selected = {key: fields.get(key, "") for key in REPORT_PROVIDERS}
            try:
                spec = export_input(fields, kind, REPORT_PROVIDERS[kind])
                imported = await run_in_threadpool(import_upload, workspace, fields.get("file"), spec,
                                                   project=data["manifest"]["project"])
            except ValueError as exc:
                return report_form(rid, selected, str(exc))
        if "dataset.json" not in imported.artifacts:
            return report_form(rid, selected, imported.warnings[0] if imported.warnings else "The import did not complete.")
        selected[kind] = imported.run_id
        return RedirectResponse(f"/runs/{rid}/report?" + urlencode(selected), 303)

    @app.post("/runs/{rid}/report")
    async def create_report(rid: str, request: Request):
        fields = await form(request)
        selected = {kind: fields.get(kind, "") for kind in REPORT_PROVIDERS}
        data = detail(rid)
        crawl = artifact_path(data, "snapshot.jsonl").parent
        datasets = []
        for kind, dataset_id in selected.items():
            if dataset_id:
                item = detail(dataset_id)
                manifest = item["manifest"]
                if dataset_kind(manifest, CONNECTED_REPORT_TOOLS) != kind:
                    raise HTTPException(400, f"Choose a saved {REPORT_PROVIDERS[kind]} dataset.")
                datasets.append(str(artifact_path(item, "dataset.json").parent))
        if not datasets:
            return report_form(rid, selected, "Choose at least one saved export.")
        result = await run_in_threadpool(ToolRunner(workspace).run, tools.WORKBOOK, WorkbookInput(str(crawl), tuple(datasets)),
                                         project=data["manifest"]["project"], log=lambda _: None)
        return RedirectResponse("/runs/" + result.run_id, 303)

    @app.get("/tools")
    def tool_catalogue():
        return render("tools")

    @app.get("/tools/site-qa")
    def site_qa_options():
        return render("site_qa_form", values={})

    @app.post("/tools/site-qa")
    async def site_qa_run(request: Request):
        fields = await form(request)
        values = {name: fields.get(name, "").strip().removeprefix('"').removesuffix('"')
                  for name in ("directory", "lighthouse", "axe", "access_log", "baseline", "screenshot")}
        if not values["directory"] or any(path and not full_local_path(path) for path in values.values()):
            return render("site_qa_form", values=values, error="Enter full local paths for the build folder and any selected files.")
        if bool(values["baseline"]) != bool(values["screenshot"]):
            return render("site_qa_form", values=values, error="Enter both screenshot paths to compare PNG files.")
        result = await run_in_threadpool(ToolRunner(workspace).run, tools.SITE_QA, SiteQAInput(**values), log=lambda _: None)
        return RedirectResponse("/runs/" + result.run_id, 303)

    def browser_capture_form(values, error=""):
        baselines = [run for run in history.runs_with_artifact("browser-qa.json")
                     if run["tool_id"] == tools.BROWSER_QA.id and "screenshot.png" in run["artifacts"]]
        return render("browser_qa_form", values=values, baselines=baselines, error=error)

    @app.get("/tools/browser-qa")
    def browser_capture_options(baseline: str = ""):
        if not baseline:
            return browser_capture_form({})
        data = detail(baseline)
        run = data["manifest"]
        if run["tool_id"] != tools.BROWSER_QA.id:
            raise HTTPException(400, "Choose a saved browser capture.")
        artifact_path(data, "browser-qa.json")
        artifact_path(data, "screenshot.png")
        params = run["parameters"]
        return browser_capture_form({key: params[key] for key in ("directory", "page", "width", "height")} |
                                    {"baseline": baseline})

    @app.post("/tools/browser-qa")
    async def run_browser_capture(request: Request):
        fields = await form(request)
        values = {key: fields.get(key, default).strip() for key, default in
                  (("directory", ""), ("page", "/"), ("width", "1365"), ("height", "768"), ("baseline", ""))}
        directory = values["directory"].removeprefix('"').removesuffix('"')
        if not full_local_path(directory):
            return browser_capture_form(values, "Enter the full path to the local build folder.")
        try:
            width, height = int(values["width"]), int(values["height"])
        except ValueError:
            return browser_capture_form(values, "Enter the viewport dimensions in whole pixels.")
        baseline_id = values["baseline"]
        baseline = ""
        if baseline_id:
            data = detail(baseline_id)
            run = data["manifest"]
            if run["tool_id"] != tools.BROWSER_QA.id:
                raise HTTPException(400, "Choose a saved browser capture.")
            artifact_path(data, "browser-qa.json")
            params = run["parameters"]
            if (params["page"], params["width"], params["height"]) != (values["page"], width, height):
                return browser_capture_form(values, "Use the same page path and viewport as the approved baseline.")
            baseline = str(artifact_path(data, "screenshot.png"))
        result = await run_in_threadpool(ToolRunner(workspace).run, tools.BROWSER_QA,
                                         BrowserQAInput(directory, values["page"], width, height,
                                                        baseline=baseline, baseline_run_id=baseline_id), log=lambda _: None)
        return RedirectResponse("/runs/" + result.run_id, 303)

    def research_form(*, selected=(), host="", error="", feed_url=""):
        datasets = [item for item in saved_datasets(RESEARCH_DATASETS, RESEARCH_SOURCE_TOOLS) if item["rows"]]
        return render("research_form", datasets=datasets, dataset_labels=RESEARCH_DATASETS,
                      selected=selected, host=host, error=error, feed_url=feed_url)

    @app.get("/tools/research")
    def research_options(added: str = "", host: str = "", url: str = ""):
        return research_form(selected=(added,), host=host, feed_url=url)

    @app.post("/tools/research/import")
    async def research_import(request: Request):
        async with export_form(request) as fields:
            verify_token(fields.get("token"))
            kind, host = fields.get("kind"), fields.get("host", "")
            if not isinstance(kind, str) or kind not in RESEARCH_DATASETS or not isinstance(host, str):
                raise HTTPException(400, "Choose a supported source type.")
            try:
                spec = export_input(fields, kind)
                imported = await run_in_threadpool(import_upload, workspace, fields.get("file"), spec)
            except ValueError as exc:
                return research_form(host=host, error=str(exc))
        if "dataset.json" not in imported.artifacts:
            return research_form(host=host, error=imported.warnings[0] if imported.warnings else "The import did not complete.")
        return RedirectResponse("/tools/research?" + urlencode({"added": imported.run_id, "host": host}), 303)

    @app.post("/tools/research")
    async def run_research(request: Request):
        fields = await form(request, repeated=("dataset",))
        host = fields.get("host", "")
        ids = list(dict.fromkeys(fields.get("dataset", ())))
        if not ids:
            return research_form(host=host, error="Choose at least one saved dataset.")
        datasets = []
        for dataset_id in ids:
            data = detail(dataset_id)
            manifest = data["manifest"]
            if dataset_kind(manifest, RESEARCH_SOURCE_TOOLS) not in RESEARCH_DATASETS:
                raise HTTPException(400, "Choose supported saved research datasets.")
            datasets.append(str(artifact_path(data, "dataset.json").parent))
        result = await run_in_threadpool(ToolRunner(workspace).run, tools.RESEARCH, ResearchInput(tuple(datasets), host), log=lambda _: None)
        return RedirectResponse("/runs/" + result.run_id, 303)

    @app.post("/tools/research/feed")
    async def sample_feed(request: Request):
        fields = await form(request)
        url, host = fields.get("url", ""), fields.get("host", "")
        try:
            limit = int(fields.get("max_items", "25"))
            if not 1 <= limit <= 500:
                raise ValueError
        except ValueError:
            return research_form(host=host, error="Choose between 1 and 500 feed items.")
        result = await run_in_threadpool(ToolRunner(workspace).run, tools.PUBLIC_FEED, FeedInput(url, limit), log=lambda _: None)
        if result.status == "failed":
            query = urlencode({"host": host}) if host else ""
            return RedirectResponse("/runs/" + result.run_id + (("?" + query) if query else ""), 303)
        if not result.counts.get("rows"):
            return RedirectResponse("/runs/" + result.run_id, 303)
        return RedirectResponse("/tools/research?" + urlencode({"added": result.run_id, "host": host}), 303)

    @app.get("/runs/{rid}/dataset/{row_id}")
    def dataset_row(rid: str, row_id: int):
        data = detail(rid)
        dataset = json.loads(artifact_path(data, "dataset.json").read_text(encoding="utf-8"))
        row = next((row for row in dataset["rows"] if row.get("row") == row_id), None)
        if row is None:
            raise HTTPException(404, "Unknown source row")
        return render("dataset_row", rid=rid, row=row, dataset=dataset["source"], dataset_labels=RESEARCH_DATASETS)

    def research_result(data, page, category, q):
        run = data["manifest"]
        report = (json.loads(artifact_path(data, "research.json").read_text(encoding="utf-8"))
                  if "research.json" in run["artifacts"] else {})
        if report and "content-plan.json" in run["artifacts"]:
            plan = json.loads(artifact_path(data, "content-plan.json").read_text(encoding="utf-8"))
            report.update({key: plan.get(key, []) for key in ("content_briefs", "keyword_clusters")})
        sections = {key: label for key, label in RESEARCH_SECTIONS.items() if report.get(key)}
        section = category if category in sections or category == "observations" else next(iter(sections), "keywords")
        if section == "observations":
            keyword = next((item for item in report.get("keywords", []) if item["query"] == q), None)
            rows = keyword["observations"] if keyword else []
        else:
            rows = report.get(section, [])
        page = min(max(1, page), max(1, (len(rows) + 29) // 30))
        return render("research_result", rid=run["run_id"], run=run, report=report, sections=sections, section=section,
                      q=q, rows=rows[(page - 1) * 30:page * 30], page=page, more=len(rows) > page * 30,
                      dataset_labels=RESEARCH_DATASETS)

    def feed_failure(data):
        manifest = data["manifest"]
        if "feed-source.json" in manifest["artifacts"]:
            return json.loads(artifact_path(data, "feed-source.json").read_text(encoding="utf-8"))
        shown, hidden = redact_url(str(manifest["parameters"].get("url", "")))
        warnings = manifest.get("warnings") or []
        return {"reason": "unknown", "message": warnings[0] if warnings else "The feed request failed.",
                "source": shown, "hidden_parameters": hidden, "candidate": ""}

    @app.get("/runs/{rid}")
    def result(rid: str, page: int = 1, evidence_page: int = 1, q: str = "", category: str = "",
               url_q: str = "", host: str = ""):
        data = detail(rid)
        run = data["manifest"]
        if run["tool_id"] == tools.PUBLIC_FEED.id and run["status"] == "failed":
            return render("feed_failed", rid=rid, run=run, failure=feed_failure(data), host=host)
        if run["tool_id"] == tools.COMPARE.id:
            return comparison_result(data, page, category)
        if run["tool_id"] == tools.RESEARCH.id:
            return research_result(data, page, category, q)
        if "dataset.json" in run["artifacts"] and dataset_kind(run, RESEARCH_SOURCE_TOOLS) in RESEARCH_DATASETS:
            dataset = json.loads(artifact_path(data, "dataset.json").read_text(encoding="utf-8"))
            rows = dataset["rows"]
            page = min(max(1, page), max(1, (len(rows) + 29) // 30))
            return render("dataset", rid=rid, run=run, dataset=dataset["source"], rows=rows[(page - 1) * 30:page * 30],
                          page=page, more=len(rows) > page * 30, dataset_labels=RESEARCH_DATASETS)
        if run["tool_id"] == tools.SITE_QA.id:
            report = (json.loads(artifact_path(data, "site-qa.json").read_text(encoding="utf-8"))
                      if "site-qa.json" in run["artifacts"] else {})
            findings = report.get("findings", [])
            page = min(max(1, page), max(1, (len(findings) + 29) // 30))
            return render("site_qa_result", rid=rid, run=run, report=report,
                          findings=findings[(page - 1) * 30:page * 30], page=page, more=len(findings) > page * 30)
        if run["tool_id"] == tools.BROWSER_QA.id:
            report = (json.loads(artifact_path(data, "browser-qa.json").read_text(encoding="utf-8"))
                      if "browser-qa.json" in run["artifacts"] else {})
            return render("browser_qa_result", rid=rid, run=run, report=report)
        if run["tool_id"] == tools.WORKBOOK.id:
            report = (json.loads(artifact_path(data, "report.json").read_text(encoding="utf-8"))
                      if "report.json" in run["artifacts"] else None)
            source = source_run(report.get("crawl") if report else None, run["parameters"].get("crawl"))
            return render("report_preview", rid=rid, run=run, report=report, source=source, providers=REPORT_PROVIDERS,
                          evidence_ids={item["id"] for item in source["evidence"]} if source else set())
        checks_view = run["tool_id"] == tools.CHECK.id
        report, key = ("checks.json", "observations") if checks_view else ("findings.json", "findings")
        has_report = report in run["artifacts"]
        rows = json.loads(artifact_path(data, report).read_text(encoding="utf-8"))[key] if has_report else []
        source = None
        if checks_view:
            parameters = run["parameters"]
            source = source_run(parameters.get("source_run_id"), parameters.get("in_dir"))
        evidence = data["evidence"]
        evidence_urls = {item["id"]: item["url"] for item in (source["evidence"] if source else evidence)}
        q, url_q = q.strip(), url_q.strip()
        term, url_term = unquote(q).casefold(), unquote(url_q).casefold()
        category_key = "check" if checks_view else "category"
        categories = sorted({row[category_key] for row in rows})
        category = category if category in categories else ""
        if category:
            rows = [row for row in rows if row[category_key] == category]
        if term:
            if checks_view:
                rows = [row for row in rows if matches_query(
                    term, row["url"], row["target"], row["value"], row["observation"],
                    OBSERVATION_LABELS.get(row["observation"], ""), CHECK_LABELS.get(row["check"], row["check"]))]
            else:
                rows = [row for row in rows if matches_query(
                    term, row["rule"], FINDING_LABELS.get(row["rule"], ""), row["detail"],
                    *(evidence_urls.get(eid, "") for eid in row["evidence_ids"]))]
        if url_term:
            evidence = [item for item in evidence if matches_query(url_term, item["url"])]
        page = min(max(page, 1), max(1, (len(rows) + 29) // 30))
        evidence_page = min(max(evidence_page, 1), max(1, (len(evidence) + 29) // 30))
        start, end = (page - 1) * 30, page * 30
        evidence_start, evidence_end = (evidence_page - 1) * 30, evidence_page * 30
        return render("result", rid=rid, run=run, artifacts=data["artifacts"], source=source,
                      checks_view=checks_view, check_labels=CHECK_LABELS, finding_labels=FINDING_LABELS,
                      observation_labels=OBSERVATION_LABELS,
                      has_report=has_report, has_evidence=bool(data["evidence"]), categories=categories,
                      q=q, category=category, url_q=url_q, rows=rows[start:end],
                      evidence=evidence[evidence_start:evidence_end], evidence_urls=evidence_urls,
                      page=page, more=len(rows) > end, evidence_page=evidence_page,
                      evidence_more=len(evidence) > evidence_end)

    def comparison_result(data, page, category):
        run = data["manifest"]
        rid = run["run_id"]
        report = (json.loads(artifact_path(data, "comparison.json").read_text(encoding="utf-8"))
                  if "comparison.json" in run["artifacts"] else {})
        inputs = run["parameters"]
        sources = [source_run(inputs.get(f"{side}_run_id"), inputs.get(side)) for side in ("before", "after")]
        findings = category == "findings"
        rows = report.get("findings" if findings else "pages")
        if rows is not None and not findings and category != "all":
            rows = [row for row in rows if row["state"] != "unchanged observed fields"]
        page = min(max(1, page), max(1, (len(rows or []) + 29) // 30))
        return render("comparison", run=run, rid=rid, report=report, sources=sources, rows=(rows or [])[(page - 1) * 30:page * 30],
                      unavailable=rows is None, page=page, more=len(rows or []) > page * 30,
                      category=category, findings=findings, finding_labels=FINDING_LABELS)

    @app.get("/runs/{rid}/review")
    def review_pairs(rid: str, pair: int | None = None, queue: str = "pending", page: int = 1):
        data = detail(rid)
        pairs = json.loads(artifact_path(data, "pairs.json").read_text(encoding="utf-8"))
        local = Path(data["directory"]) / "decisions.jsonl"
        decisions = review.load_decisions(local) if not local.is_symlink() else {}
        for key, decision in review.load_decisions(workspace.data_dir / "decisions.jsonl").items():
            if key not in decisions or decision["ts"] >= decisions[key]["ts"]:
                decisions[key] = decision
        entries = []
        for index, candidate in enumerate(pairs):
            decision = decisions.get(review.pair_key(candidate["url_a"], candidate["url_b"]))
            if decision and (candidate["url_a"], candidate["url_b"]) == (decision["url_b"], decision["url_a"]):
                choice = decision["decision"]
                decision = decision | {"decision": REVERSED_DECISIONS.get(choice, choice)}
            entries.append(dict(index=index, pair=candidate, decision=decision,
                                pending=review.needs_review(candidate, decision)))
        if pair is not None:
            if not 0 <= pair < len(entries):
                raise HTTPException(404, "Unknown review pair")
            selected = entries[pair]
            evidence = {item["url"]: item for item in data["evidence"]}
            pages = []
            for side in ("a", "b"):
                row = evidence.get(selected["pair"][f"url_{side}"])
                observation = read_observation(data, row) if row else {}
                pages.append(dict(url=selected["pair"][f"url_{side}"], title=selected["pair"].get(f"title_{side}"),
                                  words=selected["pair"].get(f"words_{side}"), excerpt=observation.get("text", "")[:1200],
                                  evidence=row["id"] if row else None))
            return render("review_pair", rid=rid, selected=selected, pair_pages=pages, decision_labels=DECISION_LABELS)
        pending = sum(entry["pending"] for entry in entries)
        waiting = queue != "reviewed"
        entries = [entry for entry in entries if entry["pending"] == waiting]
        page = min(max(1, page), max(1, (len(entries) + 29) // 30))
        return render("review", rid=rid, entries=entries[(page - 1) * 30:page * 30], pending=pending,
                      reviewed=len(pairs) - pending, waiting=waiting, page=page, more=len(entries) > page * 30)

    @app.post("/runs/{rid}/review/{index}")
    async def save_review(rid: str, index: int, request: Request):
        fields = await form(request)

        def save():
            with history.run_storage_lock():
                history.check_reset_complete()
                pairs = json.loads(artifact_path(detail(rid), "pairs.json").read_text(encoding="utf-8"))
                if not 0 <= index < len(pairs):
                    raise HTTPException(404, "Unknown review pair")
                review.save_decision(workspace.data_dir / "decisions.jsonl", pairs[index],
                                     fields.get("decision", ""), fields.get("note", "").strip())

        try:
            await run_in_threadpool(save)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        except Timeout as exc:
            raise HTTPException(409, "Another decision is being saved. Try again.") from exc
        return RedirectResponse(f"/runs/{rid}/review?pair={index}", 303)

    @app.get("/runs/{rid}/files/{name}")
    def download(rid: str, name: str):
        return FileResponse(artifact_path(detail(rid), name), filename=name, media_type="application/octet-stream")

    @app.get("/runs/{rid}/preview/{name}")
    def preview_png(rid: str, name: str):
        data = detail(rid)
        if data["manifest"]["tool_id"] != tools.BROWSER_QA.id or name not in ("screenshot.png", "changed-pixels.png"):
            raise HTTPException(404)
        return FileResponse(artifact_path(data, name), media_type="image/png")

    @app.get("/runs/{rid}/evidence/{eid}")
    def evidence(rid: str, eid: str):
        data = detail(rid)
        row = next((e for e in data["evidence"] if e["id"] == eid), None)
        if not row:
            raise HTTPException(404)
        return render("evidence", rid=rid, observation=read_observation(data, row))
    return app
