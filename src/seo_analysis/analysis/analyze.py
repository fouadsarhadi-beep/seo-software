"""Analysis of a saved crawl. Re-runnable with different settings without touching the website again."""
from __future__ import annotations

from hashlib import sha256
import json
from collections import defaultdict
from pathlib import Path

from seo_analysis.core.artifacts import write_json, write_text
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
    return canon.analyze(records)


def comparison_coverage(counts):
    compared = counts["pages_compared"]
    if compared < 2:
        return f"Content comparison requires at least two eligible pages. This run had {compared}."
    extracted = counts["pages_extracted"]
    html = counts["html_pages"]
    if compared < html:
        message = f"Content comparison covered {compared} of {html} HTML pages. Usable text was extracted from {extracted}."
        if counts["noindex_excluded"]:
            message += f" Pages excluded by noindex: {counts['noindex_excluded']}."
        return message
    return ""


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
    L += lst(f"Under {thin_words} words (a review trigger, not a Google rule)", [f"{r['url']} ({r['words']})" for r in ok if 0 < r["words"] < thin_words and r["fetch_state"] != "ok_truncated"])
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
                variants_file=None, normalizer="basic", stem=False, include_noindex=False, log=print, *,
                sample_per_stratum=0, sample_seed=0) -> dict:
    if not 0 <= sample_per_stratum <= 1000:
        raise ValueError("Choose 0–1000 calibration pairs per stratum.")
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
    html_pages = [r for r in records if r["fetch_state"].startswith("ok")]
    extracted = [r for r in html_pages if r["words"] > 0 and r["text"].strip()
                 and r["fetch_state"] != "ok_truncated"]
    noindex_excluded = 0
    for r in extracted:
        if r["effective_indexability"] == "noindex" and not include_noindex:
            noindex_excluded += 1
            continue
        text = hz.normalize(r["text"]) if (hz and normalizer == "hazm") else r["text"]
        items.append({"url": r["url"], "title": r["title"], "h1": r["h1"], "text": text, "page_type": r["page_type"]})
    log(f"Comparing {len(items)} pages ({len(items) * (len(items) - 1) // 2} pairs)...")
    corpus = similarity.prepare(items, settings, stop, variants, stem_fn)
    results = similarity.compare(corpus)
    revisions = {r["url"]: sha256(json.dumps([r.get(k) for k in ("text", "title", "h1", "effective_indexability")], ensure_ascii=False).encode()).hexdigest() for r in records}
    title_of = {i["url"]: i["title"] for i in items}

    def pair_record(p, ga, gb, count, top, comparable, triggers, evidence):
        return {"content_revisions": {p.url_a: revisions[p.url_a], p.url_b: revisions[p.url_b]},
                           "source_snapshot": str(in_dir.resolve()), "url_a": p.url_a, "url_b": p.url_b, "title_a": title_of[p.url_a], "title_b": title_of[p.url_b],
                           "title_sim": p.title_sim, "dup": p.dup, "containment": p.containment, "topic": p.topic,
                           "same_h1": p.same_h1, "shared_terms": p.shared_terms, "shared_phrases": p.shared_phrases,
                           "triggers": triggers, "evidence": evidence, "page_type_a": p.page_type_a,
                           "page_type_b": p.page_type_b, "words_a": p.words_a, "words_b": p.words_b, "short_page": p.short_page,
                           "gsc": ({"clicks_a": ga.get("clicks"), "clicks_b": gb.get("clicks"),
                                    "impr_a": ga.get("impressions"), "impr_b": gb.get("impressions"),
                                    "shared_count": count if comparable else None, "shared_top": top} if (pages or qpairs) else None)}

    rows, pairs_json = [], []
    for p in results:
        ga, gb = pages.get(url_key(p.url_a), {}), pages.get(url_key(p.url_b), {})
        comparable = url_key(p.url_a) in qpairs and url_key(p.url_b) in qpairs
        count, top = gsc.shared_queries(qpairs, p.url_a, p.url_b) if comparable else (0, [])
        evidence = p.evidence + (1 if count >= 3 else 0)
        triggers = list(p.triggers) + (["shared GSC queries"] if count >= 3 else [])
        rows.append([p.url_a, p.url_b, p.title_sim, p.dup, p.topic, "YES" if p.same_h1 else "NO",
                     p.containment, "; ".join(triggers), evidence, "، ".join(p.shared_terms), " / ".join(p.shared_phrases),
                     p.page_type_a, p.page_type_b, "yes" if p.page_type_a != p.page_type_b else "no",
                     p.words_a, p.words_b, "short page: scores can be noisy" if p.short_page else "",
                     ga.get("clicks", ""), gb.get("clicks", ""), ga.get("impressions", ""), gb.get("impressions", ""),
                     count if comparable else "", "; ".join(f"{q} ({gsc.display_metric(a)}/{gsc.display_metric(b)})" for q, a, b in top)])
        pairs_json.append(pair_record(p, ga, gb, count, top, comparable, triggers, evidence))
    rows_order = sorted(range(len(rows)), key=lambda i: -rows[i][8])
    write_csv(out / "similar_pairs.csv", PAIR_HEADER, [rows[i] for i in rows_order])
    write_json(out / "pairs.json", [pairs_json[i] for i in rows_order])
    artifacts = ["similar_pairs.csv", "pairs.json", "canonical_report.csv", "issues.txt"]
    if sample_per_stratum:
        population, sample = similarity.calibration_sample(corpus, results, sample_per_stratum, sample_seed)
        pairs = []
        for stratum, pair in sample:
            comparable = url_key(pair.url_a) in qpairs and url_key(pair.url_b) in qpairs
            count, top = gsc.shared_queries(qpairs, pair.url_a, pair.url_b) if comparable else (0, [])
            triggers = pair.triggers + (["shared GSC queries"] if count >= 3 else [])
            row = pair_record(pair, pages.get(url_key(pair.url_a), {}), pages.get(url_key(pair.url_b), {}),
                              count, top, comparable, triggers, pair.evidence + (1 if count >= 3 else 0))
            pairs.append(row | {"stratum": stratum})
        write_json(out / "calibration-sample.json", {"schema_version": 1, "seed": sample_seed,
                                                    "population": population, "pairs": pairs})
        artifacts.append("calibration-sample.json")
    canon_rows = [[r["url"], r["final_status"], r["effective_indexability"], info[r["url"]]["candidates"],
                   info[r["url"]]["relationship"], info[r["url"]]["target_status"], info[r["url"]]["issues"],
                   info[r["url"]]["pointing_here"]] for r in records
                  if info[r["url"]]["issues"] or info[r["url"]]["relationship"] not in ("self", "")]
    write_csv(out / "canonical_report.csv", CANON_HEADER, canon_rows)
    counts = {"html_pages": len(html_pages), "pages_extracted": len(extracted),
              "pages_compared": len(items), "pairs_flagged": len(results), "canonical_rows": len(canon_rows),
              "noindex_excluded": noindex_excluded}
    coverage = comparison_coverage(counts)
    text = summarize(records, info, len(results))
    if coverage:
        text = coverage + "\n\n" + text
    write_text(out / "issues.txt", text)
    write_manifest(out / "analysis_manifest.json", "analyze",
                   {"settings": settings.__dict__ | {"brand_terms": list(settings.brand_terms)},
                    "normalizer": normalizer if hz else fa_text.NORMALIZER_VERSION, "stem": stem,
                    "stopwords_version": fa_text.STOPWORDS_VERSION, "variants": len(variants),
                    "gsc_pages": bool(pages), "gsc_query_page": bool(qpairs), "include_noindex": include_noindex},
                   counts, artifacts, [coverage] if coverage else [],
                   ["Thresholds are starting values, provisional until you calibrate them with your own decisions.",
                    "Similarity is not proof of cannibalization.",
                    "Search Console data: a missing query row does not prove a page never appeared for it."])
    log(text)
    return {"counts": counts, "out_dir": str(out), "warnings": [coverage] if coverage else []}
