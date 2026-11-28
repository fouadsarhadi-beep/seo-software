"""Saved material must not leak a signed address or serve a file the run never wrote."""
import json
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from bs4 import BeautifulSoup
from fastapi.testclient import TestClient

from seo_analysis.cli import main
from seo_analysis.core.workspace import Workspace
from seo_analysis.reporting.export import build_bundle
from seo_analysis.research import sources
from seo_analysis.ui.server import create_app
from seo_analysis.web.fetch import Fetcher


def _prefix(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text('[paths]\ndata_dir="data"\n', encoding="utf-8")
    return ["--config-file", str(config)]


def _allow_local(monkeypatch):
    monkeypatch.setattr(sources, "Fetcher", lambda *args, **kwargs: Fetcher(*args, **kwargs, allow_local=True))


def test_bundle_refuses_an_unlisted_file_and_reports_a_missing_one(tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    (run / "snapshot.jsonl").write_text('{"url": "https://example.org/"}\n', encoding="utf-8")
    (run / "inventory.csv").write_text("URL\nhttps://example.org/\n", encoding="utf-8")
    manifest = {"run_id": "r" * 32, "artifacts": ["snapshot.jsonl"]}
    (run / "run.json").write_text(json.dumps(manifest), encoding="utf-8")
    bundle = build_bundle(run, manifest)
    with ZipFile(BytesIO(bundle)) as archive:
        names = set(archive.namelist())
        index = json.loads(archive.read("index.json"))
    assert "crawl/snapshot.jsonl" in names
    assert "crawl/inventory.csv" not in names
    reasons = {item["file"]: item["reason"] for item in index["skipped"]}
    assert "manifest" in reasons["crawl/inventory.csv"]
    assert reasons["analysis/findings.json"] == "not written by this run"


def test_bundle_does_not_follow_a_link_out_of_the_run(tmp_path, monkeypatch):
    """The guard is exercised directly: creating a real link needs elevation on this platform."""
    run = tmp_path / "run"
    run.mkdir()
    (run / "snapshot.jsonl").write_text('{"url": "https://example.org/"}\n', encoding="utf-8")
    (run / "pairs.json").write_text('{"pairs": []}\n', encoding="utf-8")
    manifest = {"run_id": "r" * 32, "artifacts": ["snapshot.jsonl", "pairs.json"]}
    (run / "run.json").write_text(json.dumps(manifest), encoding="utf-8")
    real = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink",
                        lambda self: True if self.name == "pairs.json" else real(self))
    with ZipFile(BytesIO(build_bundle(run, manifest))) as archive:
        names = set(archive.namelist())
        index = json.loads(archive.read("index.json"))
    assert "analysis/pairs.json" not in names
    reasons = {item["file"]: item["reason"] for item in index["skipped"]}
    assert "link" in reasons["analysis/pairs.json"]


def test_a_signed_feed_address_is_not_written_into_the_run(site, tmp_path, monkeypatch, capsys):
    _allow_local(monkeypatch)
    site.add("/robots.txt", "User-agent: *\n")
    site.add("/feed", "<rss><channel><item><title>Item</title><link>/p</link></item></channel></rss>",
             ctype="application/rss+xml")
    url = site.base + "/feed?token=SECRET&lang=fa"
    assert main([*_prefix(tmp_path), "research-feed", url, "--json"]) in (0, 3)
    run = json.loads(capsys.readouterr().out)
    out = Path(run["out_dir"])
    dataset = json.loads((out / "dataset.json").read_text(encoding="utf-8"))
    requests_log = json.loads((out / "requests.json").read_text(encoding="utf-8"))
    manifest = json.loads((out / "run.json").read_text(encoding="utf-8"))
    for saved in (dataset, requests_log, manifest):
        assert "SECRET" not in json.dumps(saved)
    assert dataset["source"]["url"].endswith("?lang=fa")
    assert manifest["parameters"]["url"].endswith("?lang=fa")


def test_a_failed_signed_feed_hides_the_token_and_explains_re_entry(site, tmp_path, monkeypatch, capsys):
    _allow_local(monkeypatch)
    site.add("/robots.txt", "User-agent: *\n")
    url = site.base + "/missing?token=SECRET&lang=fa"
    assert main([*_prefix(tmp_path), "research-feed", url, "--json"]) == 2
    run = json.loads(capsys.readouterr().out)
    out = Path(run["out_dir"])
    assert "SECRET" not in (out / "feed-source.json").read_text(encoding="utf-8")
    ws = Workspace.load(tmp_path / "config.toml")
    with TestClient(create_app(ws, 8972), base_url="http://127.0.0.1:8972") as client:
        page = client.get(f"/runs/{run['run_id']}").text
        shown = BeautifulSoup(page, "html.parser").get_text(" ", strip=True)
    assert "SECRET" not in page
    assert "Feed import failed" in shown
    assert "paste the full address again" in shown.lower()