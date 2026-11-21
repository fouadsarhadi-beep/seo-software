import json
import os
from pathlib import Path
import subprocess
import sysconfig


def test_installed_console_one_off_audit_then_offline_analysis_and_history(tmp_path, site):
    console = Path(sysconfig.get_path("scripts")) / ("seo-analysis.exe" if os.name == "nt" else "seo-analysis")
    cwd = tmp_path / "پروژه SEO"
    cwd.mkdir()
    config = cwd / "settings.toml"
    config.write_text('[paths]\ndata_dir="local data"', encoding="utf-8")
    def run(*args):
        result = subprocess.run([console, "--config-file", config, *args, "--json"],
                                cwd=cwd, capture_output=True, text=True, encoding="utf-8")
        assert result.returncode == 0, result.stdout + result.stderr
        return json.loads(result.stdout)
    site.add("/robots.txt", "User-agent: *")
    site.add("/", "<html><title>آزمایش</title><main>متن صفحه</main></html>")
    first = run("audit", site.base, "--link-crawl", "--allow-local", "--delay", "0")
    assert first["project"] is None and first["counts"]["findings"] > 0
    hits = dict(site.hits)
    second = run("analyze", "--in-dir", first["out_dir"])
    assert hits == dict(site.hits) and second["counts"]["source_status"] == "succeeded"
    assert [r["id"] for r in run("history", "list")] == [second["run_id"], first["run_id"]]
    assert run("history", "show", first["run_id"])["evidence"][0]["url"].rstrip("/") == site.base
