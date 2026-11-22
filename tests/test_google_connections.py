import json
import sqlite3
from types import SimpleNamespace

import pytest

from seo_analysis import cli
from seo_analysis.connectors import google
from seo_analysis.core.workspace import Workspace
from seo_analysis.storage.history import History, MIGRATIONS


class Vault:
    def __init__(self):
        self.records = {}

    def get_password(self, service, key):
        return self.records.get((service, key))

    def set_password(self, service, key, value):
        self.records[service, key] = value

    def delete_password(self, service, key):
        del self.records[service, key]


def test_connection_metadata_migrates_existing_workspace(tmp_path):
    workspace = Workspace(tmp_path / "config.toml", tmp_path, tmp_path / "exports")
    history = History(workspace)
    with sqlite3.connect(history.path) as db:
        for statement in MIGRATIONS[0]:
            db.execute(statement)
        db.execute("PRAGMA user_version=1")
        db.execute("INSERT INTO projects VALUES ('my-site')")
    assert history.google_connection("my-site", "gsc") is None
    history.set_google_connection("my-site", "gsc", "sc-domain:example.com", "Example")
    assert history.projects() == [{"name": "my-site"}]
    assert history.google_connection("my-site", "gsc")["property_id"] == "sc-domain:example.com"


def test_connected_cli_scopes_credentials_and_properties(tmp_path, monkeypatch, capsys):
    pytest.importorskip("google_auth_oauthlib")
    vault = Vault()
    scopes = []

    def authorize(_, scope):
        scopes.append(scope)
        return SimpleNamespace(refresh_token="mock-refresh", client_id="mock-id", client_secret="mock-secret")

    monkeypatch.setattr(google, "native_keyring", lambda: vault)
    monkeypatch.setattr(google, "authorize", authorize)
    monkeypatch.setattr(google, "properties", lambda service, _: (
        {"sc-domain:example.com": "example.com"} if service == "gsc" else {"properties/123": "Main"}
    ))
    config = tmp_path / "config.toml"
    config.write_text('[paths]\ndata_dir="data"\n', encoding="utf-8")
    prefix = ["--config-file", str(config)]
    assert cli.main([*prefix, "project", "create", "one"]) == 0
    capsys.readouterr()
    prefix += ["google"]
    assert cli.main([*prefix, "connect", "gsc", "--project", "one", "--client-file", "desktop.json",
                     "--property", "sc-domain:example.com"]) == 0
    assert cli.main([*prefix, "connect", "ga4", "--client-file", "desktop.json", "--property", "properties/123"]) == 0
    assert scopes == [google.SCOPES["gsc"], google.SCOPES["ga4"]]
    assert len(vault.records) == 2
    assert "mock-refresh" not in capsys.readouterr().out
    assert b"mock-refresh" not in (tmp_path / "data" / "history.sqlite3").read_bytes()

    assert cli.main([*prefix, "connect", "gsc", "--project", "one", "--client-file", "desktop.json",
                     "--property", "unlisted"]) == 2
    assert "property listed" in capsys.readouterr().err
    assert cli.main([*prefix, "status", "gsc", "--project", "one"]) == 0
    assert json.loads(capsys.readouterr().out)["selected"]["property_id"] == "sc-domain:example.com"
    assert cli.main([*prefix, "disconnect", "gsc", "--project", "one"]) == 0
    assert cli.main([*prefix, "status", "ga4"]) == 0
    assert len(vault.records) == 1


def test_oauth_uses_fixed_google_endpoints_and_loopback_pkce(tmp_path, monkeypatch):
    sdk = pytest.importorskip("google_auth_oauthlib.flow")
    client = tmp_path / "client.json"
    client.write_text(json.dumps({"installed": {
        "client_id": "test.apps.googleusercontent.com", "client_secret": "test",
        "auth_uri": "https://example.com/auth", "token_uri": "https://example.com/token",
    }}), encoding="utf-8")

    def fake_flow(config, scopes, autogenerate_code_verifier):
        assert config["installed"]["auth_uri"] == google.AUTH_URL
        assert config["installed"]["token_uri"] == google.TOKEN_URL
        assert scopes == [google.GSC_SCOPE] and autogenerate_code_verifier

        def get_credentials(**kwargs):
            assert kwargs["host"] == "127.0.0.1" and kwargs["port"] == 0
            return SimpleNamespace(refresh_token="mock-refresh", granted_scopes=[google.GSC_SCOPE])

        return SimpleNamespace(run_local_server=get_credentials)

    monkeypatch.setattr(sdk.InstalledAppFlow, "from_client_config", fake_flow)
    assert google.authorize(client, google.GSC_SCOPE).refresh_token == "mock-refresh"


def test_properties_list_only_authorized_entries_and_follow_ga_pages(monkeypatch):
    requests = []

    def response(_, method, url, **kwargs):
        assert method == "GET"
        if url == google.SITES_URL:
            return {"siteEntry": [
                {"siteUrl": "sc-domain:visible.test", "permissionLevel": "siteRestrictedUser"},
                {"siteUrl": "sc-domain:hidden.test", "permissionLevel": "siteUnverifiedUser"},
            ]}
        assert url == google.SUMMARIES_URL
        token = kwargs["params"].get("pageToken")
        requests.append(token)
        if token is None:
            return {"nextPageToken": "next"}
        return {"accountSummaries": [{"propertySummaries": [
            {"property": "properties/123", "displayName": "App"},
        ]}]}

    monkeypatch.setattr(google, "google_json", response)
    assert google.properties("gsc", None) == {"sc-domain:visible.test": "sc-domain:visible.test"}
    assert google.properties("ga4", None) == {"properties/123": "App"}
    assert requests == [None, "next"]
