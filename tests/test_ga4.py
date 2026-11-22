from contextlib import contextmanager
import json
from pathlib import Path

from openpyxl import load_workbook

from seo_analysis.cli import main
from seo_analysis.connectors import ga4


def _row(path, sessions, events):
    return {
        "dimensionValues": [{"value": path}],
        "metricValues": [{"value": events}, {"value": sessions}],
    }


def _response(rows, total, metadata=None):
    return {
        "dimensionHeaders": [{"name": ga4.DIMENSION}],
        "metricHeaders": [{"name": "keyEvents"}, {"name": "sessions"}],
        "rowCount": total,
        "rows": rows,
        "metadata": metadata or {},
        "propertyQuota": {"tokensPerDay": {"remaining": 100}},
    }


def _connected(tmp_path, monkeypatch):
    config = tmp_path / "config.toml"
    config.write_text('[paths]\ndata_dir = "data"\n', encoding="utf-8")

    @contextmanager
    def session(connection):
        assert connection.service == "ga4"
        yield "properties/123", object()

    monkeypatch.setattr(ga4.GoogleConnection, "session", session)
    return ["--config-file", str(config)]


def test_ga4_paginates_preserves_measurements_and_records_ga4_coverage(tmp_path, monkeypatch, capsys):
    prefix = _connected(tmp_path, monkeypatch)
    monkeypatch.setattr(ga4, "BATCH_SIZE", 2)
    requests = []

    def send(_, method, url, *, json):
        assert method == "POST" and url == f"{ga4.API}/properties/123:runReport"
        requests.append((json["offset"], json["limit"]))
        filters = json["dimensionFilter"]["andGroup"]["expressions"]
        assert {f["filter"]["fieldName"]: f["filter"]["stringFilter"]["value"] for f in filters} == {
            "platform": "web", "streamId": "456", "sessionDefaultChannelGroup": "Organic Search",
        }
        if json["offset"] == "0":
            return _response([_row("/a?ref=1", "10", "2.5"), _row("/b", "0", None)], 3,
                             {"subjectToThresholding": True, "timeZone": "Asia/Tehran"})
        return _response([_row("/c", "20", "0")], 3, {"subjectToThresholding": False})

    monkeypatch.setattr(ga4, "google_json", send)
    assert main([*prefix, "google", "landing-pages", "--start", "2026-11-01", "--end", "2026-11-03",
                 "--origin", "https://example.test/", "--stream-id", "456", "--channel", "Organic Search",
                 "--max-rows", "3", "--json"]) == 3
    result = json.loads(capsys.readouterr().out)
    dataset = json.loads((Path(result["out_dir"]) / "dataset.json").read_text(encoding="utf-8"))
    assert requests == [("0", "2"), ("2", "1")]
    assert dataset["rows"] == [
        {"row": 1, "url": "/a?ref=1", "sessions": 10, "conversions": 2.5},
        {"row": 2, "url": "/b", "sessions": 0, "conversions": None},
        {"row": 3, "url": "/c", "sessions": 20, "conversions": 0},
    ]
    source = dataset["source"]
    assert source["landing_origin"] == "https://example.test"
    assert source["response_metadata"] == {"subjectToThresholding": True, "timeZone": "Asia/Tehran"}
    assert source["property_quota"]["tokensPerDay"]["remaining"] == 100
    assert source["partial"] and not source["capped"]


def test_live_ga4_path_requires_origin_and_canonical_ambiguity_is_preserved(
        site, tmp_path, monkeypatch, capsys):
    prefix = _connected(tmp_path, monkeypatch)
    paths = ["a", "b", "start?ref=1"]
    sitemap = "<urlset>" + "".join(f"<url><loc>{site.base}/{path}</loc></url>" for path in paths) + "</urlset>"
    site.add("/map", sitemap)
    for path in ("a", "b"):
        site.add("/" + path, '<link rel="canonical" href="/canonical"><main>Page text</main>')
    site.add("/start", "<main>Landing page</main>")
    assert main([*prefix, "audit", "--sitemap", site.base + "/map", "--allow-local", "--delay", "0", "--json"]) == 0
    audit = json.loads(capsys.readouterr().out)
    monkeypatch.setattr(ga4, "google_json", lambda *args, **kwargs: _response([
        _row("/canonical", "5", "1"), _row("/start?ref=1", "8", "2"), _row("(not set)", "3", "0"),
    ], 3))

    runs = []
    for origin_args in ([], ["--origin", site.base]):
        assert main([*prefix, "google", "landing-pages", "--start", "2026-11-01", "--end", "2026-11-03",
                     *origin_args, "--json"]) == 0
        runs.append(json.loads(capsys.readouterr().out)["run_id"])

    gsc = tmp_path / "gsc.csv"
    gsc.write_text(f"Page,Clicks,Impressions\n{site.base}/canonical,0,9\n", encoding="utf-8")
    assert main([*prefix, "import-data", str(gsc), "--kind", "gsc", "--provider", "test",
                 "--observed", "2026-11-03", "--json"]) == 0
    gsc_run = json.loads(capsys.readouterr().out)["run_id"]
    assert main([*prefix, "workbook", "--crawl", audit["run_id"], "--dataset", runs[0], "--dataset", runs[1],
                 "--dataset", gsc_run, "--json"]) == 0
    workbook = json.loads(capsys.readouterr().out)
    assert workbook["counts"]["matches"] == {
        "landing origin unknown": 2, "unknown landing page": 2, "ambiguous": 2, "requested": 1,
    }
    report = load_workbook(Path(workbook["out_dir"]) / "report.xlsx", read_only=True)
    try:
        first = report["GA4 1"].values
        assert next(first)[1] == "Source URL"
        assert next(first)[2] == "landing origin unknown"
        second = report["GA4 2"].values
        headers = next(second)
        ambiguous = dict(zip(headers, next(second)))
        assert ambiguous["Match"] == "ambiguous"
        assert ambiguous["Match tier"] == "declared canonical"
        assert ambiguous["Candidate URL"] == site.base + "/canonical"
        assert len(ambiguous["Crawl evidence"].split(", ")) == 2
        assert dict(zip(headers, next(second)))["Key events"] == 2
        gsc_values = report["GSC 3"].values
        gsc_row = dict(zip(next(gsc_values), next(gsc_values)))
        assert gsc_row["Match"] == "ambiguous" and gsc_row["Crawl evidence"] == ambiguous["Crawl evidence"]
        assert gsc_row["Clicks"] == 0 and gsc_row.get("Sessions") is None
    finally:
        report.close()


def test_ga4_retains_pages_after_quota_error(tmp_path, monkeypatch, capsys):
    prefix = _connected(tmp_path, monkeypatch)
    monkeypatch.setattr(ga4, "BATCH_SIZE", 1)

    def send(_, method, url, *, json):
        if json["offset"] == "0":
            return _response([_row("/a", "15", "3")], 3)
        raise RuntimeError("Google API returned HTTP 429.")

    monkeypatch.setattr(ga4, "google_json", send)
    assert main([*prefix, "google", "landing-pages", "--start", "2026-11-01", "--end", "2026-11-03", "--json"]) == 3
    manifest = json.loads(capsys.readouterr().out)
    assert manifest["counts"]["rows"] == 1
    assert manifest["counts"]["reported"] == 3
    assert any("429" in warning for warning in manifest["warnings"])
