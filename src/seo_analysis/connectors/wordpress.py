"""Read published core WordPress REST metadata from an explicitly selected HTTPS installation."""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from types import SimpleNamespace
from urllib.parse import unquote, urlencode, urlsplit

from bs4 import BeautifulSoup

from seo_analysis.connectors.google import native_keyring
from seo_analysis.core.artifacts import write_json
from seo_analysis.core.network import HttpOrigin
from seo_analysis.core.urls import url_key
from seo_analysis.reporting.report import write_csv
from seo_analysis.storage.history import History
from seo_analysis.web.crawl import TOOL_TOKEN, RobotsUnavailable, load_robots
from seo_analysis.web.fetch import Fetcher

SERVICE = "SEO Analysis Software WordPress"
TYPES = ("posts", "pages")
MAX_ITEMS = 250
PAGE_SIZE = 50
FIELDS = ("id", "slug", "link", "status", "date_gmt", "modified_gmt", "title", "author", "parent",
          "categories", "tags", "yoast_head_json")


@dataclass
class InventoryInput:
    site: str
    resource: str = "posts"
    max_items: int = 100
    authenticated: bool = False


def site_root(url):
    origin = HttpOrigin.from_url(url)
    parts = urlsplit(url)
    segments = [unquote(segment) for segment in parts.path.split("/")]
    if (origin.scheme != "https" or "?" in url or "#" in url
            or any(segment in (".", "..") or "/" in segment or "\\" in segment for segment in segments)):
        raise ValueError("Supply the WordPress installation's HTTPS base URL without a query or fragment.")
    return url_key(url).rstrip("/")


def credentials(workspace, project, site, *, account=None, password=None, delete=False):
    History(workspace).selection(project, None)
    identity = json.dumps([str(workspace.data_dir.resolve()), project, site_root(site)])
    key = sha256(identity.encode("utf-8")).hexdigest()
    vault = native_keyring("wordpress")
    try:
        if account is not None:
            if not account or ":" in account or not password:
                raise ValueError("Enter a WordPress username and Application Password.")
            vault.set_password(SERVICE, key, json.dumps([account, password]))
            return None
        saved = vault.get_password(SERVICE, key)
        if delete:
            if saved:
                vault.delete_password(SERVICE, key)
            return None
        if saved:
            username, secret = json.loads(saved)
            if isinstance(username, str) and isinstance(secret, str) and username and secret and ":" not in username:
                return username, secret
    except ValueError:
        raise ValueError("The WordPress credential is invalid.") from None
    except Exception:
        raise RuntimeError("Unable to access the OS credential store.") from None
    raise ValueError("Save a WordPress Application Password for this installation first.")


def _http_url(value):
    if isinstance(value, str) and value:
        try:
            HttpOrigin.from_url(value)
            return value
        except ValueError:
            pass
    return None


def _normalize(item):
    if not isinstance(item, dict) or type(item.get("id")) is not int or item.get("status") != "publish":
        return None
    row = {key: item.get(key) for key in ("id", "slug", "status", "date_gmt", "modified_gmt", "author",
                                         "parent", "categories", "tags")}
    row["url"] = _http_url(item.get("link"))
    title = item.get("title")
    rendered = title.get("rendered") if isinstance(title, dict) else None
    row["title"] = BeautifulSoup(rendered, "html.parser").get_text(" ", strip=True) if isinstance(rendered, str) else None
    seo = item.get("yoast_head_json")
    row["plugin_canonical"] = _http_url(seo.get("canonical")) if isinstance(seo, dict) else None
    robots = seo.get("robots") if isinstance(seo, dict) else None
    row["plugin_index_directive"] = robots.get("index") if isinstance(robots, dict) else None
    return row


