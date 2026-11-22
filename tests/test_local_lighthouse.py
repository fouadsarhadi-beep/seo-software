from contextlib import contextmanager
from http.client import HTTPConnection
import json
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit

from seo_analysis.analysis import local_lighthouse
from seo_analysis.cli import main


def test_lighthouse_build_server_serves_local_files_and_refuses_proxy_targets(tmp_path):
    root = tmp_path / "build"
    root.mkdir()
    (root / "index.html").write_text("<title>Fixture</title>", encoding="utf-8")
    (tmp_path / "private.txt").write_text("outside build", encoding="utf-8")
    with local_lighthouse.serve_build(root) as (origin, counts):
        address = urlsplit(origin)
        with_client = HTTPConnection(address.hostname, address.port, timeout=3)
        try:
            with_client.request("GET", origin + "/", headers={"Host": address.netloc})
            response = with_client.getresponse()
            assert response.status == 200 and b"Fixture" in response.read()
            with_client.request("GET", "http://example.test/", headers={"Host": "example.test"})
            bad = with_client.getresponse()
            assert bad.status == 403
            bad.read()
            with_client.request("CONNECT", "example.test:443")
            tunnel = with_client.getresponse()
            assert tunnel.status == 403
            tunnel.read()
            with_client.request("GET", "/%2e%2e/private.txt")
            outside = with_client.getresponse()
            assert outside.status == 404
            assert b"outside build" not in outside.read()
        finally:
            with_client.close()
        assert counts["requests"] == 1 and counts["blocked_external"] == 2


def test_lighthouse_run_cli_preserves_raw_and_normalized_lab_reports(tmp_path, monkeypatch, capsys):
    root = tmp_path / "build"
    root.mkdir()
    (root / "index.html").write_text("<title>Fixture</title>", encoding="utf-8")
    cli = tmp_path / "cli.js"
    cli.touch()
    chromium = tmp_path / "chromium"
    chromium.touch()
    config = tmp_path / "config.toml"
    config.write_text('[paths]\ndata_dir="data"\n', encoding="utf-8")

    @contextmanager
    def fake_browser(executable, origin, profile):
        assert Path(executable) == chromium and profile.is_dir()
        assert urlsplit(origin).hostname == "127.0.0.1"
        yield 9229

    def fake_lighthouse(args, *, cwd, timeout, **kwargs):
        assert cwd == root and timeout == 90
        assert args[:2] == ["node", str(cli)]
        assert "--port=9229" in args and "--preset=desktop" in args
        output = next(item.split("=", 1)[1] for item in args if item.startswith("--output-path="))
        Path(output).write_text(json.dumps({
            "finalDisplayedUrl": args[2], "categories": {"performance": {"score": 0.97}},
            "audits": {"largest-contentful-paint": {"numericValue": 1301}},
        }), encoding="utf-8")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(local_lighthouse, "debugging_chromium", fake_browser)
    monkeypatch.setattr(local_lighthouse, "run", fake_lighthouse)
    monkeypatch.setattr(local_lighthouse, "which", lambda name: name)
    code = main(["--config-file", str(config), "lighthouse-run", str(root), "--lighthouse-cli", str(cli),
                 "--chromium", str(chromium), "--device", "desktop", "--json"])
    result = json.loads(capsys.readouterr().out)
    assert code == 0, result
    assert result["data_egress"] == [] and result["artifacts"] == ["lighthouse.json", "performance.json"]
    report = json.loads((Path(result["out_dir"]) / "performance.json").read_text(encoding="utf-8"))
    assert report["kind"] == "lab" and report["metrics"]["LCP"] == {"value": 1301, "unit": "ms"}
