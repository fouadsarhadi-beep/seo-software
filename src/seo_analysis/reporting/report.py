"""CSV writing (UTF-8 with BOM so Excel shows Persian) with spreadsheet-formula protection."""
from __future__ import annotations

import csv
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

from seo_analysis import SCHEMA_VERSION, __version__

_DANGEROUS = ("=", "+", "-", "@", "\t", "\r", "\n", "\uff1d", "\uff0b", "\uff0d", "\uff20")


def csv_safe(value, guard: bool = True):
    """Page titles are untrusted text. A cell starting with = + - @ would run as a formula in Excel.
    Quoting does not prevent that, so such cells get a leading apostrophe (OWASP guidance)."""
    if guard and isinstance(value, str) and value and value.startswith(_DANGEROUS):
        return "'" + value
    return value


def write_csv(path, header, rows, guard: bool = True):
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        for r in rows:
            w.writerow([csv_safe(c, guard) for c in r])


def write_manifest(path, command: str, config: dict, counts: dict, files: list, warnings: list, limitations: list):
    try:
        import requests, bs4
        pkgs = {"requests": requests.__version__, "beautifulsoup4": bs4.__version__}
    except Exception:  # pragma: no cover
        pkgs = {}
    data = {"tool_version": __version__, "schema_version": SCHEMA_VERSION, "command": command,
            "written_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "python": sys.version.split()[0], "platform": platform.platform(), "packages": pkgs,
            "config": config, "counts": counts, "files": files, "warnings": warnings, "limitations": limitations}
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
