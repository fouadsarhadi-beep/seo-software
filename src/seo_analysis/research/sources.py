"""Bounded provider requests that produce the same datasets as offline imports."""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from time import monotonic
from types import SimpleNamespace
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
from defusedxml.common import DefusedXmlException
import requests

from seo_analysis.connectors.google import native_keyring
from seo_analysis.core.artifacts import write_json
from seo_analysis.core.network import HttpOrigin
from seo_analysis.reporting.report import write_csv
from seo_analysis.research.imports import feed_records
from seo_analysis.web.crawl import TOOL_TOKEN, RobotsUnavailable, load_robots
from seo_analysis.web.fetch import Fetcher
from seo_analysis.web.transport import BudgetExceeded, ScopeError

BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"
FEED_BYTES = 2_000_000
SEARCH_BYTES = 1_000_000


@dataclass
class FeedInput:
    url: str
    max_items: int = 100


@dataclass
class BraveSearchInput:
    query: str
    country: str = "us"
    language: str = "en"
    count: int = 10
    allow_storage: bool = False


def _save(ctx, rows, columns, source, raw, warnings):
    now = datetime.now(timezone.utc)
    source.update(observed=now.date().isoformat(), retrieved_at=now.isoformat(),
                  locale=source.get("locale", ""), device="", period_start="",
                  sha256=sha256(raw).hexdigest())
    write_json(ctx.directory / "dataset.json", {"schema_version": 1, "source": source, "rows": rows})
    write_csv(ctx.directory / "normalized.csv", columns, ([row.get(field) for field in columns] for row in rows))
    if not rows:
        warnings.append("This source returned no usable observations.")
    return {"status": "partial" if source["capped"] or source["skipped"] else "succeeded",
            "counts": {"rows": len(rows), "skipped": source["skipped"]}, "warnings": warnings}


def _web_url(value, base=""):
    if not isinstance(value, str) or not value.strip():
        return ""
    try:
        url = urljoin(base, value.strip()) if base else value.strip()
        HttpOrigin.from_url(url)
        return url
    except ValueError:
        return ""


def read_feed(ctx, request):
    origin = HttpOrigin.from_url(request.url)
    if not 1 <= request.max_items <= 500:
        raise ValueError("Select between 1 and 500 items.")
    if urlsplit(request.url).fragment:
        raise ValueError("Select a feed URL without a fragment.")
    fetcher = Fetcher(TOOL_TOKEN, origin=origin, max_redirects=3, max_requests=8,
                      max_seconds=25, max_bytes=FEED_BYTES, retries=0, cancel=ctx.cancel)
    try:
        # Reuse the crawler's SSRF protection, redirect policy and robots handling.
        fetcher.robots, _ = load_robots(fetcher, request.url, SimpleNamespace(robots="respect"))
        fetcher.robots_agent = TOOL_TOKEN
        response = fetcher.get(request.url)
    except RobotsUnavailable:
        raise RuntimeError("Could not read the feed's robots.txt policy. See requests.json.") from None
    except (BudgetExceeded, ScopeError) as exc:
        raise RuntimeError(f"Feed fetch stopped. {exc}") from None
    finally:
        fetcher.session.close()
        write_json(ctx.directory / "requests.json", {"schema_version": 1, "attempts": fetcher.attempts})
        if fetcher.attempts:
            ctx.data_egress.append({"method": "GET", "origin": asdict(origin), "purpose": "Read public feed and robots.txt",
                                    "attempt_log": "requests.json"})
    if response.redirect_note.startswith("blocked_robots"):
        raise ValueError("robots.txt disallows the selected feed.")
    if response.error or response.redirect_note or response.final_status != 200:
        raise RuntimeError(f"Feed fetch failed (HTTP {response.final_status or 'unavailable'}).")
    if response.truncated:
        raise ValueError("Feed response exceeds 2 MB.")
    rows = []
    skipped = 0
    capped = False
    try:
        for index, item in enumerate(feed_records(response.raw), 1):
            if index > request.max_items:
                capped = True
                break
            url = _web_url(item.get("url"), response.final_url)
            title = item.get("title")
            if not url or not title:
                skipped += 1
                continue
            rows.append({"row": index, "title": title, "url": url, "published": item.get("published")})
    except DefusedXmlException:
        raise ValueError("Feed XML contains prohibited entities or external references.") from None
    warnings = [f"Observed the first {request.max_items} feed entries."] if capped else []
    if skipped:
        warnings.append(f"Skipped {skipped} entries without a usable title and link.")
    return _save(ctx, rows, ("row", "title", "url", "published"), {
        "kind": "community", "provider": origin.host, "retrieval": "public RSS/Atom",
        "url": request.url, "resolved_url": response.final_url, "capped": capped, "skipped": skipped,
        "limitations": ["A feed is a publisher-selected sample. Linked pages were not retrieved."],
    }, response.raw, warnings)


