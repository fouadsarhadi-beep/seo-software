import json
import socket
from pathlib import Path

import pytest

from seo_analysis import cli
from seo_analysis.core.network import HttpOrigin
from seo_analysis.core.urls import url_key
from seo_analysis.web.fetch import Fetcher
from seo_analysis.web.transport import ScopeError


def run_cli(tmp_path, capsys, *args):
    config = tmp_path / "settings.toml"
    config.write_text('[paths]\ndata_dir="data"', encoding="utf-8")
    code = cli.main(["--config-file", str(config), "audit", "--json", "--delay", "0", *args])
    return code, json.loads(capsys.readouterr().out)


def test_website_fallback_evidence(site, tmp_path, capsys):
    site.add("/", '<html><a href="/مقاله">A</a><a href="/?p=1">B</a><a href="/?p=2">C</a></html>')
    site.add("/مقاله", "<article>مقاله</article>")
    code, result = run_cli(tmp_path, capsys, site.base, "--link-crawl", "--allow-local", "--max-variants", "1")
    assert code == 3 and result["status"] == "partial"
    directory = Path(result["out_dir"])
    observations = list((directory / "observations").glob("*.json"))
    assert len(observations) == 3
    findings = json.loads((directory / "findings.json").read_text())["findings"]
    assert findings and all((directory / "observations" / (eid + ".json")).exists()
                            for finding in findings for eid in finding["evidence_ids"])


def test_request_limit_includes_discovery(site, tmp_path, capsys):
    code, result = run_cli(tmp_path, capsys, site.base, "--allow-local", "--max-requests", "1")
    assert code == 3 and result["counts"]["requests"] == 1
    assert sum(site.hits.values()) == 1


def test_public_dns_policy(monkeypatch):
    # Fake resolver provides a different answer on successive resolutions.
    from seo_analysis.web import transport
    calls = []
    def resolve(*args, **kwargs):
        calls.append(args[0])
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80))]
    monkeypatch.setattr(transport.socket, "getaddrinfo", resolve)
    origin = HttpOrigin.from_url("http://example.test")
    with pytest.raises(ScopeError):
        Fetcher("test", origin=origin).get("http://example.test/page")
    assert calls == ["example.test"]


def test_reserved_characters_preserve_page_identity():
    assert url_key("https://example.org/a%2Fb") != url_key("https://example.org/a/b")
    assert url_key("https://example.org/?q=x%26y") != url_key("https://example.org/?q=x&y")


def test_seed_csv_and_sitemap_discovery(site, tmp_path, capsys):
    site.add("/robots.txt", f"User-agent: *\nSitemap: {site.base}/custom-map")
    site.add("/custom-map", f"<urlset><url><loc>{site.base}/hello</loc></url></urlset>", ctype="application/xml")
    site.add("/hello", "<html><main>hello</main></html>")
    assert run_cli(tmp_path, capsys, site.base, "--allow-local")[0] == 0
    seeds = tmp_path / "seeds.csv"
    seeds.write_text("URL\n" + site.base + "/hello")
    code, result = run_cli(tmp_path, capsys, "--urls-file", str(seeds), "--allow-local")
    assert code == 0 and result["counts"]["observed"] == 1


def test_pinned_socket_uses_one_resolution(monkeypatch):
    from seo_analysis.web import transport
    from seo_analysis.web.transport import CrawlBudget, scoped_adapter
    answers = iter(["93.184.216.34", "127.0.0.1"])
    connected = []
    def resolve(host, port, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (next(answers), port))]
    class TestSocket:
        def settimeout(self, value):
            pass
        def connect(self, sockaddr):
            connected.append(sockaddr)
    monkeypatch.setattr(transport.socket, "getaddrinfo", resolve)
    monkeypatch.setattr(transport.socket, "socket", lambda *args: TestSocket())
    origin = HttpOrigin.from_url("https://example.test")
    adapter = scoped_adapter(origin, False, CrawlBudget(2, 10))
    connection = adapter.poolmanager.connection_from_url("https://example.test").ConnectionCls(origin.host, timeout=1)
    connection._new_conn()
    assert connected == [("93.184.216.34", 443)]
    with pytest.raises(ScopeError):
        connection._new_conn()
    assert len(connected) == 1


def test_cancellation_preserves_completed_page(site, tmp_path, monkeypatch, capsys):
    from seo_analysis.web import crawl
    site.add("/map", f"<urlset><url><loc>{site.base}/a</loc></url><url><loc>{site.base}/b</loc></url></urlset>")
    site.add("/a", "<html><title>A</title></html>")
    observe = crawl.observe
    def interrupt(cfg, fetcher, policy, entry, *args):
        if entry.url.endswith("/b"):
            raise KeyboardInterrupt()
        return observe(cfg, fetcher, policy, entry, *args)
    monkeypatch.setattr(crawl, "observe", interrupt)
    code, result = run_cli(tmp_path, capsys, "--sitemap", site.base + "/map", "--allow-local")
    assert code == 130 and result["status"] == "cancelled"
    directory = Path(result["out_dir"])
    assert json.loads((directory / "snapshot.jsonl").read_text())["url"].endswith("/a")
    assert len(list((directory / "observations").glob("*.json"))) == 1


def test_no_sitemap_and_invalid_sitemap_are_visible(site, tmp_path, capsys):
    site.add("/bad.xml", "<xml")
    code, result = run_cli(tmp_path, capsys, "--sitemap", site.base + "/bad.xml", "--allow-local")
    assert code == 2 and result["status"] == "no_pages_found"
    assert any("malformed" in w for w in result["warnings"])


def test_url_and_sitemap_are_mutually_exclusive(site, tmp_path, capsys):
    code, result = run_cli(tmp_path, capsys, site.base, "--sitemap", site.base)
    assert code == 2 and not site.hits
