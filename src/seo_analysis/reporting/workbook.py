"""A local reporting workbook with source-level measurements and crawl identity matches."""

from collections import Counter, defaultdict
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
from tempfile import NamedTemporaryFile
from urllib.parse import urlsplit

from seo_analysis.analysis.checks import source_info

from seo_analysis.analysis.analyze import load_snapshot
from seo_analysis.core.artifacts import write_json
from seo_analysis.core.network import HttpOrigin
from seo_analysis.core.urls import url_key
from seo_analysis.reporting.report import csv_safe


@dataclass
class WorkbookInput:
    crawl: str
    datasets: tuple
    report_url: str = ""


def landing_identity(raw, source, crawl_base):
    """Resolve a landing path only with the origin available for its source."""
    if not raw or raw in ("(not set)", "(other)"):
        return "", "", "unknown landing page"
    if not raw.startswith("/") or raw.startswith("//"):
        return raw, "source URL", "unmatched"
    if "landing_origin" in source:
        origin = source["landing_origin"]
        if not origin:
            return "", "", "landing origin unknown"
        return origin + raw, "operator-selected GA4 origin and path", "unmatched"
    return crawl_base + raw, "crawl origin assumed for imported path", "unmatched"


def build_workbook(ctx, request):
    if request.report_url and not re.fullmatch(
        r"https://lookerstudio\.google\.com/(?:u/\d+/)?reporting/[a-zA-Z0-9/_-]+", request.report_url
    ):
        raise ValueError("Supply a Looker Studio HTTPS report link.")
    directory = Path(request.crawl)
    records = load_snapshot(directory / "snapshot.jsonl")
    if not records:
        raise ValueError("Select a crawl with page observations.")
    origin = HttpOrigin.from_url(records[0]["url"])
    origins = urlsplit(records[0]["url"])
    base = f"{origins.scheme}://{origins.netloc}"
    indexes = {k: defaultdict(set) for k in ("requested", "final", "declared canonical")}
    for r in records:
        eid = r.get("evidence_id") or r["url"]
        indexes["requested"][url_key(r["url"])].add(eid)
        if r.get("final_url") and r["fetch_state"].startswith("ok"):
            indexes["final"][url_key(r["final_url"])].add(eid)
        for url in (*r.get("canonicals_html", []), *r.get("canonicals_header", [])):
            indexes["declared canonical"][url_key(url)].add(eid)
    datasets = []
    for filename in request.datasets:
        dataset = json.loads((Path(filename) / "dataset.json").read_text(encoding="utf-8"))
        if dataset["source"]["kind"] not in ("gsc", "ga4"):
            raise ValueError("Reporting joins accept GSC and GA4 datasets.")
        datasets.append((Path(filename).name, dataset))

    from openpyxl import Workbook
    from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE

    book = Workbook(write_only=True)

    def table(name, columns, rows):
        sheet = book.create_sheet(name)
        sheet.freeze_panes = "A2"
        sheet.append(columns)
        for row in rows:
            sheet.append(
                [csv_safe(ILLEGAL_CHARACTERS_RE.sub("", v)[:32760]) if isinstance(v, str) else v for v in row]
            )

    table(
        "Crawl",
        ["Requested URL", "Final URL", "Status", "State", "Title", "Evidence"],
        (
            [r["url"], r["final_url"], r["final_status"], r["fetch_state"], r["title"], r.get("evidence_id")]
            for r in records
        ),
    )
    counts, sources, preview = Counter(), [], []
    for seq, (run_id, dataset) in enumerate(datasets, 1):
        s = dataset["source"]
        sources.append({"run_id": run_id, **s})
        extra = [field for field in ("date", "device", "country", "ctr") if
                 field in s.get("dimensions", ()) or (field == "ctr" and s.get("retrieval") == "Search Analytics API")]
        rows = []
        matches, examples = Counter(), defaultdict(list)
        for r in dataset["rows"]:
            raw = r.get("url", "")
            if s["kind"] == "ga4":
                full, basis, state = landing_identity(raw, s, base)
            else:
                full, basis, state = raw, "source URL" if raw else "", "unmatched" if raw else "unattributed query"
            evidence = []
            key = match_tier = ""
            if origin.allows(full):
                key = url_key(full)
                for kind, index in indexes.items():
                    ids = index.get(key, set())
                    if ids:
                        match_tier = kind
                        state, evidence = kind if len(ids) == 1 else "ambiguous", sorted(ids)
                        break
            elif full:
                try:
                    HttpOrigin.from_url(full)
                except ValueError:
                    pass
                else:
                    key = url_key(full)
                    state = "outside crawl origin"
            counts[state] += 1
            matches[state] += 1
            if len(examples[state]) < 3:
                examples[state].append({"row": r["row"], "url": raw[:600], "query": (r.get("query") or "")[:300],
                                        "evidence": evidence[:3], "clicks": r.get("clicks"),
                                        "impressions": r.get("impressions"), "sessions": r.get("sessions"),
                                        "conversions": r.get("conversions")})
            rows.append(
                [
                    r["row"],
                    raw,
                    state,
                    ", ".join(evidence),
                    r.get("query"),
                    *[r.get(k) for k in ("clicks", "impressions", "rank", "sessions", "conversions")],
                    full, key, basis, match_tier,
                    *[r.get(k) for k in extra],
                ]
            )
        preview.append({"run_id": run_id, "matches": dict(matches), "examples": dict(examples)})
        table(
            f"{s['kind'].upper()} {seq}",
            [
                "Source row",
                "Source URL",
                "Match",
                "Crawl evidence",
                "Query",
                "Clicks",
                "Impressions",
                "Average position",
                "Sessions",
                "Key events",
                "Candidate URL",
                "Normalized candidate",
                "URL basis",
                "Match tier",
                *[field.upper() if field == "ctr" else field.capitalize() for field in extra],
            ],
            rows,
        )
    table(
        "Sources",
        ["Run", "Provider", "Kind", "Period start", "Observation date", "Locale", "Device", "SHA-256",
         "Retrieval", "Property", "Landing origin", "Channel", "Property time zone"],
        (
            [
                *[s[k] for k in (
                    "run_id",
                    "provider",
                    "kind",
                    "period_start",
                    "observed",
                    "locale",
                    "device",
                    "sha256",
                )],
                s.get("retrieval"), s.get("property"), s.get("landing_origin"), s.get("channel"),
                s.get("response_metadata", {}).get("timeZone"),
            ]
            for s in sources
        ),
    )
    dest = ctx.directory / "report.xlsx"
    with NamedTemporaryFile(dir=ctx.directory, prefix=".workbook-", delete=False) as temp:
        name = temp.name
    try:
        book.save(name)
        os.replace(name, dest)
    finally:
        Path(name).unlink(missing_ok=True)
    crawl_source = source_info(directory)
    partial = crawl_source["status"] != "succeeded" or any(s["skipped"] or s["capped"] or s.get("partial") for s in sources)
    write_json(
        ctx.directory / "report.json",
        {
            "schema_version": 1,
            "crawl": directory.name,
            "crawl_source": crawl_source,
            "sources": sources,
            "matches": counts,
            "preview": preview,
            "looker_studio_url": request.report_url,
            "workbook": dest.name,
        },
    )
    return {
        "status": "partial" if partial else "succeeded",
        "counts": {"pages": len(records), "sources": len(sources), "matches": dict(counts)},
        "warnings": [
            "Imported GA4 paths assume the crawl origin. API paths require an origin supplied by the operator."
        ],
    }
