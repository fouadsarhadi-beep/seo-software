"""Bounded provider requests that produce the same datasets as offline imports."""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from time import monotonic
from types import SimpleNamespace
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
from xml.etree.ElementTree import ParseError

from bs4 import BeautifulSoup
from defusedxml import ElementTree
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

# Parameters that must not appear in a saved or displayed URL.
SENSITIVE_PARAMETERS = frozenset({
    "access_token", "apikey", "api_key", "auth", "client_secret", "code", "key",
    "password", "secret", "session", "sig", "signature", "token",
})
FEED_ROOTS = ("rss", "feed", "rdf")
FEED_MESSAGES = {
    "empty": "The source returned an empty response. Check the feed address or try again later.",
    "html": "The address returned an HTML page instead of a feed.",
    "malformed": "The response is not valid XML, so it cannot be read as a feed.",
    "prohibited": "The feed XML contains prohibited entities or external references.",
    "too_large": "The feed response exceeds 2 MB.",
    "robots": "robots.txt disallows the selected feed.",
    "robots_unavailable": "Could not read the feed's robots.txt policy. See requests.json.",
    "unsupported": "The response is valid XML but not an RSS or Atom feed (found <{detail}>).",
}


def redact_url(value: str) -> tuple[str, int]:
    """Return the URL without credentials or sensitive parameters, and how many were hidden."""
    try:
        parts = urlsplit(value)
    except ValueError:
        return "(unreadable address)", 0
    netloc = parts.hostname or ""
    if parts.port:
        netloc = f"{netloc}:{parts.port}"
    pairs = parse_qsl(parts.query, keep_blank_values=True)
    kept = [(name, item) for name, item in pairs if name.casefold() not in SENSITIVE_PARAMETERS]
    return urlunsplit((parts.scheme, netloc, parts.path, urlencode(kept), "")), len(pairs) - len(kept)


def _feed_error(ctx, reason: str, detail: str = "", source: str = "", candidate: str = ""):
    """Record why a feed request failed, then return the exception to raise."""
    if reason == "http":
        message = f"The feed request returned HTTP {detail or 'unavailable'}."
    elif reason == "request":
        message = "The feed request failed before a response arrived."
        if detail:
            message = f"{message} {detail}"
    elif reason == "redirect":
        note = {"loop": "redirect loop", "too_many": "too many redirects"}.get(detail, "blocked redirect")
        message = f"The feed address redirects and the app will not follow it ({note})."
    else:
        message = FEED_MESSAGES[reason].format(detail=detail)
        if reason == "malformed" and detail:
            message = f"{message} {detail}"
    shown, hidden = redact_url(source) if source else ("", 0)
    write_json(ctx.directory / "feed-source.json", {
        "schema_version": 1, "reason": reason, "message": message, "detail": detail,
        "source": shown, "hidden_parameters": hidden, "candidate": candidate,
    })
    return ValueError(message) if reason in ("empty", "html", "malformed", "prohibited", "robots",
                                             "too_large", "unsupported") else RuntimeError(message)


def _advertised_feed(response) -> str:
    """Return a validated feed link that an HTML page advertises, if any."""
    try:
        soup = BeautifulSoup(response.raw, "html.parser")
    except (ValueError, TypeError):
        return ""
    for tag in soup.find_all("link", href=True):
        rel = tag.get("rel") or []
        rel = [str(item).casefold() for item in rel] if isinstance(rel, list) else str(rel).casefold().split()
        if "alternate" not in rel:
            continue
        kind = str(tag.get("type", "")).casefold()
        if "rss" not in kind and "atom" not in kind:
            continue
        candidate = urljoin(response.final_url or "", str(tag["href"]).strip())
        try:
            HttpOrigin.from_url(candidate)
        except ValueError:
            continue
        return candidate
    return ""


def _classify_feed(response) -> tuple[str, str]:
    """Decide what a fetched response is before it is parsed as a feed."""
    raw = response.raw or b""
    head = raw.lstrip()[:4096]
    if not head.strip():
        return "empty", ""
    if not head.startswith(b"<?xml") and re.search(rb"<(!doctype\s+html|html)\b", head, re.IGNORECASE):
        return "html", ""
    try:
        root = ElementTree.fromstring(raw)
    except DefusedXmlException:
        return "prohibited", ""
    except ParseError as exc:
        detail = str(exc).strip()
        return "malformed", detail.splitlines()[0][:120] if detail else ""
    tag = root.tag.rsplit("}", 1)[-1].casefold()
    if tag not in FEED_ROOTS:
        return "unsupported", tag
    return "feed", tag


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
        raise _feed_error(ctx, "robots_unavailable", source=request.url) from None
    except (BudgetExceeded, ScopeError) as exc:
        raise _feed_error(ctx, "request", str(exc), request.url) from None
    finally:
        fetcher.session.close()
        write_json(ctx.directory / "requests.json", {"schema_version": 1, "attempts": fetcher.attempts})
        if fetcher.attempts:
            ctx.data_egress.append({"method": "GET", "origin": asdict(origin), "purpose": "Read public feed and robots.txt",
                                    "attempt_log": "requests.json"})
    if response.redirect_note.startswith("blocked_robots"):
        raise _feed_error(ctx, "robots", source=request.url)
    if response.error:
        raise _feed_error(ctx, "request", response.error, request.url)
    if response.redirect_note:
        raise _feed_error(ctx, "redirect", response.redirect_note, request.url)
    if response.final_status != 200:
        raise _feed_error(ctx, "http", str(response.final_status or "unavailable"), request.url)
    if response.truncated:
        raise _feed_error(ctx, "too_large", source=request.url)
    kind, detail = _classify_feed(response)
    if kind != "feed":
        raise _feed_error(ctx, kind, detail, request.url,
                          _advertised_feed(response) if kind == "html" else "")
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
