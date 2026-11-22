import json
import time
from threading import Event
from bs4 import BeautifulSoup
from fastapi.testclient import TestClient

from seo_analysis.core.workspace import Workspace
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
