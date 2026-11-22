import json
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

from seo_analysis.cli import main
from seo_analysis.connectors import wordpress
from seo_analysis.core.network import HttpOrigin
from seo_analysis.core.workspace import Workspace
from seo_analysis.web.fetch import Fetcher, FetchResult
from test_google_connections import Vault


def _workspace(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('[paths]\ndata_dir="data"\n', encoding="utf-8")
    return path, ["--config-file", str(path)]


def test_wordpress_inventory_limits_fields_and_keeps_credentials_out_of_artifacts(tmp_path, monkeypatch, capsys):
    cfg, args = _workspace(tmp_path)
    workspace = Workspace.load(cfg)
    vault = Vault()
    monkeypatch.setattr(wordpress, "native_keyring", lambda extra: vault)
    root = "https://example.com/blog"
    wordpress.credentials(workspace, None, root + "/", account="dedicated-reader", password="private-password")
    expected = ("dedicated-reader", "private-password")
    calls = []

    class FixtureFetcher:
        def __init__(self, agent, *, origin, **kwargs):
            assert origin == HttpOrigin.from_url(root)
            self.attempts = []
            self.session = SimpleNamespace(close=lambda: None, auth=None)

        def get(self, url, *, follow_redirects, header_names):
            assert self.session.auth == expected
            assert follow_redirects is False and header_names == ("X-WP-Total",)
            self.attempts.append({"method": "GET", "url": url, "http_status": 200})
            parts = urlsplit(url)
            assert parts.path == "/blog/wp-json/wp/v2/posts"
            params = parse_qs(parts.query)
            assert params["context"] == ["view"] and params["status"] == ["publish"]
            assert "content" not in params["_fields"][0].split(",")
            offset, size = int(params["offset"][0]), int(params["per_page"][0])
            calls.append((offset, size))
            batch = [
                {"id": index + 1, "status": "publish", "slug": "sample", "link": root + "/sample",
                 "title": {"rendered": "عنوان &amp; متن"}, "ignored": "private field",
                 "yoast_head_json": {"canonical": root + "/canonical", "robots": {"index": "index"}}}
                for index in range(offset, offset + size)
            ]
            return FetchResult(url, final_status=200, raw=json.dumps(batch).encode(),
                               selected_headers={"X-WP-Total": "12"})

    monkeypatch.setattr(wordpress, "PAGE_SIZE", 2)
    monkeypatch.setattr(wordpress, "Fetcher", FixtureFetcher)
    assert main([*args, "wordpress", "inventory", root, "--authenticated", "--max-items", "3", "--json"]) == 3
    run = json.loads(capsys.readouterr().out)
    assert calls == [(0, 2), (2, 1)]
    assert run["counts"] == {"items": 3, "skipped": 0}
    assert run["data_egress"][0]["authenticated"] is True
    directory = Path(run["out_dir"])
    content = (directory / "wordpress.json").read_text(encoding="utf-8")
    first = json.loads(content)["items"][0]
    assert first["title"] == "عنوان & متن" and first["plugin_canonical"] == root + "/canonical"
    for file in directory.iterdir():
        if file.suffix in (".json", ".csv"):
            data = file.read_text(encoding="utf-8-sig")
            assert "private-password" not in data and "dedicated-reader" not in data and "private field" not in data
    assert main([*args, "wordpress", "inventory", "https://example.com/other", "--authenticated", "--json"]) == 2
    attempt = json.loads(capsys.readouterr().out)
    assert attempt["data_egress"] == []
    assert main([*args, "wordpress", "forget", root]) == 0 and not vault.records


def test_opt_in_header_capture_and_redirect_stop_on_real_fetcher(site):
    site.add("/api", "{}", headers=[("X-WP-Total", "1"), ("Set-Cookie", "hidden=1")])
    site.redirect("/redirect", "/api")
    fetcher = Fetcher("test", origin=HttpOrigin.from_url(site.base), allow_local=True, delay=0)
    try:
        blocked = fetcher.get(site.base + "/redirect", follow_redirects=False)
        assert blocked.redirect_note == "redirect_not_followed" and blocked.final_status == 301
        assert "/api" not in site.hits
        result = fetcher.get(site.base + "/api", follow_redirects=False, header_names=("X-WP-Total",))
        assert result.selected_headers == {"X-WP-Total": "1"}
    finally:
        fetcher.session.close()
