"""Self-contained exports for one saved audit: filtered page CSV and a versioned analysis bundle."""
import csv
from datetime import datetime, timezone
from io import BytesIO, StringIO
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from seo_analysis.reporting.report import csv_safe

BUNDLE_SCHEMA = 1
BUNDLE_FILE_LIMIT = 25_000_000
PAGE_HEADER = ["URL", "URL (decoded)", "Final URL", "HTTP status", "First HTTP status", "Redirected to",
               "Redirect count", "Effective indexability", "Indexability reason", "Findings", "Title",
               "Words", "Depth", "Evidence ID"]

# group -> files copied verbatim into the bundle
BUNDLE_GROUPS = {
    "crawl": ("snapshot.jsonl", "inventory.csv", "requests.json", "crawl_manifest.json"),
    "analysis": ("findings.json", "findings.csv", "pairs.json", "canonical_report.csv", "analysis_manifest.json"),
    "diagnostics": ("run.json",),
}
FILE_META = {
    "snapshot.jsonl": {"format": "jsonl", "grain": "one observed page", "identifiers": ["evidence_id"],
                       "join_keys": ["evidence_id", "url"],
                       "missing_values": ["final_status 0 means no HTTP response",
                                          "markup is absent when no HTML response was read",
                                          "extraction is absent before tool version 0.4.0",
                                          "content_hash is null when extracted text is empty"]},
    "inventory.csv": {"format": "csv", "grain": "one observed page", "identifiers": ["URL"],
                      "join_keys": ["URL"], "missing_values": ["a blank cell means the value was unavailable"]},
    "requests.json": {"format": "json", "grain": "one HTTP request attempt", "identifiers": [],
                      "join_keys": ["url → snapshot.jsonl url"]},
    "crawl_manifest.json": {"format": "json", "grain": "one crawl run", "identifiers": [], "join_keys": []},
    "findings.json": {"format": "json", "grain": "one finding", "identifiers": ["evidence_ids"],
                      "join_keys": ["evidence_ids[] → snapshot.jsonl evidence_id", "urls[] → snapshot.jsonl url"],
                      "missing_values": ["absent when the run stopped before findings were written"]},
    "findings.csv": {"format": "csv", "grain": "one finding", "identifiers": ["Evidence IDs"],
                     "join_keys": ["Evidence IDs → snapshot.jsonl evidence_id"]},
    "pairs.json": {"format": "json", "grain": "one compared page pair", "identifiers": ["url_a", "url_b"],
                   "join_keys": ["url_a, url_b → snapshot.jsonl url"]},
    "canonical_report.csv": {"format": "csv", "grain": "one page with a canonical issue", "identifiers": ["URL"],
                             "join_keys": ["URL → snapshot.jsonl url"]},
    "analysis_manifest.json": {"format": "json", "grain": "one analysis run", "identifiers": [],
                               "join_keys": ["thresholds apply to analysis/pairs.json"]},
    "run.json": {"format": "json", "grain": "one run", "identifiers": ["run_id"], "join_keys": ["run_id"]},
}


def stamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _describe(filters: dict) -> str:
    parts = [f"{key}={value}" for key, value in filters.items()
             if value and key != "tab" and not (key == "sort" and value == "url")]
    return "; ".join(parts) if parts else "none"


def page_csv(query, *, run: dict, site: str, generated_at: str = "") -> str:
    """Every matching page, with the scope written into the file."""
    scope = (f"# SEO Analysis page export · run {run.get('run_id', '')} · site {site or 'unknown'} · "
             f"{query.matched} of {query.total} observed pages · filters: {_describe(query.filters)} · "
             f"exported {generated_at or stamp()}")
    buffer = StringIO()
    buffer.write("\ufeff" + scope + "\r\n")
    writer = csv.writer(buffer)
    writer.writerow(PAGE_HEADER)
    for page in query.rows:
        writer.writerow([csv_safe(value) for value in (
            page.url, page.url_decoded, page.final_url, page.status_text, page.first_status or "",
            page.redirect_to, page.redirect_count, page.indexability_text, page.indexability_reason,
            " | ".join(page.rules), page.title, page.words if page.words is not None else "",
            page.depth if page.depth is not None else "", page.evidence_id,
        )])
    return buffer.getvalue()


