"""Explicit, single-target Google performance reports and local lab imports."""
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from ipaddress import ip_address
import json
import re
from urllib.parse import urlsplit

import requests

from seo_analysis.analysis.lighthouse import REPORT_LIMIT, import_lighthouse, number, summarize_lighthouse
from seo_analysis.connectors.google import APP_NAME, native_keyring
from seo_analysis.core.artifacts import write_json
from seo_analysis.core.network import HttpOrigin

PSI_URL = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
CRUX_URL = "https://chromeuxreport.googleapis.com/v1/records:queryRecord"
CRUX_FIELDS = {
    "largest_contentful_paint": ("LCP", "ms"),
    "interaction_to_next_paint": ("INP", "ms"),
    "cumulative_layout_shift": ("CLS", "score"),
    "first_contentful_paint": ("FCP", "ms"),
    "experimental_time_to_first_byte": ("TTFB", "ms"),
}
FORM_FACTORS = ("ALL_FORM_FACTORS", "PHONE", "DESKTOP", "TABLET")


@dataclass
class PageSpeedInput:
    url: str
    strategy: str = "mobile"
    use_key: bool = False


@dataclass
class CruxInput:
    target: str
    scope: str = "url"
    form_factor: str = "ALL_FORM_FACTORS"


@dataclass
class LighthouseInput:
    report: str


def performance_key(workspace, action="get", value=None):
    vault = native_keyring()
    identity = sha256(str(workspace.data_dir.resolve()).encode()).hexdigest()
    name = f"performance:{identity}"
    try:
        if action == "set":
            vault.set_password(APP_NAME, name, value)
        else:
            existing = vault.get_password(APP_NAME, name)
            if action == "delete" and existing is not None:
                vault.delete_password(APP_NAME, name)
            return existing
    except Exception:
        raise RuntimeError("Unable to access the OS credential store.") from None
    return None


def validate_key(value):
    if not re.fullmatch(r"[A-Za-z0-9_-]{20,160}", value):
        raise ValueError("Enter a valid Google API key.")
    return value


def _public_target(value, *, require_origin=False):
    origin = HttpOrigin.from_url(value)
    parts = urlsplit(value)
    if "#" in value:
        raise ValueError("Supply a URL without a fragment.")
    if require_origin and (parts.path not in ("", "/") or "?" in value):
        raise ValueError("Supply an origin without a path or query.")
    host = origin.host.rstrip(".")
    try:
        address = ip_address(host)
    except ValueError:
        if "." not in host or host.endswith((".localhost", ".local", ".internal", ".test", ".invalid")):
            raise ValueError("Google performance APIs require a public website.") from None
    else:
        if not address.is_global:
            raise ValueError("Google performance APIs require a public website.")
    return f"{parts.scheme}://{parts.netloc}" if require_origin else value


def _request(ctx, method, endpoint, *, key=None, **kwargs):
    ctx.data_egress.append({"method": method, "endpoint": endpoint, "purpose": "Measure the selected public target"})
    headers = {"X-Goog-Api-Key": key} if key else {}
    try:
        with requests.Session() as session, session.request(
            method, endpoint, headers=headers, allow_redirects=False,
            timeout=(5, 90 if endpoint == PSI_URL else 30), stream=True, **kwargs,
        ) as response:
            if not 200 <= response.status_code < 300 and not (endpoint == CRUX_URL and response.status_code == 404):
                raise RuntimeError(f"Google performance API returned HTTP {response.status_code}.")
            raw = bytearray()
            for chunk in response.iter_content(chunk_size=65536):
                raw.extend(chunk)
                if len(raw) > REPORT_LIMIT:
                    raise RuntimeError("The Google performance response exceeded 25 MB.")
            payload = json.loads(raw)
            code = response.status_code
    except (requests.RequestException, ValueError):
        raise RuntimeError("Unable to read the Google performance response.") from None
    if not isinstance(payload, dict):
        raise RuntimeError("Google returned an unexpected performance response.")
    return code, payload


