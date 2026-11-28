import json
from pathlib import Path
import time
from threading import Event
from uuid import uuid4
from bs4 import BeautifulSoup
from fastapi.testclient import TestClient

from seo_analysis import cli
from seo_analysis.app.runner import ToolRunner
from seo_analysis.core import tools
from seo_analysis.core.workspace import Workspace
from seo_analysis.storage.history import History
from seo_analysis.research import sources
from seo_analysis.web.fetch import Fetcher
from seo_analysis.ui.server import create_app
from seo_analysis.web.crawl import CrawlConfig


def test_ui_end_to_end(site, tmp_path):
    origin = "http://127.0.0.1:8972"
    ws = Workspace(tmp_path / "config", tmp_path / "data", tmp_path / "exports")
    site.add("/robots.txt", f"User-agent: *\nSitemap: {site.base}/map")
    site.add("/map", f"<urlset><url><loc>{site.base}/</loc></url></urlset>")
    site.add("/", "<html><main>متن فارسی مقاله</main></html>")
    with TestClient(create_app(ws, 8972), base_url=origin) as client:
        home = client.get("/")
        token = BeautifulSoup(home.text, "html.parser").select_one("input[name=token]")["value"]
        assert client.get("/", headers={"Host":"elsewhere"}).status_code == 403
        assert client.post("/audit", data={"url":site.base,"token":token}).status_code == 403
        assert client.post("/audit", headers={"Origin": origin}, data={"url":site.base}).status_code == 403
        reply = client.post("/audit", headers={"Origin": origin}, data={"url":site.base,"token":token,"local":"on"})
        for _ in range(100):
            reply = client.get(reply.url)
            if "/runs/" in str(reply.url):
                break
            time.sleep(.05)
        dom = BeautifulSoup(reply.text, "html.parser")
        assert dom.h1.text == "Run results"
        assert dom.select_one('nav.tabs a[aria-current="page"]').get_text(strip=True) == "Overview"
        assert "at least two eligible pages" in reply.text
        run_path = reply.url.path
        pages_tab = BeautifulSoup(client.get(run_path, params={"tab": "pages"}).text, "html.parser")
        evidence = pages_tab.select_one('a[href*="/evidence/"]')
        assert evidence.text == "/"
        page = client.get(evidence["href"])
        assert page.status_code == 200 and "متن فارسی مقاله" in page.text
        assert "3 words" in page.text
        exports = BeautifulSoup(client.get(run_path, params={"tab": "exports"}).text, "html.parser")
        assert client.get(exports.select_one('a[href$="inventory.csv"]')["href"]).status_code == 200
        technical = exports.find("summary", string="Technical files").parent
        assert not technical.has_attr("open")
        assert technical.select_one('a[href$="snapshot.jsonl"]')
        history = BeautifulSoup(client.get("/history").text, "html.parser")
        archive = history.select_one(f'form[action="{run_path}/archive"]')
        request = {"token": archive.select_one('input[name="token"]')["value"], "action": "archive"}
        assert client.post(archive["action"], data=request).status_code == 403
        headers = {"Origin": origin}
        assert client.post(archive["action"], headers=headers, data=request).status_code == 200
        assert History(ws).reindex()["indexed"] == 1
        assert run_path not in client.get("/").text
        assert run_path not in client.get("/history").text
        archived = client.get("/history?archived=true")
        assert run_path in archived.text and "Restore" in archived.text
        assert client.get(run_path).status_code == 200
        archived_exports = BeautifulSoup(client.get(run_path, params={"tab": "exports"}).text, "html.parser")
        assert client.get(archived_exports.select_one('a[href$="inventory.csv"]')["href"]).status_code == 200
        assert client.post(archive["action"], headers=headers, data=request | {"action": "restore"}).status_code == 200
        assert run_path in client.get("/history").text
        assert run_path not in client.get("/history?archived=true").text


def test_ui_projects_list_and_explicit_target_forms(tmp_path):
    origin = "http://127.0.0.1:8972"
    ws = Workspace(tmp_path / "config", tmp_path / "data", tmp_path / "exports")
    with TestClient(create_app(ws, 8972), base_url=origin) as client:
        initial = BeautifulSoup(client.get("/projects").text, "html.parser")
        token = initial.select_one('input[name="token"]')["value"]
        assert initial.find("summary", string="Create project").parent.select_one('input[name="url"]')
        name = "SEO & content + فارسی"
        headers = {"Origin": origin}
        created = client.post("/projects", headers=headers,
                              data={"token": token, "name": name, "url": "https://example.com/"})
        listing = BeautifulSoup(created.text, "html.parser")
        assert listing.select_one('form[action="/targets"]') is None
        project = listing.find("a", string=name)["href"]
        detail = BeautifulSoup(client.get(project).text, "html.parser")
        assert detail.find("strong", string="Website")
        add_target = detail.find("summary", string="Add target").parent
        assert not add_target.has_attr("open")
        saved = client.post("/targets", headers=headers,
                            data={"token": token, "project": name, "name": "Blog", "url": "https://example.com/blog"})
        assert BeautifulSoup(saved.text, "html.parser").find("strong", string="Blog")
        assert name in [option.text for option in BeautifulSoup(client.get("/").text, "html.parser")
                        .select('select[name="project"] option')]


