"""Evidence-backed offline checks against the pages actually observed."""
from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from seo_analysis.analysis import canon
from seo_analysis.analysis.analyze import load_snapshot
from seo_analysis.core.artifacts import write_json
from seo_analysis.core.urls import url_key
from seo_analysis.reporting.report import write_csv

CHECKS = ("technical", "sitemap", "links", "broken-links", "canonicals", "schema", "hreflang", "assets")
MARKUP_FIELDS = {"all": {"links", "schema", "alternates", "assets"}, "sitemap": {"links"},
                 "links": {"links"}, "broken-links": {"links"}, "schema": {"schema"},
                 "hreflang": {"alternates"}, "assets": {"assets"}}


@dataclass
class SnapshotInput:
    in_dir: str
    check: str = "all"
    source_run_id: str | None = None


@dataclass
class CompareInput:
    before: str
    after: str
    before_run_id: str | None = None
    after_run_id: str | None = None


def source_info(directory):
    directory = Path(directory)
    manifest = directory / "crawl_manifest.json"
    data = json.loads(manifest.read_text(encoding="utf-8")) if manifest.is_file() else {}
    config = data.get("config", {})
    return {"snapshot": str(directory.resolve()), "status": config.get("status", "unknown"),
            "origin": config.get("origin"), "coverage": data.get("counts", {}),
            "limit": config.get("max_pages"), "target": config.get("target"), "kind": config.get("kind")}


def check_snapshot(ctx, request):
    if request.check not in (*CHECKS, "all"):
        raise ValueError("Unknown snapshot check.")
    pages = load_snapshot(Path(request.in_dir) / "snapshot.jsonl")
    source = source_info(request.in_dir)
    index = {url_key(p["url"]): p for p in pages}
    for p in pages:
        if p.get("final_url") and p["fetch_state"].startswith("ok"):
            index.setdefault(url_key(p["final_url"]), p)
    canonical = canon.analyze(pages)
    rows = []
    missing = Counter()
    required_markup = MARKUP_FIELDS.get(request.check, set())

    def emit(check, p, observation, value="", target=""):
        if request.check in (check, "all"):
            rows.append({"check": check, "url": p["url"], "evidence": p.get("evidence_id") or p["url"],
                         "observation": observation, "value": value, "target": target})

    for p in pages:
        emit("technical", p, p["fetch_state"], p.get("effective_indexability"))
        emit("sitemap", p, p.get("discovery_method", "unknown"), p.get("sitemap_source"), p.get("final_url"))
        if p["fetch_state"].startswith("ok"):
            for name in ("title", "meta", "h1"):
                if not p.get(name):
                    emit("technical", p, "missing-" + name)
            c = canonical[p["url"]]
            emit("canonicals", p, c["relationship"], c["issues"], c["candidates"])
        else:
            continue
        facts = p.get("markup")
        if facts is None:
            if required_markup:
                missing["markup unavailable"] += 1
            continue
        if required_markup - facts.keys():
            missing["markup fields unavailable"] += 1
        if required_markup and (facts.get("limited") or p["fetch_state"] == "ok_truncated"):
            missing["incomplete markup"] += 1
        for href in facts.get("links", ()):
            if urlsplit(href).netloc.lower() != urlsplit(p["final_url"]).netloc.lower():
                continue
            target = index.get(url_key(href))
            state = "unobserved" if target is None else target["fetch_state"]
            emit("links", p, state, "", href)
            if target and target["final_status"] >= 400:
                emit("broken-links", p, "observed-http-error", target["final_status"], href)
            if target is None and p.get("discovery_method") == "sitemap":
                emit("sitemap", p, "linked target absent from observed sitemap inventory", "", href)
        for info in facts.get("schema", ()):
            emit("schema", p, info["state"], ", ".join(info["types"]))
        for lang, href in facts.get("alternates", ()):
            target = index.get(url_key(href))
            target_markup = (target or {}).get("markup") or {}
            if not re.fullmatch(r"(?:[a-zA-Z]{2,3}(?:-[a-zA-Z0-9]{2,8})*|x-default)", lang, re.I):
                state = "invalid language tag shape"
            elif "alternates" not in target_markup:
                state = "return link unverified"
            elif any(url_key(u) == url_key(p["final_url"]) for _, u in target_markup["alternates"]):
                state = "return link observed"
            else:
                state = "return link not observed"
            emit("hreflang", p, state, lang, href)
        for asset in facts.get("assets", ()):
            emit("assets", p, asset["kind"], asset["alt_state"], asset["url"])
            if p["final_url"].startswith("https://") and asset["url"].startswith("http://"):
                emit("assets", p, "mixed content reference", "", asset["url"])
    incomplete = bool(missing) or source["status"] != "succeeded"
    write_json(ctx.directory / "checks.json", dict(schema_version=1, source=source, missing=missing, observations=rows))
    fields = ("check", "url", "evidence", "observation", "value", "target")
    write_csv(ctx.directory / "checks.csv", fields, ([r[k] for k in fields] for r in rows))
    return dict(status="partial" if incomplete else "succeeded", counts=dict(pages=len(pages), observations=len(rows)),
                warnings=[f"{k}: {v}" for k, v in missing.items()] + ([f"Source: {source['status']}"] if source["status"] != "succeeded" else []))


