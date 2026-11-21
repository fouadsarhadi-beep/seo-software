import time
from bs4 import BeautifulSoup
from fastapi.testclient import TestClient

from seo_analysis.core.workspace import Workspace
from seo_analysis.ui.server import create_app


def test_ui_end_to_end(site, tmp_path):
    origin = "http://127.0.0.1:8972"
    ws = Workspace(tmp_path / "config", tmp_path / "data", tmp_path / "exports")
    site.add("/robots.txt", f"User-agent: *\nSitemap: {site.base}/map")
    site.add("/map", f"<urlset><url><loc>{site.base}/</loc></url></urlset>")
    site.add("/", "<html><main>Hello world</main></html>")
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
        assert client.get(dom.select_one('a[href*="/evidence/"]')["href"]).status_code == 200
        assert client.get(dom.select_one('a[href$="inventory.csv"]')["href"]).status_code == 200
