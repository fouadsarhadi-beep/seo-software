"""Robots directives from <meta> tags and X-Robots-Tag headers, combined the way Google does:
the more restrictive rule wins, `none` = noindex+nofollow, rules for other bots are kept as raw evidence."""
from __future__ import annotations

import re
from dataclasses import dataclass

_VALUE_DIRECTIVES = {"max-snippet", "max-image-preview", "max-video-preview", "unavailable_after"}
_DATE = re.compile(r"unavailable_after\s*:\s*[^;]*?(?:GMT|UTC|Z|[+-]\d{4})", re.I)
GOOGLE_AGENTS = {None, "robots", "googlebot"}


def parse_directives(value: str):
    """'googlebot: noindex, nofollow, otherbot: nosnippet' -> [(agent|None, directive), ...]"""
    value = _DATE.sub("unavailable_after", value or "")
    out, agent = [], None
    for item in value.split(","):
        item = item.strip().lower()
        if not item:
            continue
        if ":" in item:
            head, rest = (p.strip() for p in item.split(":", 1))
            if head not in _VALUE_DIRECTIVES and re.fullmatch(r"[a-z0-9_-]+", head):
                agent, item = head, rest
        if item:
            out.append((agent, item))
    return out


@dataclass
class IndexState:
    effective: str = "unknown"       # indexable | noindex | unknown | not_indexable_status
    reason: str = ""
    meta_raw: str = ""
    header_raw: str = ""
    googlebot: str = ""


def evaluate(meta_tags, header_values, fetched: bool, final_status: int, blocked_by_robots: bool) -> IndexState:
    st = IndexState()
    st.meta_raw = " | ".join(f"{n}: {c}" for n, c in meta_tags)
    st.header_raw = " | ".join(header_values or [])
    if blocked_by_robots:
        st.reason = "robots.txt blocks the crawl, so page directives cannot be read"
        return st
    if not fetched:
        st.reason = "page was not fetched"
        return st
    if final_status != 200:
        st.effective, st.reason = "not_indexable_status", f"HTTP status {final_status}"
        return st
    found = []                                        # (source, directive)
    for name, content in meta_tags:
        agent = None if name == "robots" else name
        if agent in GOOGLE_AGENTS:
            for ag, d in parse_directives(content):
                if ag in GOOGLE_AGENTS and agent in GOOGLE_AGENTS:
                    found.append((f"meta {name}", d))
        # directives with an explicit other-bot prefix inside a robots tag stay raw only
    for h in header_values or []:
        for ag, d in parse_directives(h):
            if ag in GOOGLE_AGENTS:
                found.append(("X-Robots-Tag", d))
    st.googlebot = ", ".join(sorted({d for _, d in found}))
    restrict = [(s, d) for s, d in found if d in ("noindex", "none")]
    if restrict:
        st.effective = "noindex"
        st.reason = "; ".join(sorted({f"{d} via {s}" for s, d in restrict}))
    else:
        st.effective, st.reason = "indexable", "no noindex or none directive for Googlebot"
    return st