def _store(ctx, report, warnings, status):
    write_json(ctx.directory / "performance.json", {
        "schema_version": 1, "retrieved_at": datetime.now(timezone.utc).isoformat(), "status": status, **report,
    })
    return {"status": "partial" if status != "available" else "succeeded",
            "counts": {"measurements": sum(m.get("value", m.get("p75")) is not None
                                           for m in report["metrics"].values())}, "warnings": warnings}


def _lab_report(ctx, summary, source, **extra):
    warnings = []
    runtime_error = summary["runtime_error"]
    if runtime_error:
        warnings.append("Lighthouse could not complete the lab run. See runtime_error in performance.json.")
    if not any(item["value"] is not None for item in summary["metrics"].values()):
        warnings.append("This Lighthouse report contains no supported lab measurements.")
    return _store(ctx, {**summary, **extra, "source": source, "kind": "lab"}, warnings,
                  "partial" if warnings else "available")


def pagespeed(ctx, request):
    target = _public_target(request.url)
    if request.strategy not in ("mobile", "desktop"):
        raise ValueError("Choose mobile or desktop.")
    key = performance_key(ctx.workspace) if request.use_key else None
    if request.use_key and not key:
        raise ValueError("Save a Google performance API key first.")
    _, payload = _request(ctx, "GET", PSI_URL, key=key,
                          params={"url": target, "strategy": request.strategy, "category": "performance"})
    return _lab_report(ctx, summarize_lighthouse(payload.get("lighthouseResult")), "PageSpeed Insights",
                       submitted_url=target, requested_strategy=request.strategy)


def crux(ctx, request):
    if request.scope not in ("url", "origin") or request.form_factor not in FORM_FACTORS:
        raise ValueError("Choose URL or origin scope and a supported CrUX form factor.")
    target = _public_target(request.target, require_origin=request.scope == "origin")
    key = performance_key(ctx.workspace)
    if not key:
        raise ValueError("Save a Google performance API key first.")
    query = {request.scope: target, "metrics": list(CRUX_FIELDS)}
    if request.form_factor != "ALL_FORM_FACTORS":
        query["formFactor"] = request.form_factor
    code, payload = _request(ctx, "POST", CRUX_URL, key=key, json=query)
    report = {"source": "Chrome UX Report", "kind": "field", "target": target,
              "scope": request.scope, "form_factor": request.form_factor, "metrics": {}}
    if code == 404:
        error = payload.get("error")
        if isinstance(error, dict) and error.get("status") == "NOT_FOUND":
            return _store(ctx, report, ["CrUX returned no field record for this target and form factor."], "no_data")
        raise RuntimeError("CrUX returned HTTP 404 without a field-data result.")
    record = payload.get("record")
    if not isinstance(record, dict) or not isinstance(record.get("metrics"), dict):
        raise RuntimeError("Google returned an unexpected CrUX record.")
    for field, (label, unit) in CRUX_FIELDS.items():
        value = record["metrics"].get(field, {})
        if not isinstance(value, dict):
            value = {}
        percentiles = value.get("percentiles")
        p75 = number(percentiles.get("p75"), decimal_string=True) if isinstance(percentiles, dict) else None
        report["metrics"][label] = {"p75": p75, "unit": unit, "histogram": value.get("histogram")}
    report.update(record_key=record.get("key"), collection_period=record.get("collectionPeriod"),
                  url_normalization=payload.get("urlNormalizationDetails"))
    if not any(item["p75"] is not None for item in report["metrics"].values()):
        return _store(ctx, report, ["CrUX returned a record without usable requested percentiles."], "partial")
    return _store(ctx, report, [], "available")


def lighthouse(ctx, request):
    return _lab_report(ctx, import_lighthouse(request.report), "Local Lighthouse report")
