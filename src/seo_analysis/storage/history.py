"""SQLite index over authoritative, per-run manifests and observation files."""
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
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
]


class History:
    def __init__(self, workspace):
        self.workspace = workspace
        self.path = workspace.data_dir / "history.sqlite3"

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

    def add_project(self, name):
        if not name.strip():
            raise ValueError("Project name is empty.")
        with self.transaction() as db:
            db.execute("INSERT INTO projects VALUES (?)", (name,))

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

    def index(self, directory, *, recover=False):
        with self.transaction() as db:
            record = json.loads((directory / "run.json").read_text(encoding="utf-8"))
            if record["run_id"] != directory.name:
                raise ValueError("Manifest ID and run directory differ.")
            rid = directory.name
            if recover and record["project"] is not None:
                db.execute("INSERT OR IGNORE INTO projects VALUES (?)", (record["project"],))
                if record["saved_target"] is not None:
                    inputs = record["parameters"]
                    db.execute("INSERT OR IGNORE INTO targets VALUES (?, ?, ?, ?)",
                               (record["project"], record["saved_target"], inputs["kind"], inputs["sitemap"]))
            db.execute("""INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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

    def list_runs(self, project=None, *, limit=-1, offset=0):
        with self.transaction() as db:
            rows = db.execute("""SELECT id, tool, status, project, target, started, finished, coverage FROM runs WHERE (? IS NULL OR project=?)
                                 ORDER BY started DESC, id LIMIT ? OFFSET ?""", (project, project, limit, offset))
            return [dict(row) | {"coverage": json.loads(row["coverage"])} for row in rows]

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
        from seo_analysis.app.runner import timestamp
        stats = {"indexed": 0, "active": 0, "recovered": 0, "errors": []}
        for path in sorted(self.workspace.runs_dir.glob("*/run.json")):
            directory = path.parent
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
