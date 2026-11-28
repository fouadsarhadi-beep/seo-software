"""Normalize selected exports locally, keeping source, period and original row identity."""

import csv
from dataclasses import dataclass, field
from datetime import date
from hashlib import sha256
from io import BytesIO, StringIO
from pathlib import Path
from xml.etree.ElementTree import ParseError
from zipfile import BadZipFile, ZipFile

from defusedxml import ElementTree

from seo_analysis.connectors.gsc import to_float
from seo_analysis.core.artifacts import write_json
from seo_analysis.reporting.report import write_csv


@dataclass
class ExportInput:
    file: str
    kind: str
    provider: str
    observed: str
    locale: str = ""
    device: str = ""
    period_start: str = ""
    mapping: dict = field(default_factory=dict)
    source_filename: str = ""


ALIASES = {
    "query": ("query", "keyword", "search query", "top queries", "عبارت"),
    "url": (
        "url",
        "page",
        "top pages",
        "landing page",
        "landing page + query string",
        "position url",
        "target url",
    ),
    "source_url": ("source url", "referring page url", "referring page", "source_url"),
    "rank": ("position", "rank", "average position"),
    "volume": ("volume", "search volume"),
    "clicks": ("clicks",),
    "impressions": ("impressions",),
    "sessions": ("sessions", "organic sessions"),
    "conversions": ("conversions", "key events"),
    "title": ("title", "question", "post title", "topic"),
    "published": ("published", "publication date", "pubdate"),
}
REQUIRED = {
    "keywords": ("query",),
    "serp": ("query", "url", "rank"),
    "gsc": ("clicks", "impressions"),
    "ga4": ("url", "sessions"),
    "community": ("title", "url"),
    "backlinks": ("source_url", "url"),
}
METRICS = {"rank", "volume", "clicks", "impressions", "sessions", "conversions"}


def feed_records(raw):
    try:
        root = ElementTree.fromstring(raw)
    except ParseError as exc:
        raise ValueError(f"Invalid feed XML: {exc}") from None
    if root.tag.rsplit("}", 1)[-1].lower() not in ("rss", "feed", "rdf"):
        raise ValueError("Expected an RSS or Atom feed.")
    for entry in root.iter():
        if entry.tag.rsplit("}", 1)[-1] not in ("entry", "item"):
            continue
        row = {"title": "", "url": "", "published": ""}
        for tag in entry:
            field = tag.tag.rsplit("}", 1)[-1]
            if field == "title":
                row["title"] = "".join(tag.itertext()).strip()
            elif field == "link" and tag.get("rel", "alternate") == "alternate":
                row["url"] = tag.get("href") or tag.text
            elif field in ("published", "pubDate", "date") or (field == "updated" and not row["published"]):
                row["published"] = (tag.text or "").strip()
        yield row


def records(path, raw, kind):
    if path.suffix.lower() in (".rss", ".atom", ".xml") and kind == "community":
        yield from feed_records(raw)
        return
    if path.suffix.lower() == ".xlsx":
        from openpyxl import load_workbook

        try:
            archive = ZipFile(BytesIO(raw))
        except BadZipFile as exc:
            raise ValueError("Invalid XLSX archive.") from exc
        with archive:
            if sum(item.file_size for item in archive.infolist()) > 100_000_000:
                raise ValueError("Expanded workbook exceeds 100 MB.")
        try:
            book = load_workbook(BytesIO(raw), read_only=True, data_only=True, keep_links=False)
        except (BadZipFile, KeyError, ParseError) as exc:
            raise ValueError("Invalid XLSX workbook structure.") from exc
        try:
            rows = iter(book.active.values)
            header = next(rows, ())
            for row in rows:
                yield dict(zip(header, row))
        finally:
            book.close()
        return
    if path.suffix.lower() not in (".csv", ".tsv", ".txt"):
        raise ValueError("Select CSV, TSV, XLSX or a community RSS/Atom feed.")
    encoding = "utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
    stream = StringIO(raw.decode(encoding), newline="")
    # GA4 prefixes CSV exports with comment lines identifying the property and report.
    start = stream.tell()
    if kind == "ga4":
        for line in stream:
            if line.strip() and not line.startswith("#"):
                break
            start = stream.tell()
        stream.seek(start)
    try:
        dialect = csv.Sniffer().sniff(stream.read(4096), delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    stream.seek(start)
    try:
        yield from csv.DictReader(stream, dialect=dialect)
    except csv.Error as exc:
        raise ValueError(f"Invalid delimited export: {exc}") from exc


def import_export(ctx, request):
    if request.kind not in REQUIRED or not request.provider.strip():
        raise ValueError("Choose a supported export kind and identify the source.")
    end = date.fromisoformat(request.observed)
    if request.period_start and date.fromisoformat(request.period_start) > end:
        raise ValueError("Period start must precede the observation date.")
    if (
        not isinstance(request.mapping, dict)
        or set(request.mapping) - ALIASES.keys()
        or any(not isinstance(v, str) for v in request.mapping.values())
    ):
        raise ValueError("Column mappings use normalized field names as keys.")
    path = Path(request.file)
    with path.open("rb") as file:
        raw = file.read(20_000_001)
    if len(raw) > 20_000_000:
        raise ValueError("Select an export of 20 MB or less.")
    rows, skipped, capped, mapping = [], 0, False, {}
    for number, source in enumerate(records(path, raw, request.kind), 1):
        if number > 50000:
            capped = True
            break
        if number == 1:
            headers = {str(h).strip().casefold(): h for h in source if h is not None}
            for field_name, aliases in ALIASES.items():
                if field_name in request.mapping:
                    column = request.mapping[field_name]
                    if column not in source:
                        raise ValueError(f"Missing mapped column: {column}")
                    mapping[field_name] = column
                else:
                    for alias in aliases:
                        if alias in headers:
                            mapping[field_name] = headers[alias]
                            break
            missing = set(REQUIRED[request.kind]) - mapping.keys()
            if request.kind == "gsc" and not ({"query", "url"} & mapping.keys()):
                raise ValueError("A Search Console export requires a page or query column.")
            if missing:
                raise ValueError("Missing required columns: " + ", ".join(sorted(missing)))
        row = {"row": number}
        for name, column in mapping.items():
            value = source.get(column)
            row[name] = to_float(value) if name in METRICS else str(value or "").strip()
        if any(row.get(key) in (None, "") for key in REQUIRED[request.kind] if key not in METRICS):
            skipped += 1
            continue
        if request.kind == "gsc" and not (row.get("url") or row.get("query")):
            skipped += 1
            continue
        rows.append(row)
    if not rows:
        raise ValueError("No usable rows in the selected export.")
    provenance = dict(
        kind=request.kind,
        provider=request.provider,
        observed=end.isoformat(),
        locale=request.locale,
        device=request.device,
        period_start=request.period_start,
        filename=request.source_filename or path.name,
        mapping=mapping,
        sha256=sha256(raw).hexdigest(),
        retrieval="local import",
        skipped=skipped,
        capped=capped,
    )
    write_json(ctx.directory / "dataset.json", {"schema_version": 1, "source": provenance, "rows": rows})
    columns = ["row", *mapping]
    write_csv(ctx.directory / "normalized.csv", columns, ([r[c] for c in columns] for r in rows))
    warnings = (["Read the first 50,000 rows."] if capped else []) + (
        [f"Skipped {skipped} incomplete rows."] if skipped else []
    )
    return dict(
        status="partial" if warnings else "succeeded",
        counts={"rows": len(rows), "skipped": skipped},
        warnings=warnings,
    )
