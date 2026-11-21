"""Parse each page once: head data, headings, robots meta, canonical candidates, main text."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from seo_analysis.analysis.fa_text import tokenize

DEFAULT_CONTENT_SELECTORS = ["main", "article", "[role=main]", ".entry-content", ".post-content",
                             ".elementor-widget-theme-post-content", "#content"]
DEFAULT_EXCLUDE = ["nav", "footer", "header", "aside", "form"]
ROBOTS_NAMES = re.compile(r"^(robots|googlebot|googlebot-news|bingbot|msnbot|slurp|yandex|[\w-]*bot)$", re.I)


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


@dataclass
class PageData:
    title: str = ""
    h1_list: list = field(default_factory=list)
    h2_count: int = 0
    meta_description: str = ""
    robots_meta: list = field(default_factory=list)       # [(name, content)]
    canonicals: list = field(default_factory=list)        # resolved URLs, in document order
    lang: str = ""
    text: str = ""
    selector: str = ""
    state: str = ""                                       # success | fallback | empty
    words: int = 0
    chars: int = 0


def extract_page(html: str, base_url: str, content_selector: str = "", exclude_selectors=(),
                 variants=None) -> PageData:
    soup = BeautifulSoup(html, "html.parser")
    pd = PageData()
    pd.title = _clean(soup.title.get_text(" ")) if soup.title else ""
    pd.h1_list = [_clean(h.get_text(" ")) for h in soup.find_all("h1")]
    pd.h2_count = len(soup.find_all("h2"))
    tag = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
    pd.meta_description = _clean(tag.get("content", "")) if tag else ""
    for m in soup.find_all("meta"):
        name = m.get("name") or ""
        if ROBOTS_NAMES.match(name) and m.get("content") is not None:
            pd.robots_meta.append((name.lower(), _clean(m["content"])))
    base_tag = soup.find("base", href=True)
    base = urljoin(base_url, base_tag["href"]) if base_tag else base_url
    for link in soup.find_all("link"):
        rel = link.get("rel") or []
        rel = rel.split() if isinstance(rel, str) else rel
        if "canonical" in [r.lower() for r in rel] and link.get("href", "").strip():
            pd.canonicals.append(urljoin(base, link["href"].strip()))
    html_tag = soup.find("html")
    pd.lang = (html_tag.get("lang") or "") if html_tag else ""

    for t in soup(["script", "style", "noscript", "template", "svg", "iframe"]):
        t.decompose()
    node, used = None, ""
    if content_selector:
        node = soup.select_one(content_selector)
        used = content_selector if node is not None else ""
    if node is None:
        for sel in DEFAULT_CONTENT_SELECTORS:
            node = soup.select_one(sel)
            if node is not None:
                used = sel
                break
    fallback = False
    if node is None:
        node, used, fallback = (soup.body or soup), "body", True
    for sel in list(DEFAULT_EXCLUDE) + list(exclude_selectors or ()):
        try:
            for t in node.select(sel):
                t.decompose()
        except Exception:
            continue
    pd.text = node.get_text(" ", strip=True)
    pd.selector = used
    pd.words = len(tokenize(pd.text, variants))
    pd.chars = len(pd.text)
    if pd.words == 0:
        pd.state = "empty"
    elif fallback or (content_selector and used != content_selector):
        pd.state = "fallback"
    else:
        pd.state = "success"
    return pd
