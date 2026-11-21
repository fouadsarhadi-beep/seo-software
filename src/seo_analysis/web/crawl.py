"""Crawl pipeline: sitemap -> robots check -> fetch -> extract -> indexability -> canonical analysis -> files.
Read-only: it only requests public pages. It never changes anything on the site."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from hashlib import sha256
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from seo_analysis.analysis import canon, indexability
from seo_analysis.web.discovery import Discovery
from seo_analysis.web.sitemap import SitemapEntry
from seo_analysis.web.transport import BudgetExceeded, ScopeError
from seo_analysis.core.artifacts import atomic_text, write_json
from seo_analysis.web.classify import classify
from seo_analysis.web.extract import extract_page
from seo_analysis.analysis.fa_text import load_variants
from seo_analysis.web.fetch import Fetcher
from seo_analysis.reporting.report import write_csv, write_manifest
from seo_analysis.web.robots import RobotsPolicy
from seo_analysis import __version__
from seo_analysis.core.network import HttpOrigin
from seo_analysis.core.urls import decoded, url_key

TOOL_TOKEN = "SEOAnalysis"

INVENTORY_HEADER = [
    # first nine = the original layout, so the tracker workbook still works
    "URL", "Title", "H1", "Meta description", "Words", "Declared canonical", "HTTP status", "Robots meta", "Redirected to",
    # new in V2
    "First HTTP status", "Redirect count", "Redirect chain", "Fetch state", "Robots.txt allowed (this tool)",
    "Robots.txt allowed (Googlebot)", "X-Robots-Tag", "Effective indexability", "Indexability reason", "H1 count",
    "Canonical candidates", "Canonical relationship", "Canonical target status", "Canonical issues", "Pages pointing here",
    "Extraction selector", "Extraction state", "Characters", "Page type", "Classification reason",
    "Sitemap source", "Sitemap lastmod", "URL (decoded)", "Language attribute",
]


@dataclass
class CrawlConfig:
    sitemap: str
    out_dir: str
    delay: float = 0.5
    timeout: tuple = (10, 30)
    retries: int = 2
    allow_local: bool = False
    max_requests: int = 500
    max_seconds: float = 300
    limit: int = 100
    kind: str = "sitemap"
    source: str = ""
    seeds: tuple = ()
    sitemap_paths: tuple = ("/sitemap.xml", "/sitemap_index.xml")
    max_depth: int = 2
    max_variants: int = 5
    link_crawl: bool = False
    max_redirects: int = 5
    max_bytes: int = 5_000_000
    robots: str = "respect"                 # respect | ignore
    content_selector: str = ""
    exclude_selectors: list = field(default_factory=list)
    skip_sitemap: str = ""
    config_file: str = ""
    variants_file: str = ""
    page_types: list = field(default_factory=list)
    user_agent: str = f"{TOOL_TOKEN}/{__version__}"
    csv_guard: bool = True


def load_robots(fetcher, sitemap_url, cfg, input_fn=None):
    p = urlsplit(sitemap_url)
    res = fetcher.get(f"{p.scheme}://{p.netloc}/robots.txt")
    if res.final_status == 200 and not res.truncated:
        return RobotsPolicy.parse(res.text), "robots.txt read"
    if 400 <= res.final_status < 500:
        return RobotsPolicy.allow_all(), f"robots.txt returned HTTP {res.final_status}: treated as 'allow all' (RFC 9309)"
    msg = f"robots.txt could not be read (status {res.final_status or res.error})."
    if cfg.robots == "ignore":
        return RobotsPolicy.allow_all(available=False), msg + " Continuing because --robots ignore was chosen."
    if input_fn and input_fn(msg + " Continue anyway and treat everything as allowed? [y/N] ").strip().lower() == "y":
        return RobotsPolicy.allow_all(available=False), msg + " You chose to continue."
    raise RuntimeError(msg + " Nothing was crawled. Re-run with --robots ignore to continue.")


def fetch_state(res, is_html: bool) -> str:
    n = res.redirect_note
    if res.error:
        return "fetch_error"
    if n.startswith("blocked_external"):
        return "redirect_blocked_external"
    if n.startswith("blocked_robots"):
        return "redirect_blocked_robots"
    if n == "loop":
        return "redirect_loop"
    if n == "too_many":
        return "redirect_too_many"
    if res.final_status >= 500:
        return "server_error"
    if res.final_status >= 400:
        return "client_error"
    if res.final_status != 200:
        return f"http_{res.final_status}"
    if not is_html:
        return "non_html"
    if res.truncated:
        return "ok_truncated"
    return "ok_after_redirect" if res.redirect_count else "ok"


def _blank(entry, state, allowed_tool, allowed_g, ptype, reason):
    return {"url": entry.url, "final_url": "", "first_status": 0, "final_status": 0, "chain": [], "redirect_note": "",
            "fetch_state": state, "robots_allowed_tool": allowed_tool, "robots_allowed_googlebot": allowed_g,
            "title": "", "h1": "", "h1_count": 0, "meta": "", "lang": "", "robots_meta_raw": "", "x_robots_raw": "",
            "googlebot_directives": "", "effective_indexability": "unknown",
            "indexability_reason": "robots.txt blocks the crawl, so page directives cannot be read" if state == "robots_disallowed" else "page was not fetched",
            "canonicals_html": [], "canonicals_header": [], "words": 0, "chars": 0, "text": "",
            "extraction_selector": "", "extraction_state": "not_fetched", "page_type": ptype, "classification_reason": reason,
            "sitemap_source": entry.source, "sitemap_lastmod": entry.lastmod, "content_type": "", "error": ""}


def inventory_row(r: dict, c: dict) -> list:
    status = r["final_status"] or ""
    if r["fetch_state"] == "robots_disallowed":
        status = "ROBOTS_DISALLOWED"
    elif r["fetch_state"] == "fetch_error":
        status = "ERROR"
    redirected = r["final_url"] if (r["final_url"] and url_key(r["final_url"]) != url_key(r["url"])) else ""
    chain = " > ".join(f"{u} [{s}]" for u, s in r["chain"]) if len(r["chain"]) > 1 else ""
    first = c["candidates"].split(" | ")[0] if c["candidates"] else ""
    return [r["url"], r["title"], r["h1"], r["meta"], r["words"], first, status, r["robots_meta_raw"], redirected,
            r["first_status"] or "", max(0, len(r["chain"]) - 1), chain, r["fetch_state"],
            "yes" if r["robots_allowed_tool"] else "NO", "yes" if r["robots_allowed_googlebot"] else "NO",
            r["x_robots_raw"], r["effective_indexability"], r["indexability_reason"], r["h1_count"],
            c["candidates"], c["relationship"], c["target_status"], c["issues"], c["pointing_here"],
            r["extraction_selector"], r["extraction_state"], r["chars"], r["page_type"], r["classification_reason"],
            r["sitemap_source"], r["sitemap_lastmod"], decoded(r["url"]), r["lang"]]


def run_crawl(cfg: CrawlConfig, input_fn=None, log=print, fetcher=None) -> dict:
    out = Path(cfg.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    extra = json.loads(Path(cfg.config_file).read_text(encoding="utf-8")) if cfg.config_file else {}
    page_types = cfg.page_types or extra.get("page_types", [])
    excludes = list(cfg.exclude_selectors) + list(extra.get("exclude_selectors", []))
    origin = HttpOrigin.from_url(cfg.sitemap)
    if extra.get("allowed_hosts"):
        raise ValueError("Crawls are scoped to the origin of the supplied sitemap.")
    variants = load_variants(cfg.variants_file) if cfg.variants_file else {}

    fetcher = fetcher or Fetcher(cfg.user_agent, cfg.delay, cfg.timeout, cfg.retries, cfg.max_redirects, cfg.max_bytes, origin=origin, allow_local=cfg.allow_local, max_requests=cfg.max_requests, max_seconds=cfg.max_seconds)
    if not 1 <= cfg.limit <= 10000 or cfg.max_depth < 0 or cfg.max_variants < 1:
        raise ValueError("Choose 1–10000 pages, a nonnegative depth and a positive variant limit.")
    discovery = Discovery(cfg, fetcher)
    records = []
    journal = out / "observations"
    journal.mkdir(exist_ok=False)
    status = "succeeded"
    started = datetime.now(timezone.utc).isoformat()
    notes = []
    try:
        policy, robots_note = load_robots(fetcher, cfg.sitemap, cfg, input_fn)
        notes.append(robots_note)
        if cfg.robots == "respect":
            fetcher.robots, fetcher.robots_agent = policy, TOOL_TOKEN
        discovery.discover(policy, input_fn)
        while discovery.queue:
            fetcher.budget.remaining()
            entry, depth = discovery.queue.popleft()
            log(f"[{len(records) + 1}] {entry.url}")
            rec, links = observe(cfg, fetcher, policy, entry, page_types, excludes, variants, discovery.follow_links)
            evidence_id = f"page-{len(records) + 1:06d}"
            rec.update(evidence_id=evidence_id, observed_at=datetime.now(timezone.utc).isoformat(),
                       depth=depth, discovery_source=entry.source, url_key=url_key(entry.url),
                       content_hash=sha256(rec["text"].encode()).hexdigest() if rec["text"] else None)
            write_json(journal / (evidence_id + ".json"), rec)
            records.append(rec)
            for link in links:
                if fetcher.in_scope(link):
                    discovery.add(SitemapEntry(link, "", rec["final_url"]), depth + 1)
        if not records:
            status = "no_pages_found"
        elif (discovery.incomplete_maps or discovery.skipped or
              any(r["fetch_state"] in ("ok_truncated", "fetch_error") for r in records)):
            status = "partial"
    except BudgetExceeded as exc:
        status = "partial"
        notes.append(str(exc))
    except ScopeError as exc:
        status = "partial" if records else "failed"
        notes.append(str(exc))
    except KeyboardInterrupt:
        status = "cancelled"
        notes.append("Cancelled by user.")
    finally:
        fetcher.session.close()
    warnings = notes + discovery.warnings
    if discovery.skipped:
        warnings.append("Discovery limits: " + str(dict(discovery.skipped)))
    with atomic_text(out / "snapshot.jsonl") as stream:
        for row in records:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    info = canon.analyze(records)
    write_csv(out / "inventory.csv", INVENTORY_HEADER, [inventory_row(r, info[r["url"]]) for r in records], cfg.csv_guard)
    counts = {"sitemap_files": len(discovery.files), "urls": len(records),
              "ok": sum(1 for r in records if r["fetch_state"].startswith("ok")),
              "robots_disallowed": sum(1 for r in records if r["fetch_state"] == "robots_disallowed"),
              "redirecting": sum(1 for r in records if len(r["chain"]) > 1),
              "errors": sum(1 for r in records if r["fetch_state"] in ("fetch_error", "client_error", "server_error"))}
    counts.update(discovered=len(discovery.seen), requests=fetcher.budget.requests,
                  skipped=dict(discovery.skipped), observed=len(records))
    write_manifest(out / "crawl_manifest.json", "crawl",
                   {"target": cfg.source or cfg.sitemap, "kind": cfg.kind, "status": status, "started_at": started,
                    "max_pages": cfg.limit, "max_depth": cfg.max_depth, "max_requests": cfg.max_requests,
                    "max_seconds": cfg.max_seconds, "retries": cfg.retries, "link_crawl": cfg.link_crawl,
                    "user_agent": cfg.user_agent, "sitemap_paths": cfg.sitemap_paths, "max_variants": cfg.max_variants, "allow_local": cfg.allow_local,
                    "sitemap_files": discovery.files, "delay": cfg.delay, "robots": cfg.robots, "origin": {"scheme": origin.scheme, "host": origin.host, "port": origin.port},
                    "content_selector": cfg.content_selector, "exclude_selectors": excludes,
                    "max_redirects": cfg.max_redirects, "max_bytes": cfg.max_bytes, "variants_file": cfg.variants_file},
                   counts, ["snapshot.jsonl", "inventory.csv"], warnings,
                   ["HTML-source crawl: JavaScript-generated content is not seen.",
                    "robots.txt rules follow RFC 9309; Crawl-delay is not applied.",
                    "Fields are facts from this single crawl; none of them is a verdict."])
    log(f"Wrote {out/'inventory.csv'} and {out/'snapshot.jsonl'}.")
    return {"status": status, "counts": counts, "out_dir": str(out), "warnings": warnings}


def observe(cfg, fetcher, policy, e, page_types, excludes, variants, follow_links):
    ptype, reason = classify(e.url, page_types)
    allow_tool, allow_g = policy.allowed(e.url, TOOL_TOKEN), policy.allowed(e.url, "googlebot")
    links = []
    if cfg.robots == "respect" and not allow_tool:
        return _blank(e, "robots_disallowed", allow_tool, allow_g, ptype, reason), links
    res = fetcher.get(e.url)
    is_html = "html" in res.content_type.lower() or res.raw[:2000].lower().lstrip().startswith((b"<!doctype html", b"<html"))
    state = fetch_state(res, is_html)
    rec = _blank(e, state, allow_tool, allow_g, ptype, reason)
    rec.update({"final_url": res.final_url, "first_status": res.first_status, "final_status": res.final_status,
                "chain": res.chain, "redirect_note": res.redirect_note, "content_type": res.content_type,
                "error": res.error, "x_robots_raw": " | ".join(res.x_robots)})
    if state.startswith("ok"):
        pd = extract_page(res.text, res.final_url, cfg.content_selector, excludes, variants, collect_links=follow_links)
        links = pd.links
        rec.update({"title": pd.title, "h1": pd.h1_list[0] if pd.h1_list else "", "h1_count": len(pd.h1_list),
                    "meta": pd.meta_description, "lang": pd.lang, "canonicals_html": pd.canonicals,
                    "canonicals_header": canon.header_canonicals(res.link_headers, res.final_url),
                    "words": pd.words, "chars": pd.chars, "text": pd.text,
                    "extraction_selector": pd.selector, "extraction_state": "truncated" if res.truncated else pd.state})
        ix = indexability.evaluate(pd.robots_meta, res.x_robots, True, res.final_status, False)
        rec.update({"robots_meta_raw": ix.meta_raw, "googlebot_directives": ix.googlebot,
                    "effective_indexability": ix.effective, "indexability_reason": ix.reason})
    else:
        ix = indexability.evaluate([], res.x_robots, state in ("client_error", "server_error") or res.final_status > 0,
                                   res.final_status, False)
        rec.update({"effective_indexability": ix.effective, "indexability_reason": ix.reason,
                    "extraction_state": "non_html" if state == "non_html" else "fetch_error" if state == "fetch_error" else "not_parsed"})
    return rec, links