def test_ui_cancel_interrupts_retry_and_preserves_observations(site, tmp_path):
    origin = "http://127.0.0.1:8972"
    ws = Workspace(tmp_path / "config", tmp_path / "data", tmp_path / "exports")
    site.add("/robots.txt", f"User-agent: *\nSitemap: {site.base}/map")
    site.add("/map", "<urlset>" + "".join(
        f"<url><loc>{site.base}/{path}</loc></url>" for path in ("ok", "busy")
    ) + "</urlset>")
    site.add("/ok", "<html><main>Completed page</main></html>")
    retry_requested = Event()

    def busy(_):
        retry_requested.set()
        return 503, [("Retry-After", "30")], b"Retry later"

    site.routes["/busy"] = busy
    with TestClient(create_app(ws, 8972), base_url=origin) as client:
        token = BeautifulSoup(client.get("/").text, "html.parser").select_one("input[name=token]")["value"]
        headers = {"Origin": origin}
        submitted = client.post("/audit", headers=headers, follow_redirects=False,
                                data={"url": site.base, "token": token, "local": "on"})
        job = submitted.headers["location"]
        assert retry_requested.wait(5)
        cancelled = client.post(f"{job}/cancel", headers=headers, data={"token": token})
        assert cancelled.status_code == 200
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            result = client.get(job, follow_redirects=False)
            if result.status_code == 303:
                break
            time.sleep(.05)
        assert result.status_code == 303
        run_id = result.headers["location"].rsplit("/", 1)[-1]
        directory = ws.runs_dir / run_id
        manifest = json.loads((directory / "run.json").read_text(encoding="utf-8"))
        assert manifest["status"] == "cancelled"
        assert manifest["counts"]["observed"] == 1
        assert site.hits["/busy"] == 1
        results_page = client.get(result.headers["location"], params={"tab": "pages"})
        evidence_link = BeautifulSoup(results_page.text, "html.parser").find("a", string="/ok")
        assert client.get(evidence_link["href"]).status_code == 200


def test_ui_clean_five_page_sample_shows_every_evidence_link(site, tmp_path):
    """A limit-reached audit with zero findings must still list its five observed pages."""
    origin = "http://127.0.0.1:8972"
    ws = Workspace(tmp_path / "config", tmp_path / "data", tmp_path / "exports")
    site.add("/robots.txt", f"User-agent: *\nSitemap: {site.base}/map")
    site.add("/map", "<urlset>" + "".join(
        f"<url><loc>{site.base}/page-{i}</loc></url>" for i in range(6)
    ) + "</urlset>")
    topics = [
        "Orchids reproduce through pollen transferred between specialized flowers.",
        "Glaciers accumulate compacted snow and reshape mountainous valleys.",
        "Satellites orbit the planet using carefully calculated trajectories.",
        "Pottery makers fire clay vessels inside extremely hot kilns.",
        "Octopuses use flexible arms to manipulate objects on the seabed.",
        "Astronomers study stellar spectra to measure distant temperatures.",
    ]
    for i, body in enumerate(topics):
        url = f"{site.base}/page-{i}"
        site.add(f"/page-{i}", (
            f'<html><head><title>{body.split()[0]} guide</title>'
            f'<meta name="description" content="{body}">'
            f'<link rel="canonical" href="{url}"></head>'
            f'<body><main><h1>{body.split()[0]} overview</h1><p>{body}</p></main></body></html>'
        ))
    with TestClient(create_app(ws, 8972), base_url=origin) as client:
        token = BeautifulSoup(client.get("/").text, "html.parser").select_one("input[name=token]")["value"]
        response = client.post("/audit", headers={"Origin": origin},
                               data={"url": site.base, "token": token, "pages": "5", "local": "on"})
        for _ in range(150):
            response = client.get(response.url)
            if "/runs/" in str(response.url):
                break
            time.sleep(.05)
        assert "/runs/" in str(response.url)
        dom = BeautifulSoup(response.text, "html.parser")
        assert dom.select_one(".badge").get_text(strip=True) == "partial"
        assert "A capped sample." in dom.get_text(" ", strip=True)
        assert "Reached the configured limit" not in dom.get_text(" ", strip=True)
        assert "0 findings" in dom.get_text(" ", strip=True)
        pages_tab = BeautifulSoup(client.get(response.url.path, params={"tab": "pages"}).text, "html.parser")
        links = pages_tab.select('a[href*="/evidence/"]')
        assert len(links) == 5
        for link in links:
            evidence = client.get(link["href"])
            assert evidence.status_code == 200
            assert f"{site.base}{link.text}" in evidence.text