def inventory(ctx, request):
    site = site_root(request.site)
    if request.resource not in TYPES or not 1 <= request.max_items <= MAX_ITEMS:
        raise ValueError(f"Select posts or pages and a limit of 1–{MAX_ITEMS} items.")
    origin = HttpOrigin.from_url(site)
    auth = credentials(ctx.workspace, ctx.project, site) if request.authenticated else None
    endpoint = f"{site}/wp-json/wp/v2/{request.resource}"
    per_page = min(PAGE_SIZE, request.max_items)
    fetcher = Fetcher(TOOL_TOKEN, origin=origin, max_bytes=2_000_000,
                      max_requests=(request.max_items + per_page - 1) // per_page + 4,
                      max_seconds=40, retries=0, cancel=ctx.cancel)
    rows, warnings = [], []
    seen, scanned, skipped, reported = set(), 0, 0, None
    capped = interrupted = False
    try:
        if auth is None:
            try:
                fetcher.robots, _ = load_robots(fetcher, site, SimpleNamespace(robots="respect"))
            except RobotsUnavailable:
                raise RuntimeError("Could not read this installation's robots.txt policy. See requests.json.") from None
            fetcher.robots_agent = TOOL_TOKEN
        else:
            fetcher.session.auth = auth

        for page in range(1, (request.max_items + per_page - 1) // per_page + 1):
            limit = min(per_page, request.max_items - scanned)
            query = urlencode({"context": "view", "status": "publish", "offset": scanned, "per_page": limit,
                               "orderby": "id", "order": "asc", "_fields": ",".join(FIELDS)})
            try:
                response = fetcher.get(f"{endpoint}?{query}", follow_redirects=False, header_names=("X-WP-Total",))
                if response.redirect_note:
                    raise RuntimeError("WordPress declined the exact REST URL. Check the installation path or robots.txt.")
                if response.final_status != 200 or response.error or response.truncated:
                    raise RuntimeError(f"WordPress response was unavailable or incomplete (HTTP {response.final_status or 'unknown'}).")
                batch = json.loads(response.raw)
                if not isinstance(batch, list) or len(batch) > limit:
                    raise ValueError
            except (RuntimeError, ValueError) as exc:
                if not scanned:
                    if type(exc) is ValueError:
                        raise RuntimeError("Expected a WordPress REST collection response.") from None
                    raise
                interrupted = True
                warnings.append(f"Stopped at REST page {page}. See requests.json.")
                break
            scanned += len(batch)
            for item in batch:
                row = _normalize(item)
                if not row or row["id"] in seen:
                    skipped += 1
                    continue
                seen.add(row["id"])
                rows.append(row)
            header = response.selected_headers.get("X-WP-Total", "")
            total = int(header) if header.isascii() and header.isdecimal() and len(header) <= 10 else None
            if reported is not None and total is not None and reported != total:
                interrupted = True
                warnings.append("The reported WordPress total changed during pagination.")
            reported = total
            if reported is not None and scanned >= reported:
                break
            if not batch or (len(batch) < limit and reported is None):
                if reported is not None and scanned < reported:
                    interrupted = True
                    warnings.append("WordPress returned an empty batch before its reported total.")
                break
            if scanned >= request.max_items:
                capped = True
                break
        else:
            capped = True
    finally:
        fetcher.session.close()
        write_json(ctx.directory / "requests.json", {"schema_version": 1, "attempts": fetcher.attempts})
        if fetcher.attempts:
            ctx.data_egress.append({"method": "GET", "origin": asdict(origin), "endpoints": [endpoint],
                                    "authenticated": request.authenticated, "attempt_log": "requests.json"})

    if capped:
        warnings.append("Reached the selected item limit. More published items may exist.")
    if skipped:
        warnings.append(f"Skipped {skipped} unpublished, malformed or duplicate items.")
    write_json(ctx.directory / "wordpress.json", {
        "schema_version": 1, "site": site, "resource": request.resource, "authenticated": request.authenticated,
        "observed_at": datetime.now(timezone.utc).isoformat(), "reported_items": reported, "items": rows,
    })
    columns = ("id", "url", "slug", "title", "status", "modified_gmt", "plugin_canonical", "plugin_index_directive")
    write_csv(ctx.directory / "wordpress.csv", columns, ([row[key] for key in columns] for row in rows))
    return {"status": "partial" if capped or skipped or interrupted else "succeeded",
            "counts": {"items": len(rows), "skipped": skipped}, "warnings": warnings}
