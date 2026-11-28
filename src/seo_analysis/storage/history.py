"""SQLite index over authoritative, per-run manifests and observation files."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from uuid import UUID

from filelock import FileLock, Timeout

from seo_analysis.core.artifacts import atomic_text, write_json
from seo_analysis.core.network import HttpOrigin

MIGRATIONS = [
    (
        "CREATE TABLE projects (name TEXT PRIMARY KEY)",
        """CREATE TABLE targets (project TEXT REFERENCES projects(name), name TEXT,
               kind TEXT NOT NULL, url TEXT NOT NULL, PRIMARY KEY(project, name))""",
        """CREATE TABLE runs (id TEXT PRIMARY KEY, tool TEXT NOT NULL, status TEXT NOT NULL,
               project TEXT REFERENCES projects(name), target TEXT, started TEXT NOT NULL, finished TEXT,
               coverage TEXT NOT NULL, manifest TEXT NOT NULL, FOREIGN KEY(project, target) REFERENCES targets(project, name))""",
        "CREATE INDEX runs_by_date ON runs(started DESC)",
        "CREATE INDEX runs_by_project ON runs(project, started DESC)",
        """CREATE TABLE artifacts (run_id TEXT REFERENCES runs(id), path TEXT,
               bytes INTEGER NOT NULL, PRIMARY KEY(run_id, path))""",
        """CREATE TABLE evidence (run_id TEXT REFERENCES runs(id), id TEXT, url TEXT NOT NULL,
               observed_at TEXT NOT NULL, path TEXT NOT NULL, PRIMARY KEY(run_id, id))""",
    ),
    (
        """CREATE TABLE google_connections (
               project TEXT NOT NULL, service TEXT NOT NULL, property_id TEXT NOT NULL,
               property_name TEXT NOT NULL, PRIMARY KEY(project, service))""",
    ),
    ("ALTER TABLE runs ADD COLUMN archived INTEGER NOT NULL DEFAULT 0",),
    (
        """CREATE TABLE audit_workflows (
               id TEXT PRIMARY KEY, project TEXT NOT NULL, target TEXT NOT NULL, name TEXT NOT NULL,
               page_limit INTEGER NOT NULL CHECK(page_limit BETWEEN 1 AND 500),
               link_crawl INTEGER NOT NULL CHECK(link_crawl IN (0, 1)), UNIQUE(project, name),
               FOREIGN KEY(project, target) REFERENCES targets(project, name))""",
    ),
    ("CREATE TABLE pending_removals (path TEXT PRIMARY KEY)",),
    (
        """CREATE TABLE finding_reviews (
               project TEXT NOT NULL, rule TEXT NOT NULL, page_key TEXT NOT NULL,
               status TEXT NOT NULL CHECK(status IN ('open','reviewed','ignored')),
               note TEXT NOT NULL DEFAULT '', fingerprint TEXT NOT NULL,
               evidence_id TEXT, run_id TEXT, updated_at TEXT NOT NULL,
               PRIMARY KEY (project, rule, page_key))""",
    ),
    (
        """CREATE TABLE brief_items (
               project TEXT NOT NULL, query TEXT NOT NULL, note TEXT NOT NULL DEFAULT '',
               source_run TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
               PRIMARY KEY (project, query))""",
    ),
    (
        """CREATE TABLE brief_sources (
               project TEXT NOT NULL, query TEXT NOT NULL, run_id TEXT NOT NULL,
               row_ref TEXT NOT NULL DEFAULT '', added_at TEXT NOT NULL,
               PRIMARY KEY (project, query, run_id, row_ref))""",
        # Existing items keep their note and gain the source they were collected from.
        """INSERT OR IGNORE INTO brief_sources (project, query, run_id, row_ref, added_at)
           SELECT project, query, source_run, '', updated_at FROM brief_items
           WHERE source_run IS NOT NULL AND source_run <> ''""",
    ),
]


def workspace_access_error(error: BaseException) -> bool:
    if isinstance(error, PermissionError):
        return True
    code = getattr(error, "sqlite_errorcode", 0) & 0xff
    return isinstance(error, sqlite3.OperationalError) and code in (sqlite3.SQLITE_READONLY, sqlite3.SQLITE_CANTOPEN)


class History:
    def __init__(self, workspace):
        self.workspace = workspace
        self.path = workspace.data_dir / "history.sqlite3"

    def run_storage_lock(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        return FileLock(str(self.path.parent / ".run-storage.lock"), timeout=20)

    def check_writable(self):
        with self.transaction() as db:
            # SQLite can read an existing schema even when it cannot write to it.
            db.execute("UPDATE projects SET name = name WHERE 0")
        self.workspace.runs_dir.mkdir(exist_ok=True)
        for directory in (self.workspace.data_dir, self.workspace.runs_dir):
            with TemporaryDirectory(prefix=".write-check-", dir=directory):
                pass

    def check_reset_complete(self):
        with self.transaction() as db:
            if db.execute("SELECT 1 FROM pending_removals WHERE path IN ('decisions.jsonl', 'sheets-publications')").fetchone():
                raise ValueError("Finish pending cleanup under History → Manage saved data first.")

    @contextmanager
    def transaction(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=20)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("BEGIN IMMEDIATE")
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version > len(MIGRATIONS):
                raise ValueError("History was created by a newer application.")
            for number, migration in enumerate(MIGRATIONS[version:], version + 1):
                for statement in migration:
                    db.execute(statement)
                db.execute(f"PRAGMA user_version={number}")
            yield db
            db.commit()
        except sqlite3.IntegrityError as exc:
            raise ValueError("Name already in use or referenced project/target does not exist.") from exc
        finally:
            db.close()

    def add_project(self, name, *, website=""):
        if not name.strip():
            raise ValueError("Project name is empty.")
        if website:
            HttpOrigin.from_url(website)
        with self.transaction() as db:
            db.execute("INSERT INTO projects VALUES (?)", (name,))
            if website:
                db.execute("INSERT INTO targets VALUES (?, 'Website', 'website', ?)", (name, website))

    def add_target(self, project, name, kind, url):
        if not name.strip() or kind not in ("website", "sitemap"):
            raise ValueError("Use a target name and a website or sitemap URL.")
        HttpOrigin.from_url(url)
        with self.transaction() as db:
            db.execute("INSERT INTO targets VALUES (?, ?, ?, ?)", (project, name, kind, url))

    def projects(self):
        with self.transaction() as db:
            return [dict(r) for r in db.execute("SELECT name FROM projects ORDER BY name")]

    def targets(self, project):
        with self.transaction() as db:
            return [dict(r) for r in db.execute("SELECT * FROM targets WHERE project=? ORDER BY name", (project,))]

    def selection(self, project, target):
        if project is None:
            if target is not None:
                raise ValueError("Select --project when using --target.")
            return
        with self.transaction() as db:
            if not db.execute("SELECT 1 FROM projects WHERE name=?", (project,)).fetchone():
                raise ValueError("Unknown project.")
            if target is not None:
                row = db.execute("SELECT * FROM targets WHERE project=? AND name=?", (project, target)).fetchone()
                if row is None:
                    raise ValueError("Unknown target in this project.")
                return dict(row)

    def audit_workflows(self, project=None):
        with self.transaction() as db:
            return [dict(row) for row in db.execute("""SELECT w.*, t.url FROM audit_workflows w
                JOIN targets t ON t.project=w.project AND t.name=w.target
                WHERE (? IS NULL OR w.project=?) ORDER BY w.project, w.name""", (project, project))]

    def audit_workflow(self, workflow_id):
        with self.transaction() as db:
            row = db.execute("""SELECT w.*, t.url, t.kind FROM audit_workflows w
                JOIN targets t ON t.project=w.project AND t.name=w.target WHERE w.id=?""", (workflow_id,)).fetchone()
            if row is None:
                raise ValueError("Unknown audit workflow.")
            return dict(row)

    def save_audit_workflow(self, workflow_id, project, target, name, page_limit, link_crawl, *, editing=False):
        name = name.strip()
        if not name:
            raise ValueError("Enter a workflow name.")
        if not 1 <= page_limit <= 500:
            raise ValueError("Choose between 1 and 500 pages.")
        with self.transaction() as db:
            if not db.execute("SELECT 1 FROM targets WHERE project=? AND name=?", (project, target)).fetchone():
                raise ValueError("Choose a saved target from this project.")
            if editing:
                changed = db.execute("""UPDATE audit_workflows SET target=?, name=?, page_limit=?, link_crawl=?
                    WHERE id=? AND project=?""", (target, name, page_limit, link_crawl, workflow_id, project)).rowcount
                if not changed:
                    raise ValueError("Unknown audit workflow.")
            else:
                db.execute("INSERT INTO audit_workflows VALUES (?, ?, ?, ?, ?, ?)",
                           (workflow_id, project, target, name, page_limit, link_crawl))

    def google_connection(self, project, service):
        with self.transaction() as db:
            selected = db.execute("SELECT property_id, property_name FROM google_connections WHERE project=? AND service=?",
                                  (project or "", service)).fetchone()
            return dict(selected) if selected else None

    def set_google_connection(self, project, service, property_id, property_name):
        with self.transaction() as db:
            db.execute("""INSERT INTO google_connections VALUES (?, ?, ?, ?)
                          ON CONFLICT(project, service) DO UPDATE SET property_id=excluded.property_id,
                          property_name=excluded.property_name""",
                       (project or "", service, property_id, property_name))

    def remove_google_connection(self, project, service):
        with self.transaction() as db:
            db.execute("DELETE FROM google_connections WHERE project=? AND service=?", (project or "", service))

    def save_finding_review(self, project, rule, page_key, *, status, note, fingerprint, evidence_id="", run_id=""):
        """Record one decision per project, rule and page. A repeated save updates the same row."""
        if status not in ("open", "reviewed", "ignored"):
            raise ValueError("Unknown review status.")
        updated = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self.transaction() as db:
            db.execute("""INSERT INTO finding_reviews
                          (project, rule, page_key, status, note, fingerprint, evidence_id, run_id, updated_at)
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                          ON CONFLICT(project, rule, page_key) DO UPDATE SET status=excluded.status,
                          note=excluded.note, fingerprint=excluded.fingerprint,
                          evidence_id=excluded.evidence_id, run_id=excluded.run_id, updated_at=excluded.updated_at""",
                       (project, rule, page_key, status, note, fingerprint, evidence_id, run_id, updated))
            row = db.execute("""SELECT * FROM finding_reviews WHERE project=? AND rule=? AND page_key=?""",
                             (project, rule, page_key)).fetchone()
            return dict(row)

    def finding_reviews(self, project=None):
        with self.transaction() as db:
            rows = db.execute("""SELECT * FROM finding_reviews WHERE (? IS NULL OR project=?)
                                 ORDER BY updated_at DESC, rule, page_key""", (project, project))
            return [dict(row) for row in rows]

    def finding_review(self, project, rule, page_key):
        with self.transaction() as db:
            row = db.execute("""SELECT * FROM finding_reviews WHERE project=? AND rule=? AND page_key=?""",
                             (project, rule, page_key)).fetchone()
            return dict(row) if row else None

    def add_brief_item(self, project, query, *, note="", source_run=""):
        """Collect one query into the project's brief. Adding the same query again updates it."""
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self.transaction() as db:
            db.execute("""INSERT INTO brief_items (project, query, note, source_run, created_at, updated_at)
                          VALUES (?, ?, ?, ?, ?, ?)
                          ON CONFLICT(project, query) DO UPDATE SET note=excluded.note,
                          source_run=excluded.source_run, updated_at=excluded.updated_at""",
                       (project, query, note, source_run, now, now))
            row = db.execute("SELECT * FROM brief_items WHERE project=? AND query=?", (project, query)).fetchone()
            return dict(row)

    def collect_brief_item(self, project, query, *, note="", source_run="", row_ref=""):
        """Collect a query: create it once, record where it came from, never overwrite an edited note."""
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self.transaction() as db:
            db.execute("""INSERT INTO brief_items (project, query, note, source_run, created_at, updated_at)
                          VALUES (?, ?, ?, ?, ?, ?)
                          ON CONFLICT(project, query) DO UPDATE SET updated_at=excluded.updated_at""",
                       (project, query, note, source_run, now, now))
            if source_run:
                db.execute("""INSERT OR IGNORE INTO brief_sources (project, query, run_id, row_ref, added_at)
                              VALUES (?, ?, ?, ?, ?)""", (project, query, source_run, row_ref or "", now))
            row = db.execute("SELECT * FROM brief_items WHERE project=? AND query=?", (project, query)).fetchone()
            return dict(row)

    def set_brief_note(self, project, query, note):
        """Edit the human decision, leaving the collected sources untouched."""
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self.transaction() as db:
            db.execute("UPDATE brief_items SET note=?, updated_at=? WHERE project=? AND query=?",
                       (note, now, project, query))

    def brief_sources(self, project, query=None):
        with self.transaction() as db:
            rows = db.execute("""SELECT * FROM brief_sources WHERE project=? AND (? IS NULL OR query=?)
                                 ORDER BY added_at, run_id, row_ref""", (project, query, query))
            return [dict(row) for row in rows]

    def remove_brief_source(self, project, query, run_id, row_ref=""):
        with self.transaction() as db:
            db.execute("""DELETE FROM brief_sources WHERE project=? AND query=? AND run_id=? AND row_ref=?""",
                       (project, query, run_id, row_ref or ""))

    def brief_items(self, project):
        with self.transaction() as db:
            rows = db.execute("""SELECT * FROM brief_items WHERE project=?
                                 ORDER BY updated_at DESC, query""", (project,))
            return [dict(row) for row in rows]

    def latest_audit(self, project, target=None):
        """The newest finished audit for this project and target, ignoring unrelated runs."""
        with self.transaction() as db:
            row = db.execute("""SELECT manifest FROM runs WHERE project=? AND tool=? AND finished IS NOT NULL
                                AND (? IS NULL OR target IS ?)
                                ORDER BY started DESC, id LIMIT 1""",
                             (project, "seo.audit", target, target)).fetchone()
            return json.loads(row["manifest"]) if row else None

    def remove_brief_item(self, project, query):
        with self.transaction() as db:
            db.execute("DELETE FROM brief_sources WHERE project=? AND query=?", (project, query))
            db.execute("DELETE FROM brief_items WHERE project=? AND query=?", (project, query))

    def index(self, directory, *, recover=False):
        with self.transaction() as db:
            record = json.loads((directory / "run.json").read_text(encoding="utf-8"))
            if record["run_id"] != directory.name:
                raise ValueError("Manifest ID and run directory differ.")
            rid = directory.name
            if db.execute("SELECT 1 FROM pending_removals WHERE path=?", ("runs/" + rid,)).fetchone():
                raise ValueError("This run was deleted and its saved files are pending cleanup.")
            if recover and record["project"] is not None:
                db.execute("INSERT OR IGNORE INTO projects VALUES (?)", (record["project"],))
                if record["saved_target"] is not None:
                    inputs = record["parameters"]
                    db.execute("INSERT OR IGNORE INTO targets VALUES (?, ?, ?, ?)",
                               (record["project"], record["saved_target"], inputs["kind"], inputs["sitemap"]))
            db.execute("""INSERT INTO runs (id, tool, status, project, target, started, finished, coverage, manifest)
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                          ON CONFLICT(id) DO UPDATE SET status=excluded.status,
                          finished=excluded.finished, coverage=excluded.coverage, manifest=excluded.manifest""",
                       (rid, record["tool_id"], record["status"], record["project"], record["saved_target"],
                        record["started_at"], record["finished_at"], json.dumps(record["counts"]), json.dumps(record)))
            db.execute("DELETE FROM artifacts WHERE run_id=?", (rid,))
            db.execute("DELETE FROM evidence WHERE run_id=?", (rid,))
            for name in record["artifacts"]:
                if Path(name).name != name or not (directory / name).is_file():
                    raise ValueError("Invalid artifact name in run manifest.")
                file = directory / name
                db.execute("INSERT INTO artifacts VALUES (?, ?, ?)", (rid, name, file.stat().st_size))
            for file in sorted((directory / "observations").glob("page-*.json")):
                item = json.loads(file.read_text(encoding="utf-8"))
                db.execute("INSERT INTO evidence VALUES (?, ?, ?, ?, ?)",
                           (rid, item["evidence_id"], item["url"], item["observed_at"], "observations/" + file.name))

    def list_runs(self, project=None, *, limit=-1, offset=0, archived=None):
        with self.transaction() as db:
            rows = db.execute("""SELECT id, tool, status, project, target, started, finished, coverage FROM runs
                                 WHERE (? IS NULL OR project=?) AND (? IS NULL OR archived=?)
                                 ORDER BY started DESC, id LIMIT ? OFFSET ?""", (project, project, archived, archived, limit, offset))
            return [dict(row) | {"coverage": json.loads(row["coverage"])} for row in rows]

    def set_archived(self, run_id, archived):
        with self.transaction() as db:
            if not db.execute("UPDATE runs SET archived=? WHERE id=?", (archived, run_id)).rowcount:
                raise ValueError("Unknown run ID.")

    def runs_with_artifact(self, name):
        with self.transaction() as db:
            rows = db.execute("""SELECT manifest, archived FROM runs WHERE finished IS NOT NULL
                                 AND EXISTS (SELECT 1 FROM artifacts WHERE run_id=runs.id AND path=?)
                                 ORDER BY started DESC, id""", (name,))
            return [json.loads(row["manifest"]) | {"archived": bool(row["archived"])} for row in rows]

    def show(self, run_id):
        if UUID(run_id).hex != run_id:
            raise ValueError("Invalid run ID.")
        with self.transaction() as db:
            row = db.execute("SELECT manifest FROM runs WHERE id=?", (run_id,)).fetchone()
            if row is None:
                raise ValueError("Unknown run ID.")
            artifacts = [dict(r) for r in db.execute("SELECT path, bytes FROM artifacts WHERE run_id=? ORDER BY path", (run_id,))]
            evidence = [dict(r) for r in db.execute("SELECT id,url,observed_at,path FROM evidence WHERE run_id=? ORDER BY id", (run_id,))]
            directory = self.workspace.runs_dir / run_id
            manifest = json.loads(row["manifest"])
            return dict(manifest=manifest, directory=str(directory), artifacts=artifacts, evidence=evidence)

    def reindex(self):
        with self.run_storage_lock():
            return self._reindex()

    def _reindex(self):
        from seo_analysis.app.runner import timestamp
        stats = {"indexed": 0, "active": 0, "recovered": 0, "errors": []}
        with self.transaction() as db:
            pending = {row["path"] for row in db.execute("SELECT path FROM pending_removals")}
        for path in sorted(self.workspace.runs_dir.glob("*/run.json")):
            directory = path.parent
            if "runs/" + directory.name in pending:
                continue
            try:
                with FileLock(str(directory / ".active.lock"), timeout=0):
                    manifest = json.loads(path.read_text(encoding="utf-8"))
                    if manifest["status"] == "running":
                        observations = sorted((directory / "observations").glob("page-*.json"))
                        if observations:
                            with atomic_text(directory / "snapshot.jsonl") as stream:
                                for item in observations:
                                    row = json.loads(item.read_text(encoding="utf-8"))
                                    stream.write(json.dumps(row, ensure_ascii=False) + "\n")
                        manifest.update(status="partial" if observations else "failed", finished_at=timestamp(),
                                        counts={"observed": len(observations)}, artifacts=sorted(
                                            f.name for f in directory.iterdir() if f.is_file() and f != path and not f.name.startswith(".")))
                        manifest["warnings"].append("Process ended before finalization. Coverage is incomplete.")
                        write_json(path, manifest)
                        stats["recovered"] += 1
                    self.index(directory, recover=True)
                    stats["indexed"] += 1
            except Timeout:
                stats["active"] += 1
            except (OSError, ValueError, KeyError) as exc:
                stats["errors"].append(f"{directory.name}: {exc}")
        return stats