def test_ui_page_table_paginates_filters_and_opens_exact_counts(tmp_path):
    """The table slices 30 rows, keeps filters in the URL and reproduces each overview count."""
    ws = Workspace(tmp_path / "config", tmp_path / "data", tmp_path / "exports")
    rid = uuid4().hex
    folder = ws.runs_dir / rid
    folder.mkdir(parents=True)
    pages = []
    for i in range(35):
        url = f"https://example.com/page-{i+1}"
        page = {"evidence_id": f"page-{i+1:06d}", "url": url, "final_url": url, "first_status": 200,
                "final_status": 200, "chain": [], "effective_indexability": "indexable",
                "indexability_reason": "no noindex or none directive for Googlebot",
                "title": f"Page {i+1}", "words": 5, "depth": 0,
                "observed_at": "2026-11-22T00:00:00+00:00"}
        if i >= 33:
            page.update(final_status=301, final_url=f"https://example.com/moved-{i+1}",
                        chain=[url, f"https://example.com/moved-{i+1}"])
        pages.append(page)
    (folder / "snapshot.jsonl").write_text("\n".join(json.dumps(page) for page in pages) + "\n", encoding="utf-8")
    observations = folder / "observations"
    observations.mkdir()
    for page in pages:
        (observations / f"{page['evidence_id']}.json").write_text(json.dumps(page), encoding="utf-8")
    findings = [{"category": "review", "rule": "seo.missing-meta", "detail": f"Finding {i+1}",
                 "evidence_ids": [pages[i]["evidence_id"]]} for i in range(32)]
    (folder / "findings.json").write_text(json.dumps({"findings": findings}), encoding="utf-8")
    manifest = {
        "run_id": rid, "tool_id": "seo.audit", "status": "succeeded", "project": None,
        "saved_target": None, "started_at": "2026-11-22T00:00:00Z", "finished_at": "2026-11-22T00:00:01Z",
        "parameters": {"source": "https://example.com/", "limit": 35},
        "counts": {"observed": 35, "findings": 32, "redirecting": 2, "errors": 0},
        "warnings": [], "artifacts": ["findings.json", "snapshot.jsonl"],
    }
    (folder / "run.json").write_text(json.dumps(manifest), encoding="utf-8")
    History(ws).index(folder)

    def rows(text):
        return [row for row in BeautifulSoup(text, "html.parser").select("table tr") if row.find("td")]

    with TestClient(create_app(ws, 8972), base_url="http://127.0.0.1:8972") as client:
        base = f"/runs/{rid}"
        first = client.get(base, params={"tab": "pages"})
        assert len(rows(first.text)) == 30 and "1–30 of 35" in first.text
        second = client.get(base, params={"tab": "pages", "page": 2})
        assert len(rows(second.text)) == 5 and "31–35 of 35" in second.text
        assert "Previous" in second.text
        clamped = client.get(base, params={"tab": "pages", "page": 99})
        assert "31–35 of 35" in clamped.text
        redirecting = rows(client.get(base, params={"tab": "pages", "redirect": "any"}).text)
        assert len(redirecting) == 2
        assert "moved-35" in " ".join(row.get_text(" ", strip=True) for row in redirecting)
        filtered_rule = client.get(base, params={"tab": "pages", "rule": "seo.missing-meta"})
        assert "1–30 of 32" in filtered_rule.text
        single = rows(client.get(base, params={"tab": "pages", "url_q": "page-35"}).text)
        assert len(single) == 1 and "/page-35" in single[0].get_text(" ", strip=True)
        evidence_page = client.get(single[0].find("a", href=True)["href"])
        assert evidence_page.status_code == 200
        back = BeautifulSoup(evidence_page.text, "html.parser").find("a", string="Back to results")["href"]
        assert back.startswith(f"/runs/{rid}?") and "url_q=page-35" in back
        spoofed = client.get(f"/runs/{rid}/evidence/{pages[34]['evidence_id']}", params={"back": "//evil.test"})
        assert "evil.test" not in spoofed.text
        empty = client.get(base, params={"tab": "pages", "url_q": "nothing-matches"})
        assert "No observed pages match these filters." in empty.text
        legacy = BeautifulSoup(client.get(base, params={"url_q": "page-35"}).text, "html.parser")
        assert legacy.select_one('input[name="url_q"]')["value"] == "page-35"
        detail = BeautifulSoup(client.get(base, params={"tab": "findings", "rule": "seo.missing-meta"}).text,
                               "html.parser")
        assert detail.find("h3", string="What was observed") and detail.find("h3", string="Why it matters")
        assert len(detail.select('a[href*="/evidence/"]')) == 32


