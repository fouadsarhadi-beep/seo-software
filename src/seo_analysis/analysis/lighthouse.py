"""Normalize Lighthouse lab reports from a local run or PageSpeed Insights."""
import json
import math
from pathlib import Path

REPORT_LIMIT = 25_000_000
LAB_AUDITS = {
    "first-contentful-paint": ("FCP", "ms"),
    "largest-contentful-paint": ("LCP", "ms"),
    "cumulative-layout-shift": ("CLS", "score"),
    "total-blocking-time": ("TBT", "ms"),
    "speed-index": ("Speed Index", "ms"),
    "interactive": ("Time to Interactive", "ms"),
}


def number(value, *, decimal_string=False):
    if decimal_string and isinstance(value, str):
        try:
            value = float(value)
        except ValueError:
            return None
    if type(value) is int or (isinstance(value, float) and math.isfinite(value)):
        return value
    return None


def summarize_lighthouse(data):
    if not isinstance(data, dict):
        raise ValueError("Expected a Lighthouse JSON object.")
    categories = data.get("categories", {})
    audits = data.get("audits", {})
    if not isinstance(categories, dict) or not isinstance(audits, dict) or any(
        not isinstance(item, dict) for item in categories.values()
    ) or ("categories" not in data and not data.get("runtimeError")):
        raise ValueError("Expected Lighthouse JSON with categories.")
    settings = data.get("configSettings")
    if not isinstance(settings, dict):
        settings = {}
    metrics = {}
    for key, (label, unit) in LAB_AUDITS.items():
        audit = audits.get(key)
        measurement = number(audit.get("numericValue")) if isinstance(audit, dict) else None
        metrics[label] = {"value": measurement, "unit": unit}
    return {
        "url": data.get("finalDisplayedUrl", data.get("finalUrl")),
        "requested_url": data.get("requestedUrl"),
        "time": data.get("fetchTime"),
        "version": data.get("lighthouseVersion"),
        "device": settings.get("formFactor", settings.get("emulatedFormFactor")),
        "throttling_method": settings.get("throttlingMethod"),
        "lab_scores": {key: number(item.get("score")) for key, item in categories.items()},
        "metrics": metrics,
        "runtime_error": data.get("runtimeError"),
        "run_warnings": data.get("runWarnings", []),
    }


def import_lighthouse(path):
    path = Path(path)
    with path.open("rb") as stream:
        raw = stream.read(REPORT_LIMIT + 1)
    if len(raw) > REPORT_LIMIT:
        raise ValueError("Lighthouse report exceeds 25 MB.")
    return summarize_lighthouse(json.loads(raw)) | {"source_file": path.name}
