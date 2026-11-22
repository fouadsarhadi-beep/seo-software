"""Read selected WordPress REST metadata from an explicitly selected HTTPS installation."""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
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
CORE_ROUTES = ("posts", "pages", "media")
REST_SEGMENT = re.compile(r"[a-zA-Z0-9_-]{1,80}")
NON_POST_ROUTES = {"users", "settings", "comments", "search", "types", "statuses", "taxonomies", "categories", "tags",
                   "plugins", "themes", "global-styles", "templates", "template-parts", "menus", "menu-items",
                   "menu-locations", "blocks", "navigation"}
MAX_ITEMS = 250
PAGE_SIZE = 50
FIELDS = ("id", "slug", "link", "status", "date_gmt", "modified_gmt", "title", "author", "parent",
          "categories", "tags", "yoast_head_json")
MEDIA_FIELDS = ("id", "slug", "link", "status", "date_gmt", "modified_gmt", "title", "author", "post",
                "source_url", "alt_text", "mime_type", "media_details")


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


def _normalize(item, status, *, media=False):
    if not isinstance(item, dict) or type(item.get("id")) is not int or item.get("status") != status:
        return None
    row = {key: item.get(key) for key in ("id", "slug", "status", "date_gmt", "modified_gmt", "author",
                                         "parent", "categories", "tags")}
    row["url"] = _http_url(item.get("link"))
    title = item.get("title")
    rendered = title.get("rendered") if isinstance(title, dict) else None
    row["title"] = BeautifulSoup(rendered, "html.parser").get_text(" ", strip=True) if isinstance(rendered, str) else None
    if media:
        dimensions = item.get("media_details")
        dimensions = dimensions if isinstance(dimensions, dict) else {}
        row.update(source_url=_http_url(item.get("source_url")), alt_text=item.get("alt_text"),
                   mime_type=item.get("mime_type"), attached_post=item.get("post"),
                   width=dimensions.get("width"), height=dimensions.get("height"))
        return row
    seo = item.get("yoast_head_json")
    row["plugin_canonical"] = _http_url(seo.get("canonical")) if isinstance(seo, dict) else None
    robots = seo.get("robots") if isinstance(seo, dict) else None
    row["plugin_index_directive"] = robots.get("index") if isinstance(robots, dict) else None
    return row


def _collection(fetcher, endpoint, params):
    query = urlencode(params)
    response = fetcher.get(f"{endpoint}?{query}", follow_redirects=False, header_names=("X-WP-Total",))
    if response.redirect_note:
        raise RuntimeError("WordPress declined the exact REST URL. Check the installation path or robots.txt.")
    if response.final_status != 200 or response.error or response.truncated:
        raise RuntimeError(f"WordPress response was unavailable or incomplete (HTTP {response.final_status or 'unknown'}).")
    try:
        return response, json.loads(response.raw)
    except (ValueError, UnicodeError):
        raise RuntimeError("Expected a JSON response from the WordPress REST API.") from None


def _post_types(fetcher, endpoint):
    _, data = _collection(fetcher, endpoint, {"context": "view", "_fields": "slug,name,rest_base,rest_namespace"})
    if not isinstance(data, dict):
        raise RuntimeError("Expected a WordPress post type catalogue.")
    entries = []
    for slug, item in sorted(data.items()):
        if not isinstance(item, dict):
            continue
        base = item.get("rest_base")
        if (not REST_SEGMENT.fullmatch(slug) or item.get("rest_namespace") != "wp/v2"
                or not isinstance(base, str) or not REST_SEGMENT.fullmatch(base)
                or base.casefold() in NON_POST_ROUTES):
            continue
        entries.append({"slug": slug, "name": item.get("name"), "rest_base": base})
    return entries


def inventory(ctx, request):
    site = site_root(request.site)
    if not REST_SEGMENT.fullmatch(request.resource) or not 1 <= request.max_items <= MAX_ITEMS:
        raise ValueError(f"Select a resource name and a limit of 1–{MAX_ITEMS} items.")
    origin = HttpOrigin.from_url(site)
    auth = credentials(ctx.workspace, ctx.project, site) if request.authenticated else None
    api = f"{site}/wp-json/wp/v2"
    endpoints = []
    media = request.resource == "media"
    status = "inherit" if media else "publish"
    fields = MEDIA_FIELDS if media else FIELDS
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

        resource = request.resource
        if resource not in CORE_ROUTES:
            endpoints.append(f"{api}/types")
            catalogue = _post_types(fetcher, endpoints[-1])
            if resource == "types":
                rows = catalogue[:request.max_items]
                reported = len(catalogue)
                capped = len(rows) < reported
            else:
                selected = next((entry for entry in catalogue if entry["slug"] == resource), None)
                if selected is None or selected["rest_base"] in CORE_ROUTES:
                    raise ValueError("Choose a registered custom post type from wordpress inventory --resource types.")
                resource = selected["rest_base"]
        if request.resource != "types":
            endpoints.append(f"{api}/{resource}")
            endpoint = endpoints[-1]
            for page in range(1, (request.max_items + per_page - 1) // per_page + 1):
                limit = min(per_page, request.max_items - scanned)
                try:
                    response, batch = _collection(fetcher, endpoint, {
                        "context": "view", "status": status, "offset": scanned, "per_page": limit,
                        "orderby": "id", "order": "asc", "_fields": ",".join(fields),
                    })
                    if not isinstance(batch, list) or len(batch) > limit:
                        raise RuntimeError("Expected a bounded WordPress REST collection response.")
                except (RuntimeError, ValueError):
                    if not scanned:
                        raise
                    interrupted = True
                    warnings.append(f"Stopped at REST page {page}. See requests.json.")
                    break
                scanned += len(batch)
                for item in batch:
                    row = _normalize(item, status, media=media)
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
            ctx.data_egress.append({"method": "GET", "origin": asdict(origin), "endpoints": endpoints,
                                    "authenticated": request.authenticated, "attempt_log": "requests.json"})

    if capped:
        warnings.append("Reached the selected item limit. More items may exist.")
    if skipped:
        warnings.append(f"Skipped {skipped} items with an unexpected status or invalid or duplicate identifiers.")
    write_json(ctx.directory / "wordpress.json", {
        "schema_version": 1, "site": site, "resource": request.resource, "authenticated": request.authenticated,
        "observed_at": datetime.now(timezone.utc).isoformat(), "reported_items": reported, "items": rows,
    })
    columns = ("id", "url", "slug", "title", "status", "modified_gmt", "plugin_canonical", "plugin_index_directive")
    if request.resource == "types":
        columns = ("slug", "name", "rest_base")
    elif media:
        columns = ("id", "source_url", "title", "alt_text", "mime_type", "attached_post", "width", "height")
    write_csv(ctx.directory / "wordpress.csv", columns, ([row[key] for key in columns] for row in rows))
    return {"status": "partial" if capped or skipped or interrupted else "succeeded",
            "counts": {"items": len(rows), "skipped": skipped}, "warnings": warnings}
