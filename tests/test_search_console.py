import json
from pathlib import Path

import pytest

from seo_analysis.cli import main
from seo_analysis.connectors import search_console as gsc
from seo_analysis.connectors.google import APP_NAME, GoogleConnection, SCOPES
from seo_analysis.core.workspace import Workspace


@pytest.fixture
def connected(tmp_path, monkeypatch):
    pytest.importorskip("google_auth_oauthlib")
    config = tmp_path / "config.toml"
    config.write_text('[paths]\ndata_dir = "data"\n', encoding="utf-8")
    workspace = Workspace.load(config)
    connection = GoogleConnection(workspace, None, "gsc")
    connection.history.set_google_connection(None, "gsc", "https://example.test/blog/", "Blog")

    class Vault:
        def get_password(self, service, key):
            assert (service, key) == (APP_NAME, connection.key)
            return json.dumps({"refresh_token": "fake-token", "client_id": "fake-client", "client_secret": "fake-secret"})

    monkeypatch.setattr("seo_analysis.connectors.google.native_keyring", Vault)
    return ["--config-file", str(config), "google"]


def test_search_analytics_cli_paginates_and_keeps_source_dimensions(connected, monkeypatch, capsys, site):
    monkeypatch.setattr(gsc, "BATCH_SIZE", 2)
    requested = []

    def send(session, method, url, *, json):
        assert method == "POST" and "https%3A%2F%2Fexample.test%2Fblog%2F" in url
        assert session.credentials.refresh_token == "fake-token"
        assert session.credentials.scopes == [SCOPES["gsc"]]
        requested.append((json["startRow"], json["rowLimit"]))
        assert json["dimensions"] == ["page", "query", "date", "device", "country"]
        if json["startRow"] == 0:
            keys = ["https://example.test/blog/a", "نمونه", "2026-11-01", "MOBILE", "irn"]
            return {"rows": [{"keys": keys, "clicks": 0}, {"keys": keys, "clicks": 7}],
                    "responseAggregationType": "byPage"}
        return {"rows": []}

    monkeypatch.setattr(gsc, "google_json", send)
    code = main([*connected, "search-analytics", "--start", "2026-11-01", "--end", "2026-11-02",
                 "--dimensions", "page", "query", "date", "device", "country", "--max-rows", "3", "--json"])
    result = json.loads(capsys.readouterr().out)
    assert code == 3 and requested == [(0, 2), (2, 1)]
    assert result["counts"] == {"rows": 1, "received": 2, "skipped": 1, "requests": 2}
    path = Path(result["out_dir"])
    dataset = json.loads((path / "dataset.json").read_text(encoding="utf-8"))
    assert dataset["rows"][0] == {
        "row": 1, "url": "https://example.test/blog/a", "query": "نمونه", "date": "2026-11-01",
        "device": "MOBILE", "country": "irn", "clicks": 0, "impressions": None, "ctr": None, "rank": None,
    }
    assert dataset["source"]["response_aggregation"] == ["byPage"]
    assert result["data_egress"]
    assert all("fake-token" not in file.read_text(encoding="utf-8") for file in path.glob("*.json"))

    from openpyxl import load_workbook

    site.add("/map", f"<urlset><url><loc>{site.base}/</loc></url></urlset>")
    site.add("/", "<main>A local page.</main>")
    prefix = connected[:2]
    assert main([*prefix, "audit", "--sitemap", site.base + "/map", "--allow-local", "--delay", "0", "--json"]) == 0
    crawl = json.loads(capsys.readouterr().out)
    assert main([*prefix, "workbook", "--crawl", crawl["run_id"], "--dataset", result["run_id"], "--json"]) == 3
    workbook_run = json.loads(capsys.readouterr().out)
    with (Path(workbook_run["out_dir"]) / "report.xlsx").open("rb") as file:
        book = load_workbook(file, read_only=True)
        try:
            headers, row = list(book["GSC 1"].values)
            assert headers[-4:] == ("Date", "Device", "Country", "CTR")
            cells = dict(zip(headers, row, strict=False))
            assert [cells.get(field) for field in headers[-4:]] == ["2026-11-01", "MOBILE", "irn", None]
        finally:
            book.close()


@pytest.mark.parametrize("scenario", ["empty", "interrupted", "capped"])
def test_search_analytics_coverage(connected, monkeypatch, capsys, scenario):
    monkeypatch.setattr(gsc, "BATCH_SIZE", 1)

    def send(_, method, url, *, json):
        if scenario == "empty":
            return {}
        if json["startRow"]:
            raise RuntimeError("Google API returned HTTP 429.")
        return {"rows": [{"keys": ["sample", "https://example.test/blog/a"], "clicks": 1}]}

    monkeypatch.setattr(gsc, "google_json", send)
    max_rows = "1" if scenario == "capped" else "2"
    code = main([*connected, "search-analytics", "--start", "2026-11-01", "--end", "2026-11-02",
                 "--max-rows", max_rows, "--json"])
    result = json.loads(capsys.readouterr().out)
    dataset = json.loads((Path(result["out_dir"]) / "dataset.json").read_text(encoding="utf-8"))
    assert code == (0 if scenario == "empty" else 3)
    assert len(dataset["rows"]) == (0 if scenario == "empty" else 1)
    assert dataset["source"]["capped"] == (scenario == "capped")
    assert dataset["source"]["partial"] == (scenario != "empty")


def test_url_inspection_checks_property_before_calling_google(connected, monkeypatch, capsys):
    requests = []

    def send(_, method, endpoint, *, json):
        requests.append((method, endpoint, json))
        return {"inspectionResult": {"indexStatusResult": {"verdict": "PASS"}}}

    monkeypatch.setattr(gsc, "google_json", send)
    for url in ("https://example.test/other", "https://example.test/blog/%2e%2e/other"):
        assert main([*connected, "inspect-url", url, "--json"]) == 2
        result = json.loads(capsys.readouterr().out)
        assert not result["data_egress"]
    assert not requests
    assert main([*connected, "inspect-url", "https://example.test/blog/a", "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert requests == [("POST", gsc.INSPECTION_URL, {
        "inspectionUrl": "https://example.test/blog/a", "siteUrl": "https://example.test/blog/",
    })]
    data = json.loads((Path(result["out_dir"]) / "inspection.json").read_text(encoding="utf-8"))
    assert data["result"]["indexStatusResult"]["verdict"] == "PASS"
