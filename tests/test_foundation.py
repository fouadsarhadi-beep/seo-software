import json
from pathlib import Path
import subprocess
import sys

import pytest

from seo_analysis import cli
from seo_analysis.core.network import HttpOrigin
from seo_analysis.core.workspace import ConfigurationError, Workspace
from seo_analysis.web.fetch import Fetcher


def test_installed_cli_doctor_outside_checkout(tmp_path):
    config = tmp_path / "سئو settings.toml"
    config.write_text('[paths]\ndata_dir = "site data"\nexport_dir = "reports"', encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "seo_analysis", "--config-file", str(config), "system", "doctor", "--json"],
        cwd=tmp_path, capture_output=True, text=True, encoding="utf-8", check=True,
    )
    facts = json.loads(result.stdout)
    assert facts["config_loaded"] and facts["tool_id"] == "system.doctor"
    assert Path(facts["runs_dir"]) == tmp_path / "site data" / "runs"
    assert Path(facts["export_dir"]) == tmp_path / "reports"
    assert not Path(facts["data_dir"]).exists()


@pytest.mark.parametrize("content", ["invalid TOML", "unknown = 1", '[paths]\ndata_dir = 3'])
def test_invalid_config(tmp_path, content):
    path = tmp_path / "config.toml"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ConfigurationError):
        Workspace.load(path)


def test_missing_sitemap_does_not_create_run(tmp_path, capsys):
    path = tmp_path / "config.toml"
    path.write_text('[paths]\ndata_dir = "data"', encoding="utf-8")
    assert cli.main(["--config-file", str(path), "crawl", "--yes"]) == 2
    assert "--sitemap" in capsys.readouterr().err
    assert not (tmp_path / "data").exists()


def test_default_crawl_isolated_by_run(site, tmp_path):
    config = tmp_path / "config.toml"
    config.write_text('[paths]\ndata_dir = "داده ها"', encoding="utf-8")
    site.add("/robots.txt", "User-agent: *", ctype="text/plain")
    site.add("/sitemap.xml", f"<urlset><url><loc>{site.base}/page</loc></url></urlset>", ctype="application/xml")
    site.add("/page", "<html><main>محتوای تست</main></html>")
    args = ["--config-file", str(config), "crawl", "--yes", "--allow-local", "--sitemap", site.base + "/sitemap.xml", "--delay", "0"]
    assert cli.main(args) == 0
    assert cli.main(args) == 0
    runs = list((tmp_path / "داده ها" / "runs").iterdir())
    assert len(runs) == 2
    for directory in runs:
        assert (directory / "snapshot.jsonl").is_file()
    assert cli.main(["--config-file", str(config), "analyze", "--in-dir", str(runs[0]), "--yes"]) == 0
    replays = set(runs[0].parent.iterdir()) - set(runs)
    assert len(replays) == 1 and (replays.pop() / "analysis_manifest.json").exists()
    assert not (runs[1] / "analysis_manifest.json").exists()


def test_initial_request_obeys_origin(site):
    origin = HttpOrigin.from_url(site.base.replace("127.0.0.1", "localhost"))
    result = Fetcher("test", origin=origin).get(site.base + "/outside")
    assert result.redirect_note.startswith("blocked_external")
    assert site.hits["/outside"] == 0


def test_unicode_origin_uses_transport_hostname():
    origin = HttpOrigin.from_url("https://faß.example")
    assert origin.allows("https://xn--fa-hia.example/article")
    assert not origin.allows("https://fass.example/article")


def test_tool_catalogue_describes_runnable_commands(capsys):
    assert cli.main(["tools", "list", "--json"]) == 0
    catalogue = json.loads(capsys.readouterr().out)
    assert len({tool["id"] for tool in catalogue}) == len(catalogue)
    assert {tool["command"] for tool in catalogue if tool["uses_network"]} == {
        "crawl", "audit", "google search-analytics", "google inspect-url", "google landing-pages", "google pagespeed", "google crux",
    }
    for tool in catalogue:
        with pytest.raises(SystemExit) as help_exit:
            cli.build_parser().parse_args([*tool["command"].split(), "--help"])
        assert help_exit.value.code == 0
