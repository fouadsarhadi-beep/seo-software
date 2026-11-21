"""Optional page types from explicit rules in a JSON config: {"page_types": [{"name": "blog", "url_regex": "/blog/"}]}.
Unmatched URLs are 'unknown'. The reason is always recorded so you can see why."""
from __future__ import annotations

import re
from urllib.parse import unquote


def classify(url: str, rules) -> tuple[str, str]:
    u = unquote(url)
    for rule in rules or []:
        rx = rule.get("url_regex")
        if rx and re.search(rx, u):
            return rule.get("name", "unknown"), f"url matches {rx}"
    return "unknown", "no rule matched"
