"""Parse each page once: head data, headings, robots meta, canonical candidates, main text."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from seo_analysis.analysis.fa_text import tokenize

DEFAULT_CONTENT_SELECTORS = [".entry-content", ".post-content", ".elementor-widget-theme-post-content",
                             "article", "main", "[role=main]", "#content"]
HEADING_TAGS = ("h1", "h2", "h3", "h4", "h5", "h6")
JS_NOTICE = re.compile(r"javascript|جاوا\s*اسکریپت", re.I)
DEFAULT_EXCLUDE = ["nav", "footer", "header", "aside", "form", "[hidden]", "[role=navigation]"]
ROBOTS_NAMES = re.compile(r"^(robots|googlebot|googlebot-news|bingbot|msnbot|slurp|yandex|[\w-]*bot)$", re.I)


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


@dataclass
class PageData:
    markup: dict = field(default_factory=dict)
    links: list = field(default_factory=list)
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
    extraction: dict = field(default_factory=dict)
    words: int = 0
    chars: int = 0


def extract_page(html: str, base_url: str, content_selector: str = "", exclude_selectors=(),
                 variants=None, collect_links=False) -> PageData:
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
    pd.markup = capture_markup(soup, base)
    if collect_links:
        pd.links = pd.markup["links"]
    for link in soup.find_all("link"):
        rel = link.get("rel") or []
        rel = rel.split() if isinstance(rel, str) else rel
        if "canonical" in [r.lower() for r in rel] and link.get("href", "").strip():
            pd.canonicals.append(urljoin(base, link["href"].strip()))
    html_tag = soup.find("html")
    pd.lang = (html_tag.get("lang") or "") if html_tag else ""

    js_notice = any(JS_NOTICE.search(tag.get_text(" ", strip=True)) for tag in soup("noscript"))
    selectors = list(dict.fromkeys(filter(None, [content_selector, *DEFAULT_CONTENT_SELECTORS])))
    for t in soup(["head", "title", "script", "style", "noscript", "template", "svg", "iframe"]):
        t.decompose()
    for selector in [*DEFAULT_EXCLUDE, *(exclude_selectors or ())]:
        try:
            excluded = soup.select(selector)
        except (ValueError, SyntaxError):
            continue
        for tag in excluded:
            if tag.parent is not None:
                tag.decompose()

    attempts = []
    pd.extraction = {"attempts": attempts, "javascript_notice": js_notice}
    pd.state = "empty"
    for selector in selectors + ["body"]:
        nodes = [soup.body or soup] if selector == "body" else soup.select(selector)
        attempts.append({"selector": selector, "matches": len(nodes), "outcome": "no match"})
        for node in nodes:
            text = node.get_text(" ", strip=True)
            words = len(tokenize(text, variants))
            heading_words = sum(len(tokenize(h.get_text(" ", strip=True), variants))
                                for h in node.find_all(HEADING_TAGS))
            if words <= heading_words or node.name in HEADING_TAGS:
                if attempts[-1]["outcome"] != "headings only":
                    attempts[-1]["outcome"] = "headings only" if words else "empty"
                continue
            pd.text, pd.words, pd.chars = text, words, len(text)
            pd.selector = selector
            pd.state = ("fallback" if selector == "body" or (content_selector and selector != content_selector)
                        or any(a["matches"] for a in attempts[:-1]) else "success")
            attempts[-1]["outcome"] = "selected"
            break
        if pd.words:
            break
    return pd

def capture_markup(soup, base):
    facts = {"links": [], "alternates": [], "assets": [], "schema": [], "limited": False}
    limit = 2048
    def resolved(raw):
        try:
            url = urljoin(base, raw.strip())
            return url if url.startswith(("https://", "http://")) else ""
        except ValueError:
            return ""
    seen = set()
    for tag in soup.find_all(["a", "img", "link", "script"]):
        if tag.name == "script" and str(tag.get("type", "")).lower() == "application/ld+json":
            field = "schema"
            try:
                data = json.loads(tag.get_text())
                nodes = data if isinstance(data, list) else [data]
                types = set()
                while nodes:
                    node = nodes.pop()
                    if not isinstance(node, dict):
                        continue
                    if isinstance(node.get("@graph"), list):
                        nodes.extend(node["@graph"])
                    value = node.get("@type", [])
                    types.update(t for t in (value if isinstance(value, list) else [value]) if isinstance(t, str))
                item = {"state": "types observed" if types else "no typed entity", "types": sorted(types)}
            except (ValueError, RecursionError):
                item = {"state": "invalid JSON-LD", "types": []}
        else:
            url = resolved(tag.get("href") or tag.get("src") or "") if tag.get("href") or tag.get("src") else ""
            if not url:
                continue
            if tag.name == "a":
                if url in seen:
                    continue
                if len(seen) < limit:
                    seen.add(url)
                field, item = "links", url
            elif tag.name == "link" and "alternate" in tag.get("rel", []) and tag.has_attr("hreflang"):
                field, item = "alternates", [tag["hreflang"], url]
            elif tag.name in ("img", "script") or "stylesheet" in tag.get("rel", []):
                alt = ("absent" if "alt" not in tag.attrs else "empty" if not tag["alt"].strip() else "present")
                field, item = "assets", {"kind": tag.name, "url": url, "alt_state": alt if tag.name == "img" else ""}
            else:
                continue
        if len(facts[field]) < limit:
            facts[field].append(item)
        else:
            facts["limited"] = True
    return facts
