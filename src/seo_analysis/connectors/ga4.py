"""Read GA4 web landing-page sessions and key events from a selected property."""
from dataclasses import dataclass
from datetime import date, datetime, timezone
from hashlib import sha256
import re
from urllib.parse import urlsplit

from seo_analysis.connectors.google import GoogleConnection, google_json, note_egress
from seo_analysis.connectors.gsc import to_float
from seo_analysis.core.artifacts import write_json
from seo_analysis.core.network import HttpOrigin
from seo_analysis.reporting.report import write_csv

API = "https://analyticsdata.googleapis.com/v1beta"
DIMENSION = "landingPagePlusQueryString"
METRICS = {"sessions": "sessions", "keyEvents": "conversions"}
BATCH_SIZE = 5000
MAX_ROWS = 50000


@dataclass
class LandingPagesInput:
    start: str
    end: str
    origin: str = ""
    stream_id: str = ""
    channel: str = ""
    max_rows: int = MAX_ROWS


def _exact_filter(field, value):
    return {"filter": {"fieldName": field, "stringFilter": {"matchType": "EXACT", "value": value}}}


def _decode_batch(response, limit):
    total = response.get("rowCount", 0)
    batch = response.get("rows", [])
    if (type(total) is not int or total < 0 or not isinstance(batch, list)
            or len(batch) > min(limit, total)):
        raise RuntimeError("Google returned an unexpected GA4 row count.")
    if not batch:
        return total, batch, ()
    try:
        dimension_headers = [h["name"] for h in response["dimensionHeaders"]]
        metric_headers = [h["name"] for h in response["metricHeaders"]]
        if dimension_headers != [DIMENSION] or sorted(metric_headers) != sorted(METRICS):
            raise ValueError
    except (KeyError, TypeError, ValueError):
        raise RuntimeError("Google returned unexpected GA4 report columns.") from None
    return total, batch, metric_headers


def _decode_row(item, metric_headers, number):
    try:
        [dimension] = item["dimensionValues"]
        path = dimension["value"]
        values = item["metricValues"]
        if not isinstance(path, str) or len(values) != len(metric_headers):
            return None
        # GA4 encodes metrics as strings. Missing values stay null, including when key events are unavailable.
        metrics = {METRICS[name]: to_float(value.get("value")) for name, value in zip(metric_headers, values)}
    except (AttributeError, KeyError, TypeError, ValueError):
        return None
    return {"row": number, "url": path, **metrics}


