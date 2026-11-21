"""Structural sitemap parsing. Only <url><loc> and <sitemap><loc> are pages; nested
extension elements (image:loc, video:content_loc, ...) are NOT page URLs."""
from __future__ import annotations

from collections import deque
import re
import xml.etree.ElementTree as ET
import zlib
from dataclasses import dataclass

from seo_analysis.core.urls import url_key


@dataclass
class SitemapEntry:
    url: str
    lastmod: str
    source: str
    raw_url: str = ""


def _ln(tag) -> str:
    return tag.rsplit("}", 1)[-1].lower() if isinstance(tag, str) else ""


def _child_text(el, name: str) -> str:
    for c in el:                      # direct children only
        if _ln(c.tag) == name:
            return (c.text or "").strip()
    return ""


def gunzip_capped(data: bytes, cap: int) -> bytes:
    d = zlib.decompressobj(16 + zlib.MAX_WBITS)
    out = d.decompress(data, cap + 1)
    if len(out) > cap or d.unconsumed_tail:
        raise ValueError(f"decompressed sitemap is larger than {cap} bytes")
    return out


def parse_sitemap(data: bytes, cap: int = 50_000_000):
    """-> ('index'|'urlset', [(loc, lastmod)])."""
    if data[:2] == b"\x1f\x8b":
        data = gunzip_capped(data, cap)
    if len(data) > cap:
        raise ValueError("sitemap is larger than the size cap")
    if b"<!ENTITY" in data[:4096] or b"<!DOCTYPE" in data[:200] and b"[" in data[:4096]:
        raise ValueError("sitemaps with DTD/entity declarations are refused")
    root = ET.fromstring(data)
    name = _ln(root.tag)
    items = []
    if name == "sitemapindex":
        for child in root:
            if _ln(child.tag) == "sitemap":
                loc = _child_text(child, "loc")
                if loc:
                    items.append((loc, _child_text(child, "lastmod")))
        return "index", items
    if name == "urlset":
        for child in root:
            if _ln(child.tag) == "url":
                loc = _child_text(child, "loc")
                if loc:
                    items.append((loc, _child_text(child, "lastmod")))
        return "urlset", items
    raise ValueError(f"unexpected root element <{name}>")


def collect(fetcher, sitemap_url: str, skip_re: str = "", cap: int = 50_000_000, max_depth: int = 4, max_entries: int = 10001):
    """-> (entries, warnings, sitemap_files_read)."""
    skip = re.compile(skip_re) if skip_re else None
    entries, warnings, files = [], [], []
    seen_maps, seen_pages = set(), set()
    stack = deque([(sitemap_url, 0, "")])
    while stack:
        smap, depth, _parent = stack.popleft()
        if not fetcher.in_scope(smap):
            warnings.append(f"sitemap outside the allowed hosts, not fetched: {smap}")
            continue
        key = url_key(smap)
        if key in seen_maps:
            warnings.append(f"sitemap already visited (recursive or repeated reference): {smap}")
            continue
        seen_maps.add(key)
        res = fetcher.get(smap)
        if res.final_status != 200 or not res.raw:
            warnings.append(f"cannot read sitemap {smap} (status {res.final_status or res.error})")
            continue
        try:
            kind, items = parse_sitemap(res.raw, cap)
        except Exception as exc:
            warnings.append(f"malformed sitemap {smap}: {exc}")
            continue
        files.append(smap)
        if kind == "index":
            if depth >= max_depth:
                warnings.append(f"sitemap nesting deeper than {max_depth}, stopped at {smap}")
                continue
            for loc, _lm in items:
                if skip and skip.search(loc):
                    warnings.append(f"sitemap skipped by pattern: {loc}")
                    continue
                if len(stack) >= fetcher.budget.limit:
                    warnings.append("sitemap queue reached the request limit")
                    break
                stack.append((loc, depth + 1, smap))
        else:
            for loc, lastmod in items:
                if not fetcher.in_scope(loc):
                    warnings.append(f"page URL outside the allowed hosts, ignored: {loc}")
                    continue
                k = url_key(loc)
                if k in seen_pages:
                    warnings.append(f"duplicate URL in sitemaps, kept the first: {loc}")
                    continue
                seen_pages.add(k)
                entries.append(SitemapEntry(loc, lastmod, smap))
                if len(entries) >= max_entries:
                    return entries, warnings, files
    return entries, warnings, files
