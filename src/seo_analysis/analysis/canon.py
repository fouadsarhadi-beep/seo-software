"""Canonical analysis: candidates (HTML + Link header), relationship to the URL, target checks,
chains, loops, and how many pages point at each target. Facts only; a missing canonical is not an error."""
from __future__ import annotations

import re
from urllib.parse import urljoin

from seo_analysis.core.urls import relation, url_key

_LINK = re.compile(r"<([^>]*)>\s*((?:;\s*[^;,]+)*)")


def header_canonicals(link_headers, base_url: str) -> list:
    out = []
    for h in link_headers or []:
        for m in _LINK.finditer(h):
            params = m.group(2).lower()
            if re.search(r"rel\s*=\s*\"?[^\";]*\bcanonical\b", params):
                out.append(urljoin(base_url, m.group(1).strip()))
    return out


def analyze(records: list) -> dict:
    """records: dicts with url, final_url, final_status, canonicals_html, canonicals_header,
    effective_indexability. -> {url: {candidates, relationship, target_status, issues, pointing_here}}"""
    index = {}
    for r in records:
        index[url_key(r["url"])] = r
        if r.get("final_url") and (not r.get("redirect_note")) and r.get("final_status"):
            index.setdefault(url_key(r["final_url"]), r)
    pointing: dict[str, int] = {}
    prelim = {}
    for r in records:
        cands = list(r.get("canonicals_html") or [])
        hdr = list(r.get("canonicals_header") or [])
        all_c = cands + hdr
        uniq = list(dict.fromkeys(all_c))
        prelim[r["url"]] = (all_c, uniq, cands, hdr)
        if len({url_key(u) for u in uniq}) == 1:
            tgt = uniq[0]
            if relation(r["final_url"] or r["url"], tgt)[0] == "other":
                pointing[url_key(tgt)] = pointing.get(url_key(tgt), 0) + 1

    out = {}
    for r in records:
        all_c, uniq, html_c, hdr_c = prelim[r["url"]]
        base = r.get("final_url") or r["url"]
        issues, rel_text, tstatus = [], "", ""
        keys = {url_key(u) for u in uniq}
        if not uniq:
            rel_text = "missing" if r.get("final_status") == 200 else ""
        elif len(keys) > 1:
            rel_text = "conflicting canonicals"
            issues.append("conflicting canonicals: " + " | ".join(uniq))
        else:
            if len(all_c) > 1:
                issues.append("canonical declared more than once (same target)")
            if html_c and hdr_c and {url_key(u) for u in html_c} != {url_key(u) for u in hdr_c}:
                issues.append("HTML canonical and Link-header canonical differ")
            tgt = uniq[0]
            code, human = relation(base, tgt)
            if code == "same":
                rel_text = "self"
            elif code == "same_encoding":
                rel_text = "self (written differently: encoding or case)"
            elif code == "variant":
                rel_text = "variant of itself: " + human
                issues.append("canonical differs from the page URL only by " + human.replace("differs only by ", ""))
            else:
                rel_text = "points to another page"
            if code in ("variant", "other"):
                tr = index.get(url_key(tgt))
                if tr is None:
                    tstatus = "not in crawl"
                    issues.append("canonical target is not in the crawl (check it manually)")
                else:
                    redirected = (url_key(tr["url"]) == url_key(tgt)
                                  and tr.get("first_status") in (301, 302, 303, 307, 308))
                    tstatus = str(tr.get("first_status") if redirected else tr.get("final_status"))
                    if redirected:
                        issues.append(f"canonical target redirects (HTTP {tstatus})")
                    if tr.get("final_status") != 200:
                        issues.append(f"canonical target returns HTTP {tr.get('final_status')}")
                    if tr.get("effective_indexability") == "noindex":
                        issues.append("canonical target is noindex")
                    # chain / loop
                    seen, cur, hops = {url_key(base)}, tr, 0
                    while cur is not None and hops < 6:
                        nxt = list(dict.fromkeys((cur.get("canonicals_html") or []) + (cur.get("canonicals_header") or [])))
                        if len({url_key(u) for u in nxt}) != 1:
                            break
                        nk = url_key(nxt[0])
                        if nk == url_key(cur.get("final_url") or cur["url"]):
                            break
                        if nk in seen:
                            issues.append("canonical loop")
                            break
                        seen.add(nk)
                        hops += 1
                        cur = index.get(nk)
                        if hops == 1 and cur is not None:
                            issues.append("canonical chain: the target points to yet another page")
                    # de-duplicate issue text
                    issues = list(dict.fromkeys(issues))
        out[r["url"]] = {
            "candidates": " | ".join(uniq),
            "relationship": rel_text,
            "target_status": tstatus,
            "issues": "; ".join(issues),
            "pointing_here": pointing.get(url_key(r["url"]), 0) + (
                pointing.get(url_key(r.get("final_url") or r["url"]), 0)
                if url_key(r.get("final_url") or r["url"]) != url_key(r["url"]) else 0),
        }
    return out
