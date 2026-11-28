from contextlib import closing, contextmanager
from pathlib import Path
import sqlite3

import pytest

from seo_analysis.core.workspace import Workspace
from seo_analysis.desktop import check_workspace, needs_writable_copy, open_launcher_state, recover_workspace
from seo_analysis.storage.history import History


def test_desktop_workspace_recovery_preserves_history_and_files(tmp_path):
    existing_config = tmp_path / "existing.toml"
    existing_config.write_text('[paths]\ndata_dir = "SEO محیط"\n', encoding="utf-8")
    original = Workspace.load(existing_config)
    state = tmp_path / "launcher"
    state.mkdir()
    check_workspace(original)
    history = History(original)
    history.add_project("نمونه", website="https://example.com/")
    artifact = Path("audit-example") / "report.txt"
    report = original.runs_dir / artifact
    report.parent.mkdir()
    report.write_text("Saved audit", encoding="utf-8")

    with closing(sqlite3.connect(history.path)) as writer:
        writer.execute("PRAGMA journal_mode=WAL")
        history.add_project("Latest project")
        with closing(sqlite3.connect(history.path.as_uri() + "?mode=ro", uri=True)) as readonly:
            with pytest.raises(sqlite3.OperationalError) as error:
                readonly.execute("DELETE FROM projects")
        assert needs_writable_copy(error.value)
        copied = recover_workspace(original, state)

    assert copied.data_dir != original.data_dir
    assert History(copied).projects() == [{"name": "Latest project"}, {"name": "نمونه"}]
    assert History(copied).targets("نمونه")[0]["url"] == "https://example.com/"
    assert (copied.runs_dir / artifact).read_text(encoding="utf-8") == "Saved audit"
    History(copied).add_project("Only in copy")
    assert History(original).projects() == [{"name": "Latest project"}, {"name": "نمونه"}]
    _, log, saved_config = open_launcher_state((state,), None)
    with closing(log):
        assert Workspace.load(saved_config) == copied
    _, log, explicit_config = open_launcher_state((state,), existing_config)
    with closing(log):
        assert Workspace.load(explicit_config) == original


def test_desktop_uses_writable_state_when_windows_denies_appdata(tmp_path, monkeypatch):
    original_config = tmp_path / "existing.toml"
    original_config.write_text('[paths]\ndata_dir = "existing"\n', encoding="utf-8")
    original = Workspace.load(original_config)
    History(original).add_project("Saved project")
    appdata = tmp_path / "AppData" / "Local" / "SEOAnalysisWorkbench"
    fallback = tmp_path / "user profile" / "SEOAnalysisWorkbench"
    locations = (appdata, fallback)
    mkdir = Path.mkdir

    def denied(path, *args, **kwargs):
        if path == appdata:
            raise PermissionError(13, "Access is denied", str(path))
        return mkdir(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "mkdir", denied)
        state, log, config = open_launcher_state(locations, None)
        with closing(log):
            assert state == fallback and config is None
            assert (fallback / "launcher.log").is_file()
        copied = recover_workspace(original, state)

    # Prefer the recovery already in use when AppData becomes writable again.
    state, log, config = open_launcher_state(locations, None)
    with closing(log):
        assert state == fallback
        assert Workspace.load(config) == copied
        assert History(copied).projects() == [{"name": "Saved project"}]
        assert not appdata.exists()


def test_desktop_keeps_a_saved_workspace_when_only_the_log_needs_to_move(tmp_path):
    primary = tmp_path / "appdata"
    fallback = tmp_path / "profile"
    primary.mkdir()
    (primary / "launcher.log").mkdir()
    existing_workspace = tmp_path / "existing.toml"
    (primary / "workspace-config.txt").write_text(str(existing_workspace), encoding="utf-8")

    state, log, config = open_launcher_state((primary, fallback), None)
    with closing(log):
        assert state == fallback and config == existing_workspace


def test_desktop_recovery_does_not_treat_arbitrary_sqlite_errors_as_permissions():
    assert not needs_writable_copy(sqlite3.OperationalError("database is locked"))
    assert needs_writable_copy(PermissionError())


def test_desktop_detects_a_read_only_history_after_migration(tmp_path, monkeypatch):
    config = tmp_path / "config.toml"
    config.write_text('[paths]\ndata_dir = "data"\n', encoding="utf-8")
    workspace = Workspace.load(config)
    check_workspace(workspace)

    @contextmanager
    def read_only_transaction(history):
        with closing(sqlite3.connect(history.path.as_uri() + "?mode=ro", uri=True)) as database:
            database.execute("BEGIN IMMEDIATE")
            yield database

    monkeypatch.setattr(History, "transaction", read_only_transaction)
    with pytest.raises(sqlite3.OperationalError) as error:
        check_workspace(workspace)
    assert needs_writable_copy(error.value)
