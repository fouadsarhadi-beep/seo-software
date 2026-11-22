"""Loopback workbench over the same application runner as the CLI."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
import json
from pathlib import Path
from secrets import compare_digest, token_urlsafe
from threading import Event, Lock
from urllib.parse import parse_qs
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, RedirectResponse
from jinja2 import Environment, PackageLoader, select_autoescape

from seo_analysis.app.runner import ToolRunner
from seo_analysis.core import tools
from seo_analysis.core.network import HttpOrigin
from seo_analysis.storage.history import History
from seo_analysis.web.crawl import CrawlConfig


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

    async def form(request):
        if request.headers.get("content-type", "").split(";")[0] != "application/x-www-form-urlencoded":
            raise HTTPException(415)
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 8192:
                raise HTTPException(413)
        fields = {k: v[0] for k, v in parse_qs(body.decode()).items()}
        if not compare_digest(fields.pop("token", "").encode(), token.encode()):
            raise HTTPException(403)
        return fields

    def render(view, **fields):
        return HTMLResponse(templates.get_template("workbench.html").render(view=view, token=token, **fields))

    def detail(rid):
        try:
            return history.show(rid)
        except ValueError as exc:
            raise HTTPException(404, "Unknown run") from exc

    @app.get("/")
    def home():
        return render("home", runs=history.list_runs(limit=12), projects=history.projects())

    @app.get("/history")
    def runs(page: int = 1):
        page = max(1, page)
        records = history.list_runs(limit=31, offset=(page - 1) * 30)
        return render("history", runs=records[:30], page=page, more=len(records) > 30)

    @app.get("/projects")
    def projects():
        return render("projects", projects=[p | {"targets": history.targets(p["name"])} for p in history.projects()])

    @app.post("/projects")
    async def create_project(request: Request):
        f = await form(request)
        try:
            history.add_project(f.get("name", ""))
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        return RedirectResponse("/projects", 303)

    @app.post("/targets")
    async def create_target(request: Request):
        f = await form(request)
        try:
            history.add_target(f.get("project"), f.get("name", ""), "website", f.get("url", ""))
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        return RedirectResponse("/projects", 303)

    def launch(job, cfg, project, saved):
        def progress(message):
            if job.cancel.is_set():
                raise KeyboardInterrupt()
            job.detail = str(message)[:500]
        try:
            job.status = "running"
            result = ToolRunner(workspace).run(tools.AUDIT, cfg, project=project, saved_target=saved, log=progress)
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

    @app.get("/runs/{rid}")
    def result(rid: str, page: int = 1):
        data = detail(rid)
        findings = []
        if "findings.json" in data["manifest"]["artifacts"]:
            findings = json.loads((Path(data["directory"]) / "findings.json").read_text(encoding="utf-8"))["findings"]
        page = max(page, 1)
        return render("result", rid=rid, run=data["manifest"], artifacts=data["artifacts"],
                      findings=findings[(page-1)*30:page*30], page=page, more=len(findings)>page*30)

    @app.get("/runs/{rid}/files/{name}")
    def download(rid: str, name: str):
        data = detail(rid)
        path = Path(data["directory"]) / name
        if name not in data["manifest"]["artifacts"] or path.is_symlink() or path.parent.resolve() != workspace.runs_dir.resolve() / rid:
            raise HTTPException(404)
        return FileResponse(path, filename=name, media_type="application/octet-stream")

    @app.get("/runs/{rid}/evidence/{eid}")
    def evidence(rid: str, eid: str):
        data = detail(rid)
        row = next((e for e in data["evidence"] if e["id"] == eid), None)
        if not row:
            raise HTTPException(404)
        path = Path(data["directory"]) / row["path"]
        if not path.resolve().is_relative_to(workspace.runs_dir.resolve() / rid):
            raise HTTPException(404)
        return render("evidence", rid=rid, observation=json.loads(path.read_text(encoding="utf-8")))
    return app
