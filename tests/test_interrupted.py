"""A run must survive an abandoned tab, a cancellation and a crash."""
import json
import time

from bs4 import BeautifulSoup
from fastapi.testclient import TestClient

from seo_analysis.core.workspace import Workspace
from seo_analysis.storage.history import History
from seo_analysis.ui.server import create_app

ORIGIN = "http://127.0.0.1:8972"


def _prepared(site, tmp_path):
    ws = Workspace(tmp_path / "config", tmp_path / "data", tmp_path / "exports")
    site.add("/robots.txt", f"User-agent: *\nSitemap: {site.base}/map")
    site.add("/map", f"<urlset><url><loc>{site.base}/</loc></url></urlset>")
    site.add("/", "<html><main>Interrupted check</main></html>")
    return ws


def _submit(client, site, token, **extra):
    return client.post("/audit", headers={"Origin": ORIGIN}, follow_redirects=False,
                       data={"url": site.base, "token": token, "local": "on", **extra})


def test_run_is_still_discoverable_when_the_tab_stops_following_it(site, tmp_path):
    """Closing the tab must not lose the run: history keeps it and the job URL stays valid."""
    ws = _prepared(site, tmp_path)
    with TestClient(create_app(ws, 8972), base_url=ORIGIN) as client:
        token = BeautifulSoup(client.get("/").text, "html.parser").select_one("input[name=token]")["value"]
        job = _submit(client, site, token).headers["location"].split("?")[0]
        listing = ""
        for _ in range(150):
            time.sleep(.05)
            listing = client.get("/history").text
            if "/runs/" in listing:
                break
        assert "/runs/" in listing, "the finished run never appeared in history"
        assert client.get(job).status_code == 200


def test_cancelled_run_keeps_what_it_observed_and_a_retry_creates_a_new_run(site, tmp_path):
    ws = _prepared(site, tmp_path)
    with TestClient(create_app(ws, 8972), base_url=ORIGIN) as client:
        token = BeautifulSoup(client.get("/").text, "html.parser").select_one("input[name=token]")["value"]
        headers = {"Origin": ORIGIN}
        first = _submit(client, site, token)
        job = first.headers["location"].split("?")[0]
        assert client.post(f"{job}/cancel", headers=headers, data={"token": token}).status_code == 200
        for _ in range(150):
            reply = client.get(job, follow_redirects=False)
            if reply.status_code == 303:
                break
            time.sleep(.05)
        assert reply.status_code == 303
        cancelled = reply.headers["location"].split("/")[-1]
        manifest = json.loads((ws.runs_dir / cancelled / "run.json").read_text(encoding="utf-8"))
        assert manifest["status"] == "cancelled"
        # The cancelled run keeps whatever it already saved and stays readable.
        assert client.get(f"/runs/{cancelled}").status_code == 200
        # Retrying the same input produces a second, distinct run rather than overwriting.
        second = _submit(client, site, token)
        other = second.headers["location"].split("?")[0]
        for _ in range(150):
            done = client.get(other, follow_redirects=False)
            if done.status_code == 303:
                break
            time.sleep(.05)
        retried = done.headers["location"].split("/")[-1]
        assert retried != cancelled
        assert json.loads((ws.runs_dir / retried / "run.json").read_text(encoding="utf-8"))["status"] in (
            "succeeded", "partial")


def test_a_second_submission_is_refused_while_an_audit_is_running(site, tmp_path):
    """start_audit refuses a queued or running audit, so a double click cannot create two jobs."""
    ws = _prepared(site, tmp_path)

    def slow(_):
        time.sleep(0.8)
        return 200, [("Content-Type", "text/html")], b"<html><main>slow page</main></html>"

    site.routes["/"] = slow
    with TestClient(create_app(ws, 8972), base_url=ORIGIN) as client:
        token = BeautifulSoup(client.get("/").text, "html.parser").select_one("input[name=token]")["value"]
        first = _submit(client, site, token)
        assert first.status_code == 303
        assert _submit(client, site, token).status_code == 409


def test_reindex_reconciles_a_run_left_running_by_a_crash(tmp_path):
    """A process killed mid-crawl leaves status running; reindex must not leave it there."""
    ws = Workspace(tmp_path / "config", tmp_path / "data", tmp_path / "exports")
    rid = "a" * 32
    folder = ws.runs_dir / rid
    (folder / "observations").mkdir(parents=True)
    (folder / "observations" / "page-000001.json").write_text(json.dumps({
        "evidence_id": "page-000001", "url": "https://example.org/",
        "observed_at": "2026-11-20T00:00:00+00:00", "final_status": 200}), encoding="utf-8")
    (folder / "run.json").write_text(json.dumps({
        "run_id": rid, "tool_id": "seo.audit", "status": "running", "project": None, "saved_target": None,
        "started_at": "2026-11-20T00:00:00Z", "finished_at": None,
        "parameters": {"source": "https://example.org/"}, "counts": {}, "warnings": [], "artifacts": []}),
        encoding="utf-8")
    history = History(ws)
    history.index(folder)
    history.reindex()
    recovered = json.loads((folder / "run.json").read_text(encoding="utf-8"))
    assert recovered["status"] in ("partial", "failed")
    assert any("before finalization" in warning for warning in recovered["warnings"])
    assert (folder / "snapshot.jsonl").is_file()
    assert recovered["counts"].get("observed") == 1