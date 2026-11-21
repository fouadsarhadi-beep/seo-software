"""Analysis of a saved crawl. Re-runnable with different settings without touching the website again."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from seo_analysis.analysis import canon, fa_text, similarity
from seo_analysis.connectors import gsc
from seo_analysis.reporting.report import write_csv, write_manifest
from seo_analysis.core.urls import url_key

PAIR_HEADER = [
    # first six = original layout
    "URL A", "URL B", "Title similarity", "Near-duplicate score", "Topic overlap score", "Same H1",
    # new in V2
    "Containment", "Triggered signals", "Independent signal families", "Shared terms", "Shared phrases",
    "Page type A", "Page type B", "Cross-type", "Words A", "Words B", "Short-page note",
    "Clicks A", "Clicks B", "Impressions A", "Impressions B", "Shared GSC queries", "Top shared queries",
]
CANON_HEADER = ["URL", "HTTP status", "Effective indexability", "Canonical candidates", "Canonical relationship",
                "Canonical target status", "Canonical issues", "Pages pointing here"]


def load_snapshot(path):
    return [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]


def canonical_info(records):
    return canon.analyze([{"url": r["url"], "final_url": r["final_url"], "final_status": r["final_status"],
                           "canonicals_html": r["canonicals_html"], "canonicals_header": r["canonicals_header"],
                           "effective_indexability": r["effective_indexability"]} for r in records])


def summarize(records, info, pairs_count, thin_words=300) -> str:
    ok = [r for r in records if r["fetch_state"].startswith("ok")]
    def lst(title, items, limit=8):
        s = [f"\n{title}: {len(items)}"]
        s += [f"   - {x}" for x in items[:limit]]
        if len(items) > limit:
            s.append(f"   ... and {len(items) - limit} more (see the CSV files)")
        return s
    L = ["ERRORS (concrete faults; check each)"]
    L += lst("Sitemap URLs that do not return HTTP 200 after redirects",
             [f"{r['url']} ({r['fetch_state']}, status {r['final_status'] or r['error']})" for r in records
              if r["fetch_state"] in ("client_error", "server_error", "fetch_error", "redirect_loop", "redirect_too_many")])
    L += lst("Canonical problems (target missing, broken, noindex, chain, loop, conflict)",
             [f"{u}: {v['issues']}" for u, v in info.items() if v["issues"]])
    L += ["\nWARNINGS (may be fine; need context)"]
    L += lst("Sitemap URLs that redirect (the sitemap should list final URLs)",
             [f"{r['url']} -> {r['final_url']}" for r in records if len(r["chain"]) > 1 and r["fetch_state"].startswith("ok")])
    L += lst("Sitemap URLs that are noindex", [r["url"] for r in ok if r["effective_indexability"] == "noindex"])
    L += lst("Canonical points to another page", [f"{u} -> {v['candidates']}" for u, v in info.items()
                                                   if v["relationship"] == "points to another page"])
    L += lst("Skipped by robots.txt", [r["url"] for r in records if r["fetch_state"] == "robots_disallowed"])
    L += lst("Redirects blocked (outside allowed hosts or robots)",
             [f"{r['url']} ({r['redirect_note']})" for r in records if r["fetch_state"] in ("redirect_blocked_external", "redirect_blocked_robots")])
    L += ["\nREVIEW (opportunities, not faults)"]
    L += lst("No canonical tag (informational: Google can choose one itself)", [r["url"] for r in ok if not info[r["url"]]["candidates"]])
    L += lst("Missing title", [r["url"] for r in ok if not r["title"]])
    L += lst("Missing meta description", [r["url"] for r in ok if not r["meta"]])
    L += lst("No H1", [r["url"] for r in ok if r["h1_count"] == 0])
    L += lst("More than one H1 (not an error by itself)", [r["url"] for r in ok if r["h1_count"] > 1])
    L += lst(f"Under {thin_words} words (a review trigger, not a Google rule)", [f"{r['url']} ({r['words']})" for r in ok if r["words"] < thin_words])
    L += lst("Text extraction fell back or found nothing (word counts may be wrong)",
             [f"{r['url']} ({r['extraction_state']}, {r['extraction_selector']})" for r in ok if r["extraction_state"] in ("fallback", "empty")])
    for label, key in (("Duplicate titles", "title"), ("Duplicate H1s", "h1")):
        g = defaultdict(list)
        for r in ok:
            if r[key]:
                g[" ".join(fa_text.tokenize(r[key]))].append(r["url"])
        L += lst(label, [f"{len(u)}x: {', '.join(u)}" for u in g.values() if len(u) > 1])
    L += [f"\nOverlapping page pairs flagged: {pairs_count}   (candidates for YOUR review, not verdicts)"]
    L += ["Similarity is not proof of keyword cannibalization. Pages with similar wording can serve different intents."]
    return "\n".join(L)


def run_analyze(in_dir, out_dir=None, gsc_pages=None, gsc_queries=None, settings=None, stopwords_file=None,
                variants_file=None, normalizer="basic", stem=False, include_noindex=False, log=print) -> dict:
    in_dir = Path(in_dir)
    out = Path(out_dir or in_dir)
    out.mkdir(parents=True, exist_ok=True)
    settings = settings or similarity.Settings()
    records = load_snapshot(in_dir / "snapshot.jsonl")
    info = canonical_info(records)

    vfile = variants_file or (in_dir / "persian_variants.json")
    variants = fa_text.load_variants(vfile)
    if variants:
        log(f"Using {len(variants)} Persian spelling variant(s) you approved ({vfile}).")
    stop = fa_text.load_stopwords(stopwords_file)
    stem_fn, hz = None, None
    if normalizer == "hazm" or stem:
        hz = fa_text.HazmNormalizer(stem=stem)
        stem_fn = hz.stem_token if stem else None
    pages = gsc.load_pages(gsc_pages) if gsc_pages else {}
    qpairs = gsc.load_query_page(gsc_queries) if gsc_queries else {}

    items = []
    for r in records:
        if not r["fetch_state"].startswith("ok") or r["words"] == 0:
            continue
        if r["effective_indexability"] == "noindex" and not include_noindex:
            continue
        text = hz.normalize(r["text"]) if (hz and normalizer == "hazm") else r["text"]
        items.append({"url": r["url"], "title": r["title"], "h1": r["h1"], "text": text, "page_type": r["page_type"]})
    log(f"Comparing {len(items)} pages ({len(items) * (len(items) - 1) // 2} pairs)...")
    corpus = similarity.prepare(items, settings, stop, variants, stem_fn)
    results = similarity.compare(corpus)
    title_of = {i["url"]: i["title"] for i in items}

    rows, pairs_json = [], []
    for p in results:
        ga, gb = pages.get(url_key(p.url_a), {}), pages.get(url_key(p.url_b), {})
        count, top = gsc.shared_queries(qpairs, p.url_a, p.url_b) if qpairs else (0, [])
        evidence = p.evidence + (1 if count >= 3 else 0)
        triggers = list(p.triggers) + (["shared GSC queries"] if count >= 3 else [])
        rows.append([p.url_a, p.url_b, p.title_sim, p.dup, p.topic, "YES" if p.same_h1 else "NO",
                     p.containment, "; ".join(triggers), evidence, "، ".join(p.shared_terms), " / ".join(p.shared_phrases),
                     p.page_type_a, p.page_type_b, "yes" if p.page_type_a != p.page_type_b else "no",
                     p.words_a, p.words_b, "short page: scores can be noisy" if p.short_page else "",
                     ga.get("clicks", ""), gb.get("clicks", ""), ga.get("impressions", ""), gb.get("impressions", ""),
                     count if qpairs else "", "; ".join(f"{q} ({a:.0f}/{b:.0f})" for q, a, b in top)])
        pairs_json.append({"url_a": p.url_a, "url_b": p.url_b, "title_a": title_of[p.url_a], "title_b": title_of[p.url_b],
                           "title_sim": p.title_sim, "dup": p.dup, "containment": p.containment, "topic": p.topic,
                           "same_h1": p.same_h1, "shared_terms": p.shared_terms, "shared_phrases": p.shared_phrases,
                           "triggers": triggers, "evidence": evidence, "page_type_a": p.page_type_a,
                           "page_type_b": p.page_type_b, "words_a": p.words_a, "words_b": p.words_b, "short_page": p.short_page,
                           "gsc": ({"clicks_a": ga.get("clicks", 0), "clicks_b": gb.get("clicks", 0),
                                    "impr_a": ga.get("impressions", 0), "impr_b": gb.get("impressions", 0),
                                    "shared_count": count, "shared_top": top} if (pages or qpairs) else None)})
    rows_order = sorted(range(len(rows)), key=lambda i: -rows[i][8])
    write_csv(out / "similar_pairs.csv", PAIR_HEADER, [rows[i] for i in rows_order])
    (out / "pairs.json").write_text(json.dumps([pairs_json[i] for i in rows_order], ensure_ascii=False, indent=1), encoding="utf-8")
    canon_rows = [[r["url"], r["final_status"], r["effective_indexability"], info[r["url"]]["candidates"],
                   info[r["url"]]["relationship"], info[r["url"]]["target_status"], info[r["url"]]["issues"],
                   info[r["url"]]["pointing_here"]] for r in records
                  if info[r["url"]]["issues"] or info[r["url"]]["relationship"] not in ("self", "")]
    write_csv(out / "canonical_report.csv", CANON_HEADER, canon_rows)
    text = summarize(records, info, len(results))
    (out / "issues.txt").write_text(text, encoding="utf-8")
    counts = {"pages_compared": len(items), "pairs_flagged": len(results), "canonical_rows": len(canon_rows)}
    write_manifest(out / "analysis_manifest.json", "analyze",
                   {"settings": settings.__dict__ | {"brand_terms": list(settings.brand_terms)},
                    "normalizer": normalizer if hz else fa_text.NORMALIZER_VERSION, "stem": stem,
                    "stopwords_version": fa_text.STOPWORDS_VERSION, "variants": len(variants),
                    "gsc_pages": bool(pages), "gsc_query_page": bool(qpairs), "include_noindex": include_noindex},
                   counts, ["similar_pairs.csv", "pairs.json", "canonical_report.csv", "issues.txt"], [],
                   ["Thresholds are starting values, provisional until you calibrate them with your own decisions.",
                    "Similarity is not proof of cannibalization.",
                    "Search Console data: a missing query row does not prove a page never appeared for it."])
    log(text)
    return {"counts": counts, "out_dir": str(out)}
