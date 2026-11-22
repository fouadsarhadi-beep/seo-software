from contextlib import contextmanager
import csv
import json
from pathlib import Path
from types import SimpleNamespace

from openpyxl import load_workbook
import pytest

from seo_analysis.cli import main
from seo_analysis.connectors import google, sheets
from test_google_connections import Vault


def _preview(tmp_path, capsys):
    config = tmp_path / "config.toml"
    config.write_text('[paths]\ndata_dir = "data"\n', encoding="utf-8")
    prefix = ["--config-file", str(config)]
    csv_file = tmp_path / "gsc.csv"
    csv_file.write_text("Query,Page,Clicks,Impressions\n=sample,https://example.com/a,0,5\n"
                        "test,https://example.com/b,,2\n", encoding="utf-8")
    assert main([*prefix, "import-data", str(csv_file), "--kind", "gsc", "--provider", "Test",
                 "--observed", "2026-11-22", "--json"]) == 0
    dataset = json.loads(capsys.readouterr().out)
    assert main([*prefix, "export-dataset", "--dataset", dataset["run_id"], "--title", "Search report",
                 "--column", "query", "--column", "clicks", "--json"]) == 0
    export = json.loads(capsys.readouterr().out)
    directory = Path(export["out_dir"])
    summary = json.loads((directory / "export.json").read_text(encoding="utf-8"))
    return prefix, export, directory, summary


def test_selected_export_is_offline_and_keeps_zero_and_missing_values(tmp_path, capsys):
    _, export, directory, summary = _preview(tmp_path, capsys)
    assert export["data_egress"] == [] and summary["columns"] == ["query", "clicks"]
    with (directory / "selected.csv").open(encoding="utf-8-sig", newline="") as file:
        assert list(csv.reader(file)) == [["query", "clicks"], ["'=sample", "0.0"], ["test", ""]]
    book = load_workbook(directory / "selected.xlsx", read_only=True)
    try:
        assert list(book["Data"].values) == [("query", "clicks"), ("'=sample", 0), ("test",)]
    finally:
        book.close()


def test_sheets_requires_review_and_resumes_known_spreadsheet(tmp_path, monkeypatch, capsys):
    prefix, export, _, summary = _preview(tmp_path, capsys)
    calls = []

    @contextmanager
    def session(connection):
        assert connection.service == "sheets"
        yield "app-created-spreadsheets", object()

    monkeypatch.setattr(sheets.GoogleConnection, "session", session)

    def send(_, method, endpoint, *, json, params):
        calls.append(method)
        if method == "POST":
            assert endpoint == sheets.SHEETS_URL
            assert json["properties"]["title"] == "Search report"
            assert json["sheets"][0]["properties"]["gridProperties"]["columnCount"] == 2
            return {"spreadsheetId": "fake-sheet-id"}
        assert "fake-sheet-id" in endpoint and params["valueInputOption"] == "RAW"
        assert json["values"] == [["query", "clicks"], ["=sample", 0], ["test", ""]]
        if calls.count("PUT") == 1:
            raise RuntimeError("Google API returned HTTP 429.")
        return {"updatedRows": 3}

    monkeypatch.setattr(sheets, "google_json", send)
    cmd = [*prefix, "google", "publish-sheets", export["run_id"], "--json", "--confirm"]
    assert main([*cmd, "wrong"]) == 2
    assert json.loads(capsys.readouterr().out)["data_egress"] == []
    assert not calls
    assert main([*cmd, summary["sha256"]]) == 2
    first = json.loads(capsys.readouterr().out)
    receipt = Path(first["out_dir"]) / "publication.json"
    assert json.loads(receipt.read_text(encoding="utf-8"))["status"] == "created"
    assert main([*cmd, summary["sha256"]]) == 0
    recovered = json.loads(capsys.readouterr().out)
    assert recovered["data_egress"][-1]["fields"] == ["query", "clicks"]
    assert main([*cmd, summary["sha256"]]) == 0
    repeated = json.loads(capsys.readouterr().out)
    assert repeated["data_egress"] == []
    assert calls == ["POST", "PUT", "PUT"]


def test_sheets_stops_when_create_outcome_is_unknown(tmp_path, monkeypatch, capsys):
    prefix, export, _, summary = _preview(tmp_path, capsys)
    calls = []

    @contextmanager
    def session(connection):
        yield "app-created-spreadsheets", object()

    def send(_, method, endpoint, **options):
        calls.append(method)
        raise RuntimeError("Request timed out.")

    monkeypatch.setattr(sheets.GoogleConnection, "session", session)
    monkeypatch.setattr(sheets, "google_json", send)
    cmd = [*prefix, "google", "publish-sheets", export["run_id"], "--confirm", summary["sha256"], "--json"]
    assert main(cmd) == 2
    capsys.readouterr()
    assert main(cmd) == 2
    assert "unknown outcome" in json.loads(capsys.readouterr().out)["warnings"][0]
    assert calls == ["POST"]


def test_sheets_connection_uses_app_file_scope_without_property_discovery(tmp_path, capsys, monkeypatch):
    pytest.importorskip("google_auth_oauthlib")
    config = tmp_path / "config.toml"
    config.write_text('[paths]\ndata_dir="data"\n', encoding="utf-8")
    vault = Vault()
    monkeypatch.setattr(google, "native_keyring", lambda: vault)

    def authorize(_, scope):
        assert scope == "https://www.googleapis.com/auth/drive.file"
        return SimpleNamespace(refresh_token="test-token", client_id="test-id", client_secret="test-secret")

    def reject(*args):
        raise AssertionError("Sheets must skip property discovery.")

    monkeypatch.setattr(google, "authorize", authorize)
    monkeypatch.setattr(google, "properties", reject)
    assert main(["--config-file", str(config), "google", "connect", "sheets", "--client-file", "desktop.json"]) == 0
    assert "test-token" not in capsys.readouterr().out
    assert len(vault.records) == 1