def _row_count(path: Path) -> int | None:
    try:
        if path.suffix == ".jsonl":
            with path.open(encoding="utf-8") as handle:
                return sum(1 for line in handle if line.strip())
        if path.suffix == ".csv":
            with path.open(encoding="utf-8-sig") as handle:
                return max(0, sum(1 for _ in csv.reader(handle)) - 1)
    except OSError:
        return None
    return None


def _analysis(run_dir: Path) -> tuple[dict, list]:
    path = run_dir / "analysis_manifest.json"
    if not path.is_file():
        return {}, []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}, []
    return data.get("config", {}).get("settings", {}) or {}, data.get("limitations", []) or []


def _entry_path(run_dir: Path, name: str, manifest: dict):
    """Resolve one bundle entry through the same rules the run-file handler uses."""
    path = run_dir / name
    if path.is_symlink():
        return None, "is a link and is not followed"
    if not path.is_file():
        return None, "not written by this run"
    resolved = path.resolve()
    if resolved.parent != run_dir.resolve():
        return None, "resolves outside the run directory"
    if name != "run.json" and name not in (manifest.get("artifacts") or []):
        return None, "not listed in the run manifest"
    return resolved, ""


def build_bundle(run_dir, manifest: dict, *, site: str = "", generated_at: str = "") -> bytes:
    """A ZIP carrying the allowlisted run files plus an index describing how to join them."""
    run_dir = Path(run_dir)
    thresholds, limitations = _analysis(run_dir)
    files, skipped = [], []
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        for group, names in BUNDLE_GROUPS.items():
            for name in names:
                path, reason = _entry_path(run_dir, name, manifest)
                if path is None:
                    skipped.append({"file": f"{group}/{name}", "reason": reason})
                    continue
                size = path.stat().st_size
                if size > BUNDLE_FILE_LIMIT:
                    skipped.append({"file": f"{group}/{name}", "reason": "exceeds the 25 MB per-file limit"})
                    continue
                entry = {"path": f"{group}/{name}", "bytes": size, "group": group,
                         "rows": _row_count(path), **_meta(name)}
                archive.writestr(f"{group}/{name}", path.read_bytes())
                files.append(entry)
        observations = run_dir / "observations"
        if observations.is_dir() and any(observations.iterdir()):
            skipped.append({"file": "observations/",
                            "reason": "each file repeats one snapshot.jsonl record, so it is not duplicated here"})
        index = {
            "schema_version": BUNDLE_SCHEMA,
            "generated_at": generated_at or stamp(),
            "run": {
                "run_id": manifest.get("run_id"), "tool_id": manifest.get("tool_id"),
                "tool_version": manifest.get("tool_version"), "status": manifest.get("status"),
                "site": site, "started_at": manifest.get("started_at"),
                "finished_at": manifest.get("finished_at"), "project": manifest.get("project"),
                "counts": manifest.get("counts", {}), "warnings": manifest.get("warnings", []),
            },
            "files": files,
            "skipped": skipped,
            "joins": [
                {"from": "analysis/findings.json", "from_field": "evidence_ids[]",
                 "to": "crawl/snapshot.jsonl", "to_field": "evidence_id",
                 "note": "one finding may reference two pages"},
                {"from": "analysis/findings.json", "from_field": "urls[]",
                 "to": "crawl/snapshot.jsonl", "to_field": "url"},
                {"from": "analysis/pairs.json", "from_field": "url_a, url_b",
                 "to": "crawl/snapshot.jsonl", "to_field": "url"},
            ],
            "thresholds": thresholds,
            "limitations": limitations,
            "coverage": {
                "observed": (manifest.get("counts") or {}).get("observed"),
                "html_pages": (manifest.get("counts") or {}).get("html_pages"),
                "pages_compared": (manifest.get("counts") or {}).get("pages_compared"),
                "skipped": (manifest.get("counts") or {}).get("skipped"),
                "capped": bool(isinstance((manifest.get("counts") or {}).get("skipped"), dict)
                               and (manifest.get("counts") or {}).get("skipped", {}).get("page_limit")),
            },
            "missing_values": {
                "status": "0 means no HTTP response was received",
                "indexability": "unknown means the directive could not be read",
                "absence": "a missing file means that stage did not run; it is not a zero",
            },
        }
        archive.writestr("index.json", json.dumps(index, ensure_ascii=False, indent=2))
    return buffer.getvalue()


def _meta(name: str) -> dict:
    meta = dict(FILE_META.get(name, {"format": Path(name).suffix.lstrip("."), "grain": "", "identifiers": [],
                                     "join_keys": []}))
    meta.setdefault("missing_values", [])
    return meta