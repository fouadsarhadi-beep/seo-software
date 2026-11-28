"""robots.txt matching following RFC 9309 (Google's rules): longest match wins, Allow wins ties,
`*` and `$` wildcards, percent-encoding normalised so Persian paths match.
Crawl-delay is NOT part of RFC 9309; it is ignored here."""
from __future__ import annotations

import re
from urllib.parse import quote, unquote, urlsplit


def _enc(s: str) -> str:
    return quote(unquote(s), safe="/%:@!$&'()*+,;=-._~?")


class RobotsPolicy:
    def __init__(self, groups, sitemaps=None, available=True):
        self.groups = groups          # {agent: [(kind, pattern, compiled)]}
        self.sitemaps = sitemaps or []
        self.available = available

    @classmethod
    def allow_all(cls, available=True):
        return cls({}, [], available)

    @classmethod
    def parse(cls, text: str):
        groups: dict[str, list] = {}
        sitemaps: list[str] = []
        current: list[str] = []
        in_rules = False
        for raw in text.splitlines():
            line = raw.split("#", 1)[0].strip()
            if ":" not in line:
                continue
            field, value = (p.strip() for p in line.split(":", 1))
            f = field.lower()
            if f == "user-agent":
                if in_rules:
                    current, in_rules = [], False
                current.append(value.lower())
            elif f in ("allow", "disallow"):
                in_rules = True
                if value == "":
                    continue          # empty Disallow = allow everything
                pat = _enc(value)
                rx = re.escape(pat).replace(r"\*", ".*")
                if rx.endswith(r"\$"):
                    rx = rx[:-2] + "$"
                for agent in current:
                    groups.setdefault(agent, []).append((f, pat, re.compile(rx)))
            elif f == "sitemap":
                sitemaps.append(value)
        return cls(groups, sitemaps)

    def _rules_for(self, agent: str):
        agent = agent.lower()
        return self.groups.get(agent) or self.groups.get("*") or []

    def check(self, url: str, agent: str = "*"):
        """-> (allowed, matching rule text or '')."""
        p = urlsplit(url)
        target = _enc((p.path or "/") + (("?" + p.query) if p.query else ""))
        best = None
        for kind, pat, rx in self._rules_for(agent):
            if rx.match(target):
                score = (len(pat), 1 if kind == "allow" else 0)
                if best is None or score > best[0]:
                    best = (score, kind, pat)
        if best is None:
            return True, ""
        return best[1] == "allow", f"{best[1].title()}: {best[2]}"

    def allowed(self, url: str, agent: str = "*") -> bool:
        return self.check(url, agent)[0]
