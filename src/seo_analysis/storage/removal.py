"""Delete saved workspace data without reindexing files left after an interrupted cleanup."""

import logging
from pathlib import Path
import re
import shutil

from filelock import FileLock, Timeout

from seo_analysis.core.tools import AUDIT
from seo_analysis.storage.history import History

LOG = logging.getLogger(__name__)
RUN_ID = re.compile(r"[0-9a-f]{32}")
WORKSPACE_FILES = ("decisions.jsonl", "sheets-publications")


class RemovalConflict(RuntimeError):
    """Saved data cannot be removed safely at this time."""


def pending_removals(history: History) -> int:
    with history.transaction() as db:
        return db.execute("SELECT count(*) FROM pending_removals").fetchone()[0]


def managed_path(history: History, key: str) -> Path:
    root = history.workspace.data_dir
    if key in WORKSPACE_FILES:
        path = root / key
    elif key.startswith("runs/") and RUN_ID.fullmatch(key.removeprefix("runs/")):
        runs = history.workspace.runs_dir
        if runs.is_symlink() or runs.is_junction():
            raise RemovalConflict("The runs folder is a link. Move saved runs into the workspace before deleting them.")
        path = runs / key.removeprefix("runs/")
    else:
        raise RemovalConflict("An invalid workspace data path was recorded.")
    if path.is_symlink() or path.is_junction():
        raise RemovalConflict(f"The saved item {path.name} is a link and cannot be deleted here.")
    if path.exists() and path.is_dir() != (key != "decisions.jsonl"):
        raise RemovalConflict(f"The saved item {path.name} has an unexpected file type.")
    return path


def ensure_inactive(history: History, keys: set[str]) -> None:
    for key in keys:
        directory = managed_path(history, key)
        if directory.is_dir():
            lock = directory / ".active.lock"
            if lock.is_symlink() or lock.is_junction():
                raise RemovalConflict("A run lock is a link. Close the workspace and check the run folder.")
            try:
                # Registration and reindexing hold the workspace lock, so a run cannot restart here.
                with FileLock(str(lock), timeout=0):
                    pass
            except Timeout as exc:
                raise RemovalConflict("A run is still active. Wait for it to finish before deleting saved data.") from exc


def _clean_pending(history: History) -> int:
    with history.transaction() as db:
        pending = [row["path"] for row in db.execute("SELECT path FROM pending_removals")]
    cleaned = []
    for key in pending:
        try:
            path = managed_path(history, key)
            if key == "decisions.jsonl":
                with FileLock(str(path.with_name(".decisions.jsonl.lock")), timeout=0):
                    path.unlink(missing_ok=True)
            elif path.is_dir():
                shutil.rmtree(path)
            cleaned.append((key,))
        except (OSError, RemovalConflict, Timeout):
            LOG.exception("Could not remove saved workspace item %s", key)
    with history.transaction() as db:
        db.executemany("DELETE FROM pending_removals WHERE path=?", cleaned)
    return len(pending) - len(cleaned)


def retry_removals(history: History) -> int:
    with history.run_storage_lock():
        return _clean_pending(history)


def remove_saved_data(history: History, scope: str, *, run_id: str | None = None) -> tuple[int, int]:
    """Commit the index changes and retryable file removals before touching saved artifacts."""
    if scope not in ("single", "audits", "runs", "workspace"):
        raise ValueError("Unknown deletion scope.")
    if scope == "single" and (not run_id or not RUN_ID.fullmatch(run_id)):
        raise ValueError("Unknown run ID.")
    with history.run_storage_lock():
        with history.transaction() as db:
            records = db.execute("SELECT id, tool, finished FROM runs").fetchall()
            if scope == "single":
                selected = [(row["id"],) for row in records if row["id"] == run_id]
                if not selected:
                    if not db.execute("SELECT 1 FROM pending_removals WHERE path=?", ("runs/" + str(run_id),)).fetchone():
                        raise ValueError("Unknown run ID.")
            elif scope == "audits":
                selected = [(row["id"],) for row in records if row["tool"] == AUDIT.id]
            else:
                selected = [(row["id"],) for row in records]
            keys = {"runs/" + rid for rid, in selected}
            if scope in ("runs", "workspace"):
                # Include unindexed run folders, which a later reindex would otherwise recover.
                root = history.workspace.runs_dir
                if root.is_symlink() or root.is_junction():
                    raise RemovalConflict("The runs folder is a link and cannot be cleared here.")
                if root.is_dir():
                    keys.update("runs/" + entry.name for entry in root.iterdir() if RUN_ID.fullmatch(entry.name))
            # An active derived run may be reading a source run the user is deleting.
            ensure_inactive(history, keys | {"runs/" + row["id"] for row in records if row["finished"] is None})
            if scope == "workspace":
                for key in WORKSPACE_FILES:
                    managed_path(history, key)
                keys.update(WORKSPACE_FILES)
            db.execute("PRAGMA secure_delete=ON")
            db.executemany("INSERT OR IGNORE INTO pending_removals VALUES (?)", [(key,) for key in keys])
            db.executemany("DELETE FROM evidence WHERE run_id=?", selected)
            db.executemany("DELETE FROM artifacts WHERE run_id=?", selected)
            db.executemany("DELETE FROM runs WHERE id=?", selected)
            if scope == "workspace":
                db.execute("DELETE FROM audit_workflows")
                db.execute("DELETE FROM targets")
                db.execute("DELETE FROM projects")
                db.execute("DELETE FROM google_connections")
                db.execute("DELETE FROM finding_reviews")
                db.execute("DELETE FROM brief_items")
                db.execute("DELETE FROM brief_sources")
        return len(selected), _clean_pending(history)
