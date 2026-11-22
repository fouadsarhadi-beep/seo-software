from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sqlite3

from filelock import FileLock
import pytest

from seo_analysis import cli
from seo_analysis.app.operations import AnalysisInput
from seo_analysis.app.runner import ToolRunner
from seo_analysis.core import tools
from seo_analysis.core.workspace import Workspace
from seo_analysis.storage.history import History, MIGRATIONS
from seo_analysis.web.crawl import CrawlConfig


def workspace(tmp_path):
    return Workspace(tmp_path / "config.toml", tmp_path / "data", tmp_path / "exports")


def test_saved_target_history_and_offline_replay(tmp_path, site, monkeypatch, capsys):
    ws = workspace(tmp_path)
    ws.config_file.write_text('[paths]\ndata_dir = "data"')
    def command(*args):
        code = cli.main(["--config-file", str(ws.config_file), *args, "--json"])
        output = json.loads(capsys.readouterr().out)
        assert code == 0, output
        return output
    command("project", "create", "SEO team")
    command("target", "add", "blog", site.base + "/map", "--kind", "sitemap", "--project", "SEO team")
    site.add("/map", f"<urlset><url><loc>{site.base}/one</loc></url></urlset>")
    site.add("/one", "<html><title>Example</title><main>content</main></html>")
    audit = command("audit", "--project", "SEO team", "--target", "blog", "--allow-local", "--delay", "0")
    db = History(ws)
    hits = dict(site.hits)
    offline = ToolRunner(ws).run(tools.ANALYZE, AnalysisInput(audit["out_dir"]), project="SEO team", log=lambda _: None)
    assert site.hits == hits and offline.status == "succeeded" and offline.data_egress == []
    assert offline.run_id != audit["run_id"]
    detail = command("history", "show", audit["run_id"])
    assert detail["evidence"][0]["url"] == site.base + "/one"
    assert {a["path"] for a in detail["artifacts"]} >= {"findings.csv", "snapshot.jsonl", "requests.json"}
    assert audit["data_egress"][0]["attempt_log"] == "requests.json"
    assert len(command("history", "list", "--project", "SEO team")) == 2
    # Rebuild a lost index using authoritative manifests, including project affiliations.
    db.path.unlink()
    assert command("history", "reindex")["indexed"] == 2
    assert db.selection("SEO team", "blog")["url"] == site.base + "/map"
    assert command("history", "show", audit["run_id"]) == detail


def test_interrupted_run_recovery_and_active_writer(tmp_path, site):
    ws = workspace(tmp_path)
    site.add("/map", f"<urlset><url><loc>{site.base}/one</loc></url></urlset>")
    site.add("/one", "<html><p>one</p></html>")
    result = ToolRunner(ws).run(tools.CRAWL, CrawlConfig(site.base + "/map", "", allow_local=True, delay=0))
    history = History(ws)
    directory = Path(result.out_dir)
    manifest_file = directory / "run.json"
    manifest = json.loads(manifest_file.read_text())
    manifest.update(status="running", finished_at=None, artifacts=[], counts={})
    manifest_file.write_text(json.dumps(manifest))
    (directory / "snapshot.jsonl").unlink()
    with FileLock(str(directory / ".active.lock")):
        assert history.reindex()["active"] == 1
        assert json.loads(manifest_file.read_text())["status"] == "running"
    assert history.reindex()["recovered"] == 1
    assert history.reindex()["recovered"] == 0
    assert history.show(result.run_id)["manifest"]["status"] == "partial"
    assert json.loads((directory / "snapshot.jsonl").read_text())["evidence_id"] == "page-000001"


def test_migration_is_concurrent_and_rejects_newer_schema(tmp_path):
    db = History(workspace(tmp_path))
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(db.add_project, ["one", "two", "three", "four"]))
    assert len(db.projects()) == 4
    with sqlite3.connect(db.path) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == len(MIGRATIONS)
        conn.execute("PRAGMA user_version=40")
    with pytest.raises(ValueError, match="newer"):
        db.projects()


def test_saved_target_does_not_grant_private_network_access(site, tmp_path):
    ws = workspace(tmp_path)
    db = History(ws)
    db.add_project("team")
    db.add_target("team", "local", "website", site.base)
    result = ToolRunner(ws).run(tools.AUDIT, CrawlConfig(site.base, "", kind="website", delay=0),
                                project="team", saved_target="local")
    assert result.status == "failed" and not site.hits
