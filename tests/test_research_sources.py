from contextlib import nullcontext
import json
from pathlib import Path

from seo_analysis.cli import main
from seo_analysis.research import sources
from seo_analysis.web.fetch import Fetcher


def _prefix(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text('[paths]\ndata_dir="data"\n', encoding="utf-8")
    return ["--config-file", str(config)]


def _dataset(capsys):
    run = json.loads(capsys.readouterr().out)
    dataset = json.loads((Path(run["out_dir"]) / "dataset.json").read_text(encoding="utf-8"))
    return run, dataset


def test_live_feed_keeps_dates_and_does_not_fetch_linked_pages(site, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sources, "Fetcher", lambda *args, **kwargs: Fetcher(*args, **kwargs, allow_local=True))
    site.add("/robots.txt", "User-agent: *\nDisallow: /blocked")
    site.add("/feed", """<feed xmlns="http://www.w3.org/2005/Atom">
      <entry><title>گزارش</title><link href="/post"/><published>2026-11-20T09:00:00Z</published></entry>
      <entry><title>Next item</title><link href="/next"/></entry>
    </feed>""", ctype="application/atom+xml")
    assert main([*_prefix(tmp_path), "research-feed", site.base + "/feed", "--max-items", "1", "--json"]) == 3
    run, dataset = _dataset(capsys)
    assert dataset["rows"] == [{"row": 1, "title": "گزارش", "url": site.base + "/post",
                                "published": "2026-11-20T09:00:00Z"}]
    assert dataset["source"]["capped"] is True and run["data_egress"]
    assert dict(site.hits) == {"/robots.txt": 1, "/feed": 1}
    assert main([*_prefix(tmp_path), "research-feed", site.base + "/blocked", "--json"]) == 2
    assert "/blocked" not in site.hits


def test_brave_search_stores_one_ranked_sample_with_explicit_permission(tmp_path, monkeypatch, capsys):
    sent = []

    class Response:
        status_code = 200

        def iter_content(self, chunk_size):
            yield json.dumps({"web": {"results": [
                {"url": "https://example.com/", "title": "<strong>Example</strong>"},
                {"url": "javascript:void(0)", "title": "Invalid"},
                {"url": "https://example.org/", "title": "Third"},
            ]}}).encode()

    def get(endpoint, **kwargs):
        sent.append((endpoint, kwargs))
        return nullcontext(Response())

    monkeypatch.setattr(sources, "brave_key", lambda _: "test-key")
    monkeypatch.setattr(sources.requests, "get", get)
    command = [*_prefix(tmp_path), "research-search", "عبارت نمونه", "--country", "us",
               "--language", "en", "--count", "3", "--json"]
    assert main(command) == 2
    assert not sent and "allow-storage" in json.loads(capsys.readouterr().out)["warnings"][0]
    assert main([*command, "--allow-storage"]) == 3
    run, dataset = _dataset(capsys)
    assert [row["rank"] for row in dataset["rows"]] == [1, 3]
    assert dataset["rows"][0]["title"] == "Example"
    assert dataset["source"]["locale"] == "en-US" and dataset["source"]["device"] == ""
    assert "test-key" not in json.dumps(run | dataset)
    endpoint, options = sent[0]
    assert endpoint == sources.BRAVE_URL and options["allow_redirects"] is False
    assert options["headers"]["X-Subscription-Token"] == "test-key"
    assert options["params"]["q"] == "عبارت نمونه"
    assert main([*_prefix(tmp_path), "research", "--dataset", run["run_id"],
                 "--owned-host", "example.com", "--json"]) == 3
    analyzed = json.loads(capsys.readouterr().out)
    data = json.loads((Path(analyzed["out_dir"]) / "research.json").read_text(encoding="utf-8"))
    assert data["keywords"][0]["observations"][0]["evidence"] == {"run_id": run["run_id"], "row": 1}


def _feed_failure(capsys):
    run = json.loads(capsys.readouterr().out)
    return json.loads((Path(run["out_dir"]) / "feed-source.json").read_text(encoding="utf-8"))


def _feed_request(tmp_path, monkeypatch):
    monkeypatch.setattr(sources, "Fetcher", lambda *args, **kwargs: Fetcher(*args, **kwargs, allow_local=True))
    return _prefix(tmp_path)


def test_feed_reports_an_html_page_and_offers_the_feed_it_advertises(site, tmp_path, monkeypatch, capsys):
    prefix = _feed_request(tmp_path, monkeypatch)
    site.add("/robots.txt", "User-agent: *\n")
    site.add("/page", '<!doctype html><html><head><meta charset="utf-8">'
                      '<link rel="alternate" type="application/rss+xml" href="/feed.xml"></head>'
                      "<body>Home</body></html>", ctype="text/html")
    assert main([*prefix, "research-feed", site.base + "/page", "--json"]) == 2
    failure = _feed_failure(capsys)
    assert failure["reason"] == "html"
    assert failure["candidate"] == site.base + "/feed.xml"
    assert "HTML page" in failure["message"]


def test_feed_distinguishes_empty_malformed_and_non_feed_xml(site, tmp_path, monkeypatch, capsys):
    prefix = _feed_request(tmp_path, monkeypatch)
    site.add("/robots.txt", "User-agent: *\n")
    site.add("/empty", "", ctype="application/rss+xml")
    site.add("/broken", "<feed><entry>", ctype="application/atom+xml")
    site.add("/urlset.xml", '<?xml version="1.0"?><urlset><url><loc>https://example.org/</loc></url></urlset>',
             ctype="application/xml")
    for path, reason in (("/empty", "empty"), ("/broken", "malformed"), ("/urlset.xml", "unsupported")):
        assert main([*prefix, "research-feed", site.base + path, "--json"]) == 2
        assert _feed_failure(capsys)["reason"] == reason
    site.add("/urlset2.xml", '<?xml version="1.0"?><urlset/>', ctype="application/xml")
    assert main([*prefix, "research-feed", site.base + "/urlset2.xml", "--json"]) == 2
    failure = _feed_failure(capsys)
    assert failure["detail"] == "urlset" and "<urlset>" in failure["message"]


def test_feed_accepts_a_valid_feed_whose_content_type_is_wrong(site, tmp_path, monkeypatch, capsys):
    prefix = _feed_request(tmp_path, monkeypatch)
    site.add("/robots.txt", "User-agent: *\n")
    site.add("/feed", '<rss version="2.0"><channel><item><title>Item</title><link>/post</link></item>'
                      "</channel></rss>", ctype="text/html")
    assert main([*prefix, "research-feed", site.base + "/feed", "--json"]) == 0
    _, dataset = _dataset(capsys)
    assert [row["title"] for row in dataset["rows"]] == ["Item"]


def test_feed_failure_hides_credentials_and_sensitive_parameters(site, tmp_path, monkeypatch, capsys):
    prefix = _feed_request(tmp_path, monkeypatch)
    site.add("/robots.txt", "User-agent: *\n")
    assert main([*prefix, "research-feed", site.base + "/missing?token=SECRET&lang=fa", "--json"]) == 2
    failure = _feed_failure(capsys)
    assert failure["reason"] == "http" and "404" in failure["message"]
    assert "SECRET" not in json.dumps(failure)
    assert failure["source"] == site.base + "/missing?lang=fa"
    assert failure["hidden_parameters"] == 1