def brave_key(workspace, value=None, *, delete=False):
    name = sha256(str(workspace.data_dir.resolve()).encode()).hexdigest()
    vault = native_keyring("research")
    service = "SEO Analysis Software Brave Search"
    try:
        if value is not None:
            vault.set_password(service, name, value)
            return None
        saved = vault.get_password(service, name)
        if delete and saved:
            vault.delete_password(service, name)
        return saved
    except Exception:
        raise RuntimeError("Unable to access the OS credential store.") from None


def brave_search(ctx, request):
    query = request.query.strip()
    if not query or len(query) > 400 or any(ord(c) < 32 for c in query) or len(query.split()) > 50:
        raise ValueError("Select a query of up to 400 characters and 50 words.")
    if not re.fullmatch(r"[a-z]{2}", request.country) or not re.fullmatch(r"[a-z]{2,3}(?:-[a-z]{2})?", request.language):
        raise ValueError("Enter a Brave country and search language code in lowercase.")
    if not 1 <= request.count <= 20:
        raise ValueError("Select between 1 and 20 web results.")
    if not request.allow_storage:
        raise ValueError("Confirm your Brave plan permits storage using --allow-storage.")
    key = brave_key(ctx.workspace)
    if not key:
        raise ValueError("Save a Brave Search API key first.")
    params = {"q": query, "country": request.country.upper(), "search_lang": request.language,
              "count": request.count, "result_filter": "web"}
    ctx.data_egress.append({"method": "GET", "endpoint": BRAVE_URL, "fields": ["query", "country", "language"],
                            "purpose": "Fetch one sample of web search results"})
    started = monotonic()
    try:
        with requests.get(BRAVE_URL, params=params, headers={"X-Subscription-Token": key},
                          timeout=(5, 20), stream=True, allow_redirects=False) as response:
            if response.status_code != 200:
                raise RuntimeError(f"Brave Search returned HTTP {response.status_code}.")
            raw = bytearray()
            for chunk in response.iter_content(chunk_size=65536):
                raw.extend(chunk)
                if len(raw) > SEARCH_BYTES:
                    raise RuntimeError("Brave Search response exceeded 1 MB.")
            payload = json.loads(raw)
    except (requests.RequestException, ValueError):
        raise RuntimeError("Unable to read the Brave Search response.") from None
    web = payload.get("web", {}) if isinstance(payload, dict) else None
    items = web.get("results", []) if isinstance(web, dict) else None
    if not isinstance(items, list):
        raise RuntimeError("Brave returned an unexpected web result list.")
    rows = []
    skipped = 0
    for rank, item in enumerate(items[:request.count], 1):
        url = _web_url(item.get("url")) if isinstance(item, dict) else ""
        if not url:
            skipped += 1
            continue
        title = item.get("title")
        title = BeautifulSoup(title, "html.parser").get_text(" ", strip=True) if isinstance(title, str) else ""
        rows.append({"row": rank, "query": query, "url": url, "rank": rank, "title": title})
    warnings = ["This sample contains Brave web results for the selected query and locale."]
    if skipped:
        warnings.append(f"Skipped {skipped} entries without a usable URL.")
    return _save(ctx, rows, ("row", "query", "url", "rank", "title"), {
        "kind": "serp", "provider": "Brave Search", "retrieval": "Brave Search API",
        "locale": f"{request.language}-{request.country.upper()}", "country": request.country.upper(),
        "language": request.language, "requested_count": request.count, "query": query,
        "elapsed_ms": round((monotonic() - started) * 1000),
        "terms": "User confirmed a Brave Search plan permitting storage of the selected response.",
        "capped": len(items) > request.count, "skipped": skipped,
        "limitations": ["Ranks are positions in the Brave web sample. Device class is unavailable."],
    }, raw, warnings)
