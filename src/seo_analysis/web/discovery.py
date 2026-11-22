"""Single-origin, bounded discovery for site, sitemap and URL-list inputs."""
import csv
from collections import Counter, deque
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlsplit

from seo_analysis.core.network import HttpOrigin
from seo_analysis.core.urls import url_key
from seo_analysis.web.sitemap import SitemapEntry, collect


def read_seeds(filename):
    path = Path(filename)
    if path.stat().st_size > 4_000_000:
        raise ValueError("URL list exceeds 4 MB.")
    with path.open(encoding="utf-8-sig", newline="") as stream:
        if path.suffix.lower() == ".csv":
            rows = csv.DictReader(stream)
            field = next((k for k in rows.fieldnames or [] if k.strip().lower() == "url"), None)
            if field is None:
                raise ValueError("URL CSV requires a URL column.")
            values = [row[field] for row in rows]
        else:
            values = list(stream)
    urls = [value.strip() for value in values if value and value.strip()]
    if not urls:
        raise ValueError("URL list is empty.")
    origin = HttpOrigin.from_url(urls[0])
    if any(not origin.allows(url) for url in urls):
        raise ValueError("All seed URLs must belong to the same HTTP origin.")
    return urls


class Discovery:
    def __init__(self, cfg, fetcher):
        self.cfg = cfg
        self.fetcher = fetcher
        self.queue = deque()
        self.seen = set()
        self.variants = Counter()
        self.skipped = Counter()
        self.files = []
        self.warnings = []
        self.follow_links = False
        self.incomplete_maps = False

    def add(self, entry, depth):
        url = urldefrag(entry.url).url
        if not self.fetcher.in_scope(url):
            self.skipped["outside_origin"] += 1
            return
        key = url_key(url)
        if key in self.seen:
            return
        parts = urlsplit(key)
        if len(self.seen) >= self.cfg.limit:
            self.skipped["page_limit"] += 1
            return
        if depth > self.cfg.max_depth:
            self.skipped["depth_limit"] += 1
            return
        if parts.query:
            if self.variants[parts.path] >= self.cfg.max_variants:
                self.skipped["parameter_limit"] += 1
                return
            self.variants[parts.path] += 1
        self.seen.add(key)
        self.queue.append((SitemapEntry(url, entry.lastmod, entry.source, entry.url), depth))

    def discover(self, policy, prompt=None):
        cfg = self.cfg
        if cfg.kind == "urls_file":
            for url in cfg.seeds:
                self.add(SitemapEntry(url, "", cfg.source), 0)
            return
        maps = [cfg.sitemap]
        if cfg.kind == "website":
            maps = list(dict.fromkeys(policy.sitemaps + [
                urljoin(cfg.sitemap, path) for path in cfg.sitemap_paths]))
        declared = set(policy.sitemaps) if cfg.kind == "website" else set()
        for url in maps:
            if self.queue and url not in declared:
                break
            entries, warnings, files = collect(self.fetcher, url, cfg.skip_sitemap,
                                               max_entries=cfg.limit + 1, cap=cfg.max_bytes)
            self.warnings.extend(warnings)
            self.files.extend(files)
            if files or url in declared:
                self.incomplete_maps |= any(w.startswith(("cannot read", "malformed", "sitemap nesting", "sitemap queue")) for w in warnings)
            for entry in entries:
                self.add(entry, 0)
        if self.queue:
            return
        if cfg.kind == "website":
            use_links = cfg.link_crawl or (prompt and prompt(
                f"No usable sitemap. Follow internal links (pages {cfg.limit}, depth {cfg.max_depth})? [y/N] "
            ).strip().lower() == "y")
            if use_links:
                self.follow_links = True
                self.add(SitemapEntry(cfg.sitemap, "", "website seed"), 0)
            else:
                self.warnings.append("No usable sitemap. Select --link-crawl to follow bounded internal links.")