def test_ui_runs_saved_checks_offline_and_matches_cli(site, tmp_path, capsys):
    origin = "http://127.0.0.1:8972"
    ws = Workspace(tmp_path / "config.toml", tmp_path / "data", tmp_path / "exports")
    ws.config_file.write_text('[paths]\ndata_dir = "data"', encoding="utf-8")
    site.add("/map", f"<urlset><url><loc>{site.base}/one</loc></url><url><loc>{site.base}/gone</loc></url></urlset>")
    site.add("/one", '<html><main>Article</main><a href="/gone">Missing</a><a href="/outside">Unobserved</a></html>')
    audit = ToolRunner(ws).run(tools.AUDIT, CrawlConfig(site.base + "/map", "", delay=0, allow_local=True), log=lambda _: None)
    hits = dict(site.hits)
    base = f"/runs/{audit.run_id}"
    assert cli.main(["--config-file", str(ws.config_file), "check", "--run", audit.run_id, "--json"]) == 0
    check = json.loads(capsys.readouterr().out)
    with TestClient(create_app(ws, 8972), base_url=origin) as client:
        dom = BeautifulSoup(client.get(base, params={"tab": "exports"}).text, "html.parser")
        form = dom.select_one(f'form[action="{base}/checks"]')
        token = form.select_one('input[name="token"]')["value"]
        assert client.post(form["action"], data={"token": token}).status_code == 403
        reply = client.post(form["action"], headers={"Origin": origin}, data={"token": token, "check": "all"})
        assert reply.is_success
        dom = BeautifulSoup(reply.text, "html.parser")
        assert dom.select_one(f'a[href="{base}"]')
        evidence = dom.select_one(f'a[href^="{base}/evidence/"]')
        assert client.get(evidence["href"]).is_success
        json_link = dom.select_one('a[href$="checks.json"]')["href"]
        assert client.get(json_link).json() == json.loads((Path(check["out_dir"]) / "checks.json").read_text(encoding="utf-8"))
        assert client.get(dom.select_one('a[href$="checks.csv"]')["href"]).is_success
        assert "Unknown (target not observed)" in client.get(reply.url, params={"category": "links", "q": "unknown"}).text
        broken = client.get(reply.url, params={"category": "broken-links"}).text
        assert "Observed HTTP error" in broken and "/outside" not in broken

        snapshot = Path(audit.out_dir) / "snapshot.jsonl"
        rows = [json.loads(line) for line in snapshot.read_text(encoding="utf-8").splitlines()]
        rows[0]["markup"].pop("assets")
        snapshot.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
        older = client.post(form["action"], headers={"Origin": origin}, data={"token": token, "check": "assets"})
        assert "Technical checks · partial" in older.text and "markup fields unavailable: 1" in older.text
    assert site.hits == hits


def test_ui_feed_failure_explains_the_source_and_offers_recovery(site, tmp_path, monkeypatch):
    origin = "http://127.0.0.1:8972"
    monkeypatch.setattr(sources, "Fetcher", lambda *args, **kwargs: Fetcher(*args, **kwargs, allow_local=True))
    site.add("/robots.txt", "User-agent: *\n")
    site.add("/page", '<!doctype html><html><head><link rel="alternate" type="application/rss+xml" '
                      'href="/feed.xml"></head><body>Home</body></html>', ctype="text/html")
    ws = Workspace(tmp_path / "config", tmp_path / "data", tmp_path / "exports")
    with TestClient(create_app(ws, 8972), base_url=origin) as client:
        form = client.get("/tools/research")
        token = BeautifulSoup(form.text, "html.parser").select_one("input[name=token]")["value"]
        reply = client.post("/tools/research/feed", headers={"Origin": origin},
                            data={"token": token, "url": site.base + "/page?token=SECRET",
                                  "max_items": "25", "host": "example.org"})
        assert reply.status_code == 200
        assert "Feed import failed" in reply.text
        assert "returned an HTML page" in reply.text
        assert "SECRET" not in reply.text
        assert "Use this feed" in reply.text and site.base + "/feed.xml" in reply.text
        assert "Edit source" in reply.text
        assert "normalized.csv" not in reply.text and "requests.json" not in reply.text
        assert reply.url.path.startswith("/runs/") and "host=example.org" in str(reply.url)

        links = BeautifulSoup(reply.text, "html.parser").select('a[href*="/tools/research?url="]')
        edit = next(link for link in links if link.text.strip() == "Edit source")
        reopened = client.get(edit["href"])
        assert reopened.status_code == 200
        assert f'value="{site.base}/page"' in reopened.text