def landing_pages(ctx, request):
    start, end = date.fromisoformat(request.start), date.fromisoformat(request.end)
    if start > end:
        raise ValueError("The start date must be on or before the end date.")
    if not 1 <= request.max_rows <= MAX_ROWS:
        raise ValueError(f"Choose between 1 and {MAX_ROWS:,} rows.")
    origin = request.origin
    if origin:
        HttpOrigin.from_url(origin)
        parts = urlsplit(origin)
        if parts.path not in ("", "/") or "?" in origin or "#" in origin:
            raise ValueError("Use an origin without a path, query or fragment.")
        origin = f"{parts.scheme}://{parts.netloc}"

    filters = [_exact_filter("platform", "web")]
    if request.stream_id:
        if not re.fullmatch(r"[0-9]+", request.stream_id):
            raise ValueError("Use the numeric GA4 web stream ID.")
        filters.append(_exact_filter("streamId", request.stream_id))
    if request.channel:
        filters.append(_exact_filter("sessionDefaultChannelGroup", request.channel))
    dimension_filter = filters[0] if len(filters) == 1 else {"andGroup": {"expressions": filters}}
    body = {
        "dateRanges": [{"startDate": start.isoformat(), "endDate": end.isoformat()}],
        "dimensions": [{"name": DIMENSION}],
        "metrics": [{"name": name} for name in METRICS],
        "dimensionFilter": dimension_filter,
        "orderBys": [{"dimension": {"dimensionName": DIMENSION}}],
        "returnPropertyQuota": True,
    }

    rows, warnings = [], []
    seen = set()
    metadata = {}
    quota = None
    received = skipped = requests = 0
    total = None
    partial = False
    connection = GoogleConnection(ctx.workspace, ctx.project, "ga4")
    with connection.session() as (property_id, session):
        if not re.fullmatch(r"properties/[0-9]+", property_id):
            raise ValueError("Reconnect to a valid GA4 property.")
        endpoint = f"{API}/{property_id}:runReport"
        note_egress(ctx, endpoint, "Fetch GA4 web landing-page sessions and key events")
        max_requests = (request.max_rows + BATCH_SIZE - 1) // BATCH_SIZE
        while received < request.max_rows and requests < max_requests:
            limit = min(BATCH_SIZE, request.max_rows - received)
            requests += 1
            try:
                response = google_json(session, "POST", endpoint, json=body | {
                    "offset": str(received), "limit": str(limit),
                })
                reported, batch, metric_headers = _decode_batch(response, limit)
            except RuntimeError as exc:
                if received == 0:
                    raise
                partial = True
                warnings.append(f"Stopped after {received} source rows. {exc}")
                break

            if isinstance(response.get("metadata"), dict):
                for key, value in response["metadata"].items():
                    if key in ("subjectToThresholding", "dataLossFromOtherRow"):
                        metadata[key] = bool(metadata.get(key) or value)
                    elif key != "samplingMetadatas" or value:
                        metadata[key] = value
            if isinstance(response.get("propertyQuota"), dict):
                quota = response["propertyQuota"]
            if total is not None and total != reported:
                partial = True
                warnings.append("The GA4 row count changed during pagination.")
            total = reported

            for number, item in enumerate(batch, received + 1):
                row = _decode_row(item, metric_headers, number)
                if row is None or row["url"] in seen:
                    skipped += 1
                    continue
                seen.add(row["url"])
                rows.append(row)
            received += len(batch)
            if received >= total:
                break
            if not batch:
                partial = True
                warnings.append("GA4 returned an empty batch before the reported row count.")
                break

    capped = total is not None and received >= request.max_rows and received < total
    if (not capped and not partial and total is not None and received < total
            and requests == max_requests):
        partial = True
        warnings.append("Reached the request limit before all reported GA4 rows were retrieved.")
    if capped:
        warnings.append("Reached the selected row limit before all reported GA4 rows were retrieved.")
    if skipped:
        warnings.append(f"Skipped {skipped} duplicate or malformed GA4 rows.")
    if metadata.get("subjectToThresholding"):
        warnings.append("GA4 flagged this report as subject to privacy thresholds.")
    if metadata.get("dataLossFromOtherRow") or "(other)" in seen:
        warnings.append("GA4 grouped some values into its (other) bucket.")
    if metadata.get("samplingMetadatas"):
        warnings.append("GA4 included sampling metadata.")
    if not received:
        warnings.append("GA4 returned no rows for this selection.")
    partial = partial or bool(capped or skipped or metadata.get("subjectToThresholding")
                              or metadata.get("dataLossFromOtherRow") or "(other)" in seen
                              or metadata.get("samplingMetadatas"))

    path = ctx.directory / "normalized.csv"
    fields = ["row", "url", *METRICS.values()]
    write_csv(path, fields, ([row[field] for field in fields] for row in rows))
    source = {
        "kind": "ga4", "provider": "Google Analytics 4", "property": property_id,
        "retrieval": "GA4 Data API", "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "period_start": start.isoformat(), "observed": end.isoformat(), "locale": "", "device": "",
        "landing_origin": origin, "dimensions": [DIMENSION], "metrics": list(METRICS),
        "filters": dimension_filter, "stream_id": request.stream_id, "channel": request.channel,
        "response_metadata": metadata, "property_quota": quota, "reported_rows": total,
        "filename": path.name, "sha256": sha256(path.read_bytes()).hexdigest(),
        "skipped": skipped, "capped": capped, "partial": partial, "requests": requests,
        "limitations": [
            "Sessions and key events have different definitions and units.",
            "GA4 landing paths do not identify the landing hostname. Any supplied origin is an operator assertion.",
            "Dates follow the GA4 property's reporting time zone.",
        ],
    }
    write_json(ctx.directory / "dataset.json", {"schema_version": 1, "source": source, "rows": rows})
    return {"status": "partial" if partial else "succeeded", "warnings": warnings,
            "counts": {"rows": len(rows), "received": received, "reported": total, "skipped": skipped, "requests": requests}}
