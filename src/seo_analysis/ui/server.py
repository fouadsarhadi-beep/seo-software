"""Loopback workbench over the same application runner as the CLI."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
import json
from pathlib import Path, PureWindowsPath
from secrets import compare_digest, token_urlsafe
from threading import Event, Lock
from urllib.parse import parse_qs, unquote, urlencode
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, RedirectResponse
from filelock import Timeout
from jinja2 import Environment, PackageLoader, select_autoescape
from starlette.concurrency import run_in_threadpool

from seo_analysis.analysis import review
from seo_analysis.analysis.checks import CHECKS
from seo_analysis.app.agent import run_snapshot_tool
from seo_analysis.app.runner import ToolRunner
from seo_analysis.core import tools
from seo_analysis.core.network import HttpOrigin
from seo_analysis.reporting.workbook import WorkbookInput
from seo_analysis.research.imports import ExportInput
from seo_analysis.storage.history import History
from seo_analysis.ui.uploads import export_form, import_upload
from seo_analysis.web.crawl import CrawlConfig

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


def matches_query(term, *values):
    return any(term in unquote(str(value)).casefold() for value in values)


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
                                 "Content-Security-Policy": "default-src 'none'; style-src 'self' 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'"})
        return response

    def verify_token(value):
        if not isinstance(value, str) or not compare_digest(value.encode(), token.encode()):
            raise HTTPException(403)

    async def form(request):
        if request.headers.get("content-type", "").split(";")[0] != "application/x-www-form-urlencoded":
            raise HTTPException(415)
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 8192:
                raise HTTPException(413)
        fields = {k: v[0] for k, v in parse_qs(body.decode()).items()}
        verify_token(fields.pop("token", ""))
        return fields

    def render(view, **fields):
        return HTMLResponse(templates.get_template("workbench.html").render(view=view, token=token, **fields))

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
    def home():
        return render("home", runs=history.list_runs(limit=12, archived=False), projects=history.projects())

    @app.get("/history")
    def runs(page: int = 1, archived: bool = False):
        page = max(1, page)
        records = history.list_runs(limit=31, offset=(page - 1) * 30, archived=archived)
        return render("history", runs=records[:30], page=page, more=len(records) > 30, archived=archived)

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
        return render("project", project=project, targets=history.targets(project))

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

    def launch(job, cfg, project, saved):
        def progress(message):
            job.detail = str(message)[:500]
        try:
            job.status = "running"
            result = ToolRunner(workspace).run(
                tools.AUDIT, cfg, project=project, saved_target=saved, log=progress, cancel=job.cancel
            )
            job.run_id, job.status = result.run_id, result.status
        except Exception as exc:
            job.status, job.detail = "failed", str(exc)

    @app.post("/audit")
    async def audit(request: Request):
        f = await form(request)
        url, project, saved = f.get("url", ""), f.get("project") or None, f.get("target") or None
        try:
            selection = history.selection(project, saved)
            if selection:
                url = selection["url"]
            HttpOrigin.from_url(url)
            pages = int(f.get("pages", 100))
            if not 1 <= pages <= 500:
                raise ValueError("Choose between 1 and 500 pages.")
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        cfg = CrawlConfig(url, "", source=url, kind=selection["kind"] if selection else "website",
                          limit=pages, link_crawl=f.get("links") == "on", allow_local=f.get("local") == "on")
        with guard:
            if any(j.status in ("queued", "running") for j in jobs.values()):
                raise HTTPException(409, "An audit is already running.")
            if len(jobs) >= 50:
                jobs.pop(next(iter(jobs)))
            jid = uuid4().hex
            jobs[jid] = Job()
            pool.submit(launch, jobs[jid], cfg, project, saved)
        return RedirectResponse("/jobs/" + jid, 303)

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

    def report_form(rid, selected, error=""):
        data = detail(rid)
        artifact_path(data, "snapshot.jsonl")
        datasets = {kind: [] for kind in REPORT_PROVIDERS}
        for run in history.runs_with_artifact("dataset.json"):
            params = run["parameters"]
            kind = params.get("kind")
            if run["tool_id"] == tools.IMPORT.id and kind in datasets:
                filename = params.get("source_filename") or PureWindowsPath(params.get("file", "")).name
                datasets[kind].append(dict(id=run["run_id"], filename=filename, observed=params.get("observed", ""),
                                           status=run["status"]))
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
                observed = fields.get("observed", "")
                period_start = fields.get("period_start", "")
                columns = fields.get("columns", "")
                if any(not isinstance(value, str) for value in (*selected.values(), observed, period_start, columns)):
                    raise ValueError("Enter dates and column mappings as text.")
                spec = ExportInput("", kind, REPORT_PROVIDERS[kind], observed,
                                   period_start=period_start, mapping=json.loads(columns or "{}"))
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
                if manifest["tool_id"] != tools.IMPORT.id or manifest["parameters"].get("kind") != kind:
                    raise HTTPException(400, f"Choose a saved {REPORT_PROVIDERS[kind]} export.")
                datasets.append(str(artifact_path(item, "dataset.json").parent))
        if not datasets:
            return report_form(rid, selected, "Choose at least one saved export.")
        result = await run_in_threadpool(ToolRunner(workspace).run, tools.WORKBOOK, WorkbookInput(str(crawl), tuple(datasets)),
                                         project=data["manifest"]["project"], log=lambda _: None)
        return RedirectResponse("/runs/" + result.run_id, 303)

    @app.get("/runs/{rid}")
    def result(rid: str, page: int = 1, evidence_page: int = 1, q: str = "", category: str = "", url_q: str = ""):
        data = detail(rid)
        run = data["manifest"]
        if run["tool_id"] == tools.COMPARE.id:
            return comparison_result(data, page, category)
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
        pairs = json.loads(artifact_path(detail(rid), "pairs.json").read_text(encoding="utf-8"))
        if not 0 <= index < len(pairs):
            raise HTTPException(404, "Unknown review pair")
        try:
            await run_in_threadpool(review.save_decision, workspace.data_dir / "decisions.jsonl", pairs[index],
                                    fields.get("decision", ""), fields.get("note", "").strip())
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        except Timeout as exc:
            raise HTTPException(409, "Another decision is being saved. Try again.") from exc
        return RedirectResponse(f"/runs/{rid}/review?pair={index}", 303)

    @app.get("/runs/{rid}/files/{name}")
    def download(rid: str, name: str):
        return FileResponse(artifact_path(detail(rid), name), filename=name, media_type="application/octet-stream")

    @app.get("/runs/{rid}/evidence/{eid}")
    def evidence(rid: str, eid: str):
        data = detail(rid)
        row = next((e for e in data["evidence"] if e["id"] == eid), None)
        if not row:
            raise HTTPException(404)
        return render("evidence", rid=rid, observation=read_observation(data, row))
    return app