def test_ui_overview_and_task_navigation_guide_a_first_session(tmp_path):
    origin = "http://127.0.0.1:8972"
    ws = Workspace(tmp_path / "config", tmp_path / "data", tmp_path / "exports")
    with TestClient(create_app(ws, 8972), base_url=origin) as client:
        home = BeautifulSoup(client.get("/").text, "html.parser")
        assert home.h1.text == "Your workbench"
        assert home.select_one('form[action="/projects"]')
        assert home.select_one('a[href="/audit/new"]')
        tasks = {link.get_text(strip=True): link["href"] for link in home.select("nav.tasks a")}
        assert tasks == {"Overview": "/", "Website audit": "/audit/new",
                         "Keyword and competitor research": "/tools/research",
                         "Search and traffic": "/tools/search-traffic", "Site QA": "/tools/site-qa",
                         "History": "/history", "Manage saved data": "/history/data"}
        assert home.select_one('nav.tasks a[aria-current="page"]').get_text(strip=True) == "Overview"

        start = BeautifulSoup(client.get("/audit/new").text, "html.parser")
        assert start.h1.text == "Start an audit"
        assert "page cap" in start.text and start.select_one('select[name="project"]')
        assert start.select_one('nav.tasks a[aria-current="page"]').get_text(strip=True) == "Website audit"

        traffic = BeautifulSoup(client.get("/tools/search-traffic").text, "html.parser")
        assert traffic.h1.text == "Search and traffic"
        assert "Import ready" in traffic.text and "Not available" in traffic.text
        assert traffic.select_one('nav.tasks a[aria-current="page"]').get_text(strip=True) == "Search and traffic"


def test_ui_overview_centers_the_selected_project(site, tmp_path):
    origin = "http://127.0.0.1:8972"
    ws = Workspace(tmp_path / "config", tmp_path / "data", tmp_path / "exports")
    site.add("/robots.txt", f"User-agent: *\nSitemap: {site.base}/map")
    site.add("/map", f"<urlset><url><loc>{site.base}/</loc></url></urlset>")
    site.add("/", "<html><main>نمونه متن</main></html>")
    with TestClient(create_app(ws, 8972), base_url=origin) as client:
        token = BeautifulSoup(client.get("/audit/new").text, "html.parser").select_one("input[name=token]")["value"]
        headers = {"Origin": origin}
        client.post("/projects", headers=headers, data={"token": token, "name": "Acme", "url": site.base})
        client.post("/targets", headers=headers, data={"token": token, "project": "Acme",
                                                       "name": "Blog", "url": site.base})
        reply = client.post("/audit", headers=headers, data={"url": site.base, "token": token, "local": "on",
                                                             "project": "Acme", "pages": "5"})
        for _ in range(200):
            reply = client.get(reply.url)
            if "/runs/" in str(reply.url):
                break
            time.sleep(.05)
        run_path = reply.url.path
        overview = BeautifulSoup(client.get("/").text, "html.parser")
        assert overview.h1.text == "Acme"
        assert overview.select_one('select[name="project"] option[selected]').get_text(strip=True) == "Acme"
        assert overview.find("h2", string="Targets") and "Blog" in overview.text
        latest = overview.find("h2", string="Latest audit").find_next("a", href=run_path)
        assert latest is not None
        assert overview.find("h2", string="Recent work in this project")
        assert overview.select_one(f'a[href="{run_path}"]')
        assert "Website audit" in overview.text and "seo.audit" not in overview.text
        client.post("/projects", headers=headers, data={"token": token, "name": "Beta"})
        beta = BeautifulSoup(client.get("/?project=Beta").text, "html.parser")
        assert beta.h1.text == "Beta"
        assert "No audits for this project yet." in beta.text
        assert beta.select_one(f'a[href="{run_path}"]') is None
        assert BeautifulSoup(client.get("/?project=Acme").text, "html.parser").select_one(f'a[href="{run_path}"]')
        assert overview.select_one('form.switcher[action="/"]')