def compare_findings(directories):
    reports = []
    for directory in directories:
        path = Path(directory) / "findings.json"
        if path.is_symlink() or not path.is_file():
            return None
        findings = json.loads(path.read_text(encoding="utf-8"))["findings"]
        reports.append({(row["rule"], tuple(sorted(url_key(url) for url in row["urls"])), row["detail"]): row
                        for row in findings if row.get("urls")})
    before, after = reports
    return [{"state": "reported only before" if key in before else "reported only after",
             "finding": before[key] if key in before else after[key]}
            for key in sorted(before.keys() ^ after.keys())]


def compare_snapshots(ctx, request):
    sources = [source_info(d) for d in (request.before, request.after)]
    if not sources[0]["origin"] or sources[0]["origin"] != sources[1]["origin"]:
        raise ValueError("Comparison requires two crawl manifests for the same origin.")
    indexes = [{url_key(p["url"]): p for p in load_snapshot(Path(d) / "snapshot.jsonl")}
               for d in (request.before, request.after)]
    rows = []
    fields = ("final_status", "final_url", "fetch_state", "effective_indexability", "title", "meta", "h1",
              "canonicals_html", "canonicals_header", "content_hash")
    for key in sorted(indexes[0].keys() | indexes[1].keys()):
        a, b = (index.get(key) for index in indexes)
        if a is None or b is None:
            state = "only observed after" if a is None else "only observed before"
            changes = {}
        else:
            changes = {f: [a[f], b[f]] for f in fields if f in a and f in b and a[f] != b[f]}
            state = "changed" if changes else "unchanged observed fields"
        rows.append(dict(url=key, state=state, changes=changes,
                         evidence=[p.get("evidence_id") if p else None for p in (a, b)]))
    findings = compare_findings((request.before, request.after))
    write_json(ctx.directory / "comparison.json", dict(schema_version=1, sources=sources, pages=rows, findings=findings))
    write_csv(ctx.directory / "comparison.csv", ["URL", "Observation", "Changed fields"],
              ([r["url"], r["state"], ", ".join(r["changes"])] for r in rows))
    if findings is not None:
        write_csv(ctx.directory / "finding_changes.csv", ["Observation", "Rule", "Detail", "URLs"],
                  ([r["state"], r["finding"]["rule"], r["finding"]["detail"], " ".join(r["finding"]["urls"])] for r in findings))
    warnings = [f"{s['snapshot']}: {s['status']}" for s in sources if s["status"] != "succeeded"]
    return dict(status="partial" if warnings else "succeeded", counts=dict(Counter(r["state"] for r in rows)), warnings=warnings)
