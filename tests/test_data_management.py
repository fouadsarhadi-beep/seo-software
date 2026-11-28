from dataclasses import asdict
import sqlite3

from bs4 import BeautifulSoup
from fastapi.testclient import TestClient
from filelock import FileLock

from seo_analysis import cli
from seo_analysis.app.runner import ToolResult, timestamp
from seo_analysis.core.artifacts import write_json
from seo_analysis.core.tools import AUDIT, CHECK
from seo_analysis.core.workspace import Workspace
from seo_analysis.storage.history import History
from seo_analysis.storage import removal
from seo_analysis.ui.server import create_app

ORIGIN = "http://127.0.0.1:8765"


def create_saved_run(history, tool, *, project=None):
    directory = history.workspace.create_run_directory()
    report = directory / "findings.csv"
    report.write_text("audit output", encoding="utf-8")
    (directory / "observations").mkdir()
    write_json(directory / "observations" / "page-000001.json", {
        "evidence_id": "page-000001", "url": "https://example.com/", "observed_at": timestamp(),
    })
    run = ToolResult(directory.name, tool.id, str(directory), {}, project, None, finished_at=timestamp(),
                     status="succeeded", artifacts=[report.name])
    write_json(directory / "run.json", asdict(run))
    history.index(directory)
    return directory


def csrf(response):
    return BeautifulSoup(response.text, "html.parser").select_one("input[name=token]")["value"]


def test_remove_one_run_and_retry_files_without_reindexing(tmp_path, monkeypatch):
    history = History(Workspace(tmp_path / "config.toml", tmp_path / "data", tmp_path / "exports"))
    first, second = (create_saved_run(history, AUDIT) for _ in range(2))
    history.set_archived(first.name, True)
    url = f"/runs/{first.name}/delete"
    with TestClient(create_app(history.workspace), base_url=ORIGIN) as client:
        assert url in client.get("/history?archived=true").text
        confirm = client.get(url)
        assert "Delete permanently" in confirm.text and first.is_dir()
        data = {"token": csrf(confirm), "confirm": "delete"}
        headers = {"Origin": ORIGIN}
        assert client.post(url, data=data).status_code == 403
        assert client.post(url, data={"token": data["token"]}, headers=headers).status_code == 400
        with FileLock(str(second / ".active.lock")):
            with history.transaction() as db:
                db.execute("UPDATE runs SET finished=NULL WHERE id=?", (second.name,))
            assert client.post(url, data=data, headers=headers).status_code == 409
        assert first.is_dir()

        with monkeypatch.context() as patch:
            def locked(_):
                raise PermissionError("locked by another process")
            patch.setattr(removal.shutil, "rmtree", locked)
            pending = client.post(url, data=data, headers=headers)
        assert "Retry file cleanup" in pending.text
        assert client.get(f"/runs/{first.name}").status_code == 404
        assert client.get(f"/runs/{first.name}/files/findings.csv").status_code == 404
        assert first.is_dir() and second.is_dir()
        assert history.reindex()["indexed"] == 1
        assert [row["id"] for row in history.list_runs()] == [second.name]
        assert "Saved data deleted" in client.post("/history/data/retry", data=data, headers=headers).text
        assert not first.exists() and second.is_dir()
        assert removal.pending_removals(history) == 0


def test_bulk_audit_delete_and_workspace_reset(tmp_path):
    ws = Workspace(tmp_path / "config.toml", tmp_path / "data", tmp_path / "exports")
    history = History(ws)
    history.add_project("Team", website="https://example.com")
    history.save_audit_workflow("schedule", "Team", "Website", "Monthly", 20, False)
    history.set_google_connection("Team", "gsc", "sc-domain:example.com", "Example")
    audit = create_saved_run(history, AUDIT, project="Team")
    other = create_saved_run(history, CHECK, project="Team")
    history.set_archived(audit.name, True)
    orphan = ws.create_run_directory()
    (ws.data_dir / "decisions.jsonl").write_text("saved decisions", encoding="utf-8")
    receipts = ws.data_dir / "sheets-publications"
    receipts.mkdir()
    (receipts / "receipt.json").write_text("{}", encoding="utf-8")
    ws.export_dir.mkdir()
    exported = ws.export_dir / "outside.csv"
    exported.write_text("download", encoding="utf-8")

    with TestClient(create_app(ws), base_url=ORIGIN) as client:
        def delete(scope):
            url = f"/history/data/{scope}"
            confirmation = client.get(url)
            assert confirmation.status_code == 200
            response = client.post(url, data={"token": csrf(confirmation), "confirm": "delete"},
                                   headers={"Origin": ORIGIN})
            assert response.status_code == 200 and "Saved data deleted" in response.text

        delete("audits")
        assert not audit.exists() and other.is_dir() and orphan.is_dir()
        assert history.projects() and history.audit_workflows()
        delete("runs")
        assert history.list_runs() == [] and not other.exists() and not orphan.exists()
        assert history.projects() and (ws.data_dir / "decisions.jsonl").is_file()
        create_saved_run(history, AUDIT, project="Team")
        delete("workspace")
        assert history.list_runs() == history.projects() == history.audit_workflows() == []
        assert history.google_connection("Team", "gsc") is None
        assert not list(ws.runs_dir.iterdir()) and not receipts.exists()
        assert not (ws.data_dir / "decisions.jsonl").exists()
        assert exported.read_text() == "download"
        history.add_project("New project")


def test_readonly_migration_shows_storage_error_and_cli_recovery_guidance(tmp_path, monkeypatch, capsys):
    config = tmp_path / "config.toml"
    config.write_text('[paths]\ndata_dir = "data"\n', encoding="utf-8")
    ws = Workspace.load(config)
    history = History(ws)
    history.path.parent.mkdir()
    # An existing database needing migrations, as in the Windows traceback.
    connect = sqlite3.connect
    connect(history.path).close()
    monkeypatch.setattr(sqlite3, "connect",
                        lambda path, **kwargs: connect(history.path.as_uri() + "?mode=ro", uri=True, **kwargs))
    with TestClient(create_app(ws), base_url=ORIGIN) as client:
        response = client.get("/")
        assert response.status_code == 503
        assert "Start SEO Workbench.cmd" in response.text
        assert "Workspace unavailable" in response.text
    assert cli.main(["--config-file", str(config), "serve"]) == 2
    error = capsys.readouterr().err
    assert "read-only or inaccessible" in error and "Start SEO Workbench.cmd" in error
