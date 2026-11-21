"""Crawl pipeline: sitemap -> robots check -> fetch -> extract -> indexability -> canonical analysis -> files.
Read-only: it only requests public pages. It never changes anything on the site."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from seo_analysis.analysis import canon, indexability
from seo_analysis.web import sitemap
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
    limit: int = 0
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
    if res.final_status == 200:
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

    fetcher = fetcher or Fetcher(cfg.user_agent, cfg.delay, cfg.timeout, cfg.retries, cfg.max_redirects, cfg.max_bytes, origin=origin)
    policy, robots_note = load_robots(fetcher, cfg.sitemap, cfg, input_fn)
    log(robots_note)
    if cfg.robots == "respect":
        fetcher.robots, fetcher.robots_agent = policy, TOOL_TOKEN
    entries, warnings, files = sitemap.collect(fetcher, cfg.sitemap, cfg.skip_sitemap)
    for w in warnings:
        log("  ! " + w)
    if cfg.limit:
        entries = entries[: cfg.limit]
    if not entries:
        raise RuntimeError("No page URLs were found in the sitemap.")
    log(f"{len(entries)} URLs from {len(files)} sitemap file(s). Crawling politely, one request at a time.")

    records = []
    for i, e in enumerate(entries, 1):
        ptype, reason = classify(e.url, page_types)
        allow_tool, allow_g = policy.allowed(e.url, TOOL_TOKEN), policy.allowed(e.url, "googlebot")
        log(f"[{i}/{len(entries)}] {e.url}")
        if cfg.robots == "respect" and not allow_tool:
            records.append(_blank(e, "robots_disallowed", allow_tool, allow_g, ptype, reason))
            continue
        res = fetcher.get(e.url)
        is_html = "html" in res.content_type.lower() or res.raw[:2000].lower().lstrip().startswith((b"<!doctype html", b"<html"))
        state = fetch_state(res, is_html)
        rec = _blank(e, state, allow_tool, allow_g, ptype, reason)
        rec.update({"final_url": res.final_url, "first_status": res.first_status, "final_status": res.final_status,
                    "chain": res.chain, "redirect_note": res.redirect_note, "content_type": res.content_type,
                    "error": res.error, "x_robots_raw": " | ".join(res.x_robots)})
        if state.startswith("ok"):
            pd = extract_page(res.text, res.final_url, cfg.content_selector, excludes, variants)
            rec.update({"title": pd.title, "h1": pd.h1_list[0] if pd.h1_list else "", "h1_count": len(pd.h1_list),
                        "meta": pd.meta_description, "lang": pd.lang, "canonicals_html": pd.canonicals,
                        "canonicals_header": canon.header_canonicals(res.link_headers, res.final_url),
                        "words": pd.words, "chars": pd.chars, "text": pd.text,
                        "extraction_selector": pd.selector, "extraction_state": pd.state})
            ix = indexability.evaluate(pd.robots_meta, res.x_robots, True, res.final_status, False)
            rec.update({"robots_meta_raw": ix.meta_raw, "googlebot_directives": ix.googlebot,
                        "effective_indexability": ix.effective, "indexability_reason": ix.reason})
        else:
            ix = indexability.evaluate([], res.x_robots, state in ("client_error", "server_error") or res.final_status > 0,
                                       res.final_status, False)
            rec.update({"effective_indexability": ix.effective, "indexability_reason": ix.reason,
                        "extraction_state": "non_html" if state == "non_html" else "fetch_error" if state == "fetch_error" else "not_parsed"})
        records.append(rec)

    info = canon.analyze([{"url": r["url"], "final_url": r["final_url"], "final_status": r["final_status"],
                           "canonicals_html": r["canonicals_html"], "canonicals_header": r["canonicals_header"],
                           "effective_indexability": r["effective_indexability"]} for r in records])
    with open(out / "snapshot.jsonl", "w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    write_csv(out / "inventory.csv", INVENTORY_HEADER, [inventory_row(r, info[r["url"]]) for r in records], cfg.csv_guard)
    counts = {"sitemap_files": len(files), "urls": len(records),
              "ok": sum(1 for r in records if r["fetch_state"].startswith("ok")),
              "robots_disallowed": sum(1 for r in records if r["fetch_state"] == "robots_disallowed"),
              "redirecting": sum(1 for r in records if len(r["chain"]) > 1),
              "errors": sum(1 for r in records if r["fetch_state"] in ("fetch_error", "client_error", "server_error"))}
    write_manifest(out / "crawl_manifest.json", "crawl",
                   {"sitemap": cfg.sitemap, "delay": cfg.delay, "robots": cfg.robots, "origin": {"scheme": origin.scheme, "host": origin.host, "port": origin.port},
                    "content_selector": cfg.content_selector, "exclude_selectors": excludes,
                    "max_redirects": cfg.max_redirects, "max_bytes": cfg.max_bytes, "variants_file": cfg.variants_file},
                   counts, ["snapshot.jsonl", "inventory.csv"], warnings + [robots_note],
                   ["HTML-source crawl: JavaScript-generated content is not seen.",
                    "robots.txt rules follow RFC 9309; Crawl-delay is not applied.",
                    "Fields are facts from this single crawl; none of them is a verdict."])
    log(f"Wrote {out/'inventory.csv'} and {out/'snapshot.jsonl'}.")
    return {"counts": counts, "out_dir": str(out), "warnings": warnings}
