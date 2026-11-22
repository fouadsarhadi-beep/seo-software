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
    counts, sources = Counter(), []
    for seq, (run_id, dataset) in enumerate(datasets, 1):
        s = dataset["source"]
        sources.append({"run_id": run_id, **s})
        rows = []
        for r in dataset["rows"]:
            raw = r.get("url", "")
            full = (
                base + raw if raw.startswith("/") and not raw.startswith("//") and s["kind"] == "ga4" else raw
            )
            state, evidence = ("unmatched" if raw else "unattributed query"), []
            if origin.allows(full):
                for kind, index in indexes.items():
                    ids = index.get(url_key(full), set())
                    if ids:
                        state, evidence = kind if len(ids) == 1 else "ambiguous", sorted(ids)
                        break
            counts[state] += 1
            rows.append(
                [
                    r["row"],
                    raw,
                    state,
                    ", ".join(evidence),
                    r.get("query"),
                    *[r.get(k) for k in ("clicks", "impressions", "rank", "sessions", "conversions")],
                ]
            )
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
            ],
            rows,
        )
    table(
        "Sources",
        ["Run", "Provider", "Kind", "Period start", "Observation date", "Locale", "Device", "SHA-256"],
        (
            [
                s[k]
                for k in (
                    "run_id",
                    "provider",
                    "kind",
                    "period_start",
                    "observed",
                    "locale",
                    "device",
                    "sha256",
                )
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
    partial = crawl_source["status"] != "succeeded" or any(s["skipped"] or s["capped"] for s in sources)
    write_json(
        ctx.directory / "report.json",
        {
            "schema_version": 1,
            "crawl": directory.name,
            "crawl_source": crawl_source,
            "sources": sources,
            "matches": counts,
            "looker_studio_url": request.report_url,
            "workbook": dest.name,
        },
    )
    return {
        "status": "partial" if partial else "succeeded",
        "counts": {"pages": len(records), "sources": len(sources), "matches": dict(counts)},
        "warnings": [
            "GA4 path-only rows use the selected crawl origin. Each source retains its own units and period."
        ],
    }
