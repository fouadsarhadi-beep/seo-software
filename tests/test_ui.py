import json
import time
from threading import Event
from uuid import uuid4
from bs4 import BeautifulSoup
from fastapi.testclient import TestClient

from seo_analysis.core.workspace import Workspace
from seo_analysis.storage.history import History
from seo_analysis.ui.server import create_app


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
        assert dom.find("h2", string="Crawled pages") is not None
        evidence = dom.select_one('a[href*="/evidence/"]')
        assert evidence.text == site.base + "/"
        page = client.get(evidence["href"])
        assert page.status_code == 200 and "متن فارسی مقاله" in page.text
        assert "3 words" in page.text
        assert "at least two eligible pages" in reply.text
        assert client.get(dom.select_one('a[href$="inventory.csv"]')["href"]).status_code == 200


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
        results_page = client.get(result.headers["location"])
        evidence_link = BeautifulSoup(results_page.text, "html.parser").find("a", string=f"{site.base}/ok")
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
        assert "partial" in dom.select_one("section strong").text
        assert "0 findings" in dom.get_text(" ")
        heading = dom.find("h2", string="Crawled pages")
        assert heading is not None
        links = heading.find_next("ul").find_all("a")
        assert len(links) == 5
        for link in links:
            evidence = client.get(link["href"])
            assert evidence.status_code == 200
            assert link.get_text(strip=True) in evidence.text


def test_ui_result_paginates_observations_and_findings_independently(tmp_path):
    """Both sections stay visible; advancing one does not alter the other."""
    ws = Workspace(tmp_path / "config", tmp_path / "data", tmp_path / "exports")
    rid = uuid4().hex
    folder = ws.runs_dir / rid
    observations = folder / "observations"
    observations.mkdir(parents=True)
    entries = []
    for i in range(35):
        eid = f"page-{i+1:06d}"
        url = f"https://example.com/page-{i+1}"
        entry = {"evidence_id": eid, "url": url, "observed_at": "2026-11-22T00:00:00Z",
                 "text": f"Page {i+1} content"}
        (observations / f"{eid}.json").write_text(json.dumps(entry), encoding="utf-8")
        entries.append(entry)
    findings = [
        {"category": "review", "rule": "seo.missing-meta", "detail": f"Finding {i+1}",
         "evidence_ids": [entries[i]["evidence_id"]]} for i in range(32)
    ]
    (folder / "findings.json").write_text(json.dumps({"findings": findings}), encoding="utf-8")
    manifest = {
        "run_id": rid, "tool_id": "seo.audit", "status": "partial", "project": None,
        "saved_target": None, "started_at": "2026-11-22T00:00:00Z",
        "finished_at": "2026-11-22T00:00:01Z",
        "parameters": {"source": "https://example.com/", "limit": 35},
        "counts": {"observed": 35, "findings": 32}, "warnings": [],
        "artifacts": ["findings.json"],
    }
    (folder / "run.json").write_text(json.dumps(manifest), encoding="utf-8")
    History(ws).index(folder)
    with TestClient(create_app(ws, 8972), base_url="http://127.0.0.1:8972") as client:
        base = f"/runs/{rid}"
        dom = BeautifulSoup(client.get(base).text, "html.parser")
        pages = dom.find("h2", string="Crawled pages")
        findings_header = dom.find("h2", string="Findings")
        assert len(pages.find_next("ul").find_all("a")) == 30
        assert len(findings_header.find_next("table").find_all("tr")) == 31
        next_pages = dom.find("a", string="Next pages")["href"]
        next_findings = dom.find("a", string="Next findings")["href"]

        page_two = BeautifulSoup(client.get(base + next_pages).text, "html.parser")
        assert len(page_two.find("h2", string="Crawled pages").find_next("ul").find_all("a")) == 5
        assert len(page_two.find("h2", string="Findings").find_next("table").find_all("tr")) == 31
        assert page_two.find("a", string="Previous pages") is not None
        assert page_two.find("a", string="Next findings") is not None

        findings_two = BeautifulSoup(client.get(base + next_findings).text, "html.parser")
        assert len(findings_two.find("h2", string="Crawled pages").find_next("ul").find_all("a")) == 30
        assert len(findings_two.find("h2", string="Findings").find_next("table").find_all("tr")) == 3
        assert findings_two.find("a", string="Previous findings") is not None
        assert findings_two.find("a", string="Next pages") is not None
