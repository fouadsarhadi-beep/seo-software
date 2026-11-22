"""Bounded Search Analytics and indexed URL inspection for a selected property."""
from dataclasses import dataclass
from datetime import date, datetime, timezone
from hashlib import sha256
import math
from urllib.parse import quote, unquote, urlsplit

from seo_analysis.connectors.google import GoogleConnection, SITES_URL, google_json, note_egress
from seo_analysis.core.artifacts import write_json
from seo_analysis.core.network import HttpOrigin
from seo_analysis.reporting.report import write_csv

DIMENSIONS = ("query", "page", "date", "device", "country")
SEARCH_TYPES = ("web", "image", "video", "news")
METRICS = {"clicks": "clicks", "impressions": "impressions", "ctr": "ctr", "rank": "position"}
BATCH_SIZE = 5000
MAX_ROWS = 50000
INSPECTION_URL = "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect"


@dataclass
class SearchAnalyticsInput:
    start: str
    end: str
    dimensions: tuple[str, ...] = ("query", "page")
    search_type: str = "web"
    data_state: str = "final"
    max_rows: int = MAX_ROWS


@dataclass
class InspectionInput:
    url: str


def _numeric(value):
    # Explicit zeros survive. Missing measurements remain null in JSON and blank in CSV.
    if type(value) is int or (isinstance(value, float) and math.isfinite(value)):
        return value
    return None


def search_analytics(ctx, request):
    start, end = date.fromisoformat(request.start), date.fromisoformat(request.end)
    if start > end:
        raise ValueError("The start date must be on or before the end date.")
    dims = request.dimensions
    if (len(set(dims)) != len(dims) or set(dims) - set(DIMENSIONS)
            or not {"page", "query"} & set(dims)):
        raise ValueError("Choose distinct dimensions, including page or query.")
    if request.search_type not in SEARCH_TYPES or request.data_state not in ("final", "all"):
        raise ValueError("Unsupported Search Analytics search type or data state.")
    if not 1 <= request.max_rows <= MAX_ROWS:
        raise ValueError(f"Choose between 1 and {MAX_ROWS:,} rows.")

    columns = ["url" if dimension == "page" else dimension for dimension in dims]
    rows, seen = [], set()
    received = skipped = requests = 0
    aggregations, response_metadata = set(), {}
    warnings = []
    interrupted = False
    base = {"startDate": start.isoformat(), "endDate": end.isoformat(), "dimensions": list(dims),
            "type": request.search_type, "dataState": request.data_state, "aggregationType": "auto"}
    connection = GoogleConnection(ctx.workspace, ctx.project, "gsc")
    with connection.session() as (property_id, session):
        url = f"{SITES_URL}/{quote(property_id, safe='')}/searchAnalytics/query"
        note_egress(ctx, f"{SITES_URL}/{{selected-property}}/searchAnalytics/query", "Fetch Search Analytics rows")
        while received < request.max_rows:
            limit = min(BATCH_SIZE, request.max_rows - received)
            requests += 1
            try:
                response = google_json(session, "POST", url, json=base | {"rowLimit": limit, "startRow": received})
                batch = response.get("rows", [])
                if not isinstance(batch, list) or len(batch) > limit:
                    raise RuntimeError("Google returned an unexpected Search Analytics batch.")
            except RuntimeError as exc:
                if received == 0:
                    raise
                interrupted = True
                warnings.append(f"Stopped after {received} rows. {exc}")
                break
            aggregation = response.get("responseAggregationType")
            if isinstance(aggregation, str):
                aggregations.add(aggregation)
            if isinstance(response.get("metadata"), dict):
                response_metadata.update(response["metadata"])
            received += len(batch)
            for number, item in enumerate(batch, received - len(batch) + 1):
                keys = item.get("keys") if isinstance(item, dict) else None
                if (not isinstance(keys, list) or len(keys) != len(columns)
                        or not all(isinstance(key, str) for key in keys) or tuple(keys) in seen):
                    skipped += 1
                    continue
                seen.add(tuple(keys))
                row = dict(zip(columns, keys))
                measures = {column: _numeric(item.get(field)) for column, field in METRICS.items()}
                rows.append({"row": number, **row, **measures})
            if len(batch) < limit:
                break

    capped = received >= request.max_rows
    if capped:
        warnings.append("Reached the selected row limit. Additional rows may be available.")
    if skipped:
        warnings.append(f"Skipped {skipped} duplicate or malformed source rows.")
    if not received:
        warnings.append("Google returned no rows for this selection.")
    partial = capped or skipped > 0 or interrupted
    if request.data_state == "all":
        warnings.append("This export may include provisional Search Console data.")
    filename = "normalized.csv"
    fields = ["row", *columns, *METRICS]
    path = ctx.directory / filename
    write_csv(path, fields, ([row[field] for field in fields] for row in rows))
    source = {
        "kind": "gsc", "provider": "Google Search Console", "property": property_id,
        "retrieval": "Search Analytics API", "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "period_start": start.isoformat(), "observed": end.isoformat(), "locale": "", "device": "",
        "dimensions": list(dims), "search_type": request.search_type, "data_state": request.data_state,
        "response_aggregation": sorted(aggregations), "response_metadata": response_metadata,
        "filename": filename, "sha256": sha256(path.read_bytes()).hexdigest(),
        "skipped": skipped, "capped": capped, "partial": partial, "requests": requests,
        "limitations": [
            "Dates are interpreted in Pacific Time.",
            "Google returns top rows and can omit anonymized queries. Missing rows do not represent zero.",
        ],
    }
    write_json(ctx.directory / "dataset.json", {"schema_version": 1, "source": source, "rows": rows})
    return {"status": "partial" if partial else "succeeded", "warnings": warnings,
            "counts": {"rows": len(rows), "received": received, "skipped": skipped, "requests": requests}}


def _in_property(url, property_id):
    origin = HttpOrigin.from_url(url)
    parts = urlsplit(url)
    # Reject fragments and ambiguous path hierarchy before sending a URL to Google.
    path = unquote(parts.path or "/")
    if parts.fragment or "\\" in path or set(path.split("/")) & {".", ".."}:
        return False
    if property_id.startswith("sc-domain:"):
        domain = HttpOrigin.from_url("https://" + property_id.removeprefix("sc-domain:")).host
        return origin.host == domain or origin.host.endswith("." + domain)
    return HttpOrigin.from_url(property_id) == origin and (parts.path or "/").startswith(
        urlsplit(property_id).path or "/"
    )


def inspect_url(ctx, request):
    HttpOrigin.from_url(request.url)
    connection = GoogleConnection(ctx.workspace, ctx.project, "gsc")
    with connection.session() as (property_id, session):
        if not _in_property(request.url, property_id):
            raise ValueError("The inspection URL is outside the selected Search Console property.")
        note_egress(ctx, INSPECTION_URL, "Inspect one URL in Google's index")
        response = google_json(session, "POST", INSPECTION_URL, json={
            "inspectionUrl": request.url, "siteUrl": property_id,
        })
    result = response.get("inspectionResult")
    if not isinstance(result, dict):
        raise RuntimeError("Google returned no URL Inspection result.")
    write_json(ctx.directory / "inspection.json", {
        "schema_version": 1, "property": property_id, "url": request.url,
        "retrieved_at": datetime.now(timezone.utc).isoformat(), "result": result,
        "scope": "Google's indexed assessment, which may differ from the current live page.",
    })
    return {"counts": {"urls": 1}, "warnings": ["URL Inspection describes Google's indexed assessment."]}
