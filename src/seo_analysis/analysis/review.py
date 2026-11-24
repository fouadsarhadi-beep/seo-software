"""You are the judge. This module shows the evidence for each flagged pair and records YOUR decision.
Nothing is changed on the website. Decisions are saved one by one, so you can stop and resume."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from filelock import FileLock

from seo_analysis import __version__
from seo_analysis.connectors.gsc import display_metric
from seo_analysis.core.artifacts import atomic_text
from seo_analysis.core.urls import url_key

CHOICES = {
    "1": "merge_a_into_b", "2": "merge_b_into_a", "3": "canonical_a_to_b", "4": "canonical_b_to_a",
    "d": "differentiate", "i": "ignore",
}
MENU = ("  [1] merge A into B (A gets a 301 to B)   [2] merge B into A\n"
        "  [3] keep both, canonical A -> B          [4] keep both, canonical B -> A\n"
        "  [d] differentiate (rewrite one so they stop competing)   [i] ignore (not a problem)\n"
        "  [n] add a note   [s] skip for now   [q] quit")


def pair_key(a: str, b: str) -> str:
    return "|".join(sorted([url_key(a), url_key(b)]))


def load_decisions(path) -> dict:
    p = Path(path)
    out = {}
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                d = json.loads(line)
                out[pair_key(d["url_a"], d["url_b"])] = d
    return out


def needs_review(pair, decision):
    return decision is None or decision.get("content_revisions") != pair.get("content_revisions")


def save_decision(path, pair, decision, note):
    if decision not in CHOICES.values():
        raise ValueError("Choose a listed review decision.")
    record = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "tool_version": __version__,
              "url_a": pair["url_a"], "url_b": pair["url_b"], "decision": decision, "note": note,
              "content_revisions": pair.get("content_revisions"), "source_snapshot": pair.get("source_snapshot"),
              "scores": {key: pair[key] for key in ("dup", "containment", "topic", "title_sim")},
              "same_h1": pair["same_h1"], "triggers": pair["triggers"]}
    path = Path(path)
    with FileLock(str(path.with_name(f".{path.name}.lock")), timeout=10):
        previous = path.read_text(encoding="utf-8") if path.exists() else ""
        with atomic_text(path) as stream:
            if previous:
                stream.write(previous.rstrip("\n") + "\n")
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")


def _fmt(p: dict) -> str:
    lines = [
        "=" * 78,
        f"A: {p['url_a']}", f"   title: {p.get('title_a', '')}   words: {p['words_a']}   type: {p['page_type_a']}",
        f"B: {p['url_b']}", f"   title: {p.get('title_b', '')}   words: {p['words_b']}   type: {p['page_type_b']}",
        f"signals: near-duplicate {p['dup']:.0%} | containment {p['containment']:.0%} | topic overlap {p['topic']:.0%} "
        f"| title {p['title_sim']:.0%} | same H1: {'YES' if p['same_h1'] else 'no'}",
        f"triggered: {', '.join(p['triggers'])}   (independent signal families: {p['evidence']})",
    ]
    if p.get("short_page"):
        lines.append("  note: a very short page, scores can be noisy")
    if p["page_type_a"] != p["page_type_b"]:
        lines.append("  note: different page types (compare intent before deciding)")
    if p["shared_terms"]:
        lines.append("shared terms: " + "، ".join(p["shared_terms"]))
    for ph in p["shared_phrases"]:
        lines.append(f"shared phrase: {ph}")
    g = p.get("gsc")
    if g:
        def metric(key):
            return "unknown" if g.get(key) is None else f"{g[key]:.0f}"
        lines.append(f"Search Console: clicks A {metric('clicks_a')} / B {metric('clicks_b')}; "
                     f"impressions A {metric('impr_a')} / B {metric('impr_b')}; "
                     f"shared queries: {metric('shared_count')}")
        for q, ia, ib in g.get("shared_top", []):
            lines.append(f"   query: {q}  (A {display_metric(ia)} / B {display_metric(ib)} impressions)")
        lines.append("   (a missing query row is not proof that a page never appeared for it)")
    return "\n".join(lines)


def review_loop(pairs, decisions_path, min_evidence: int = 1, limit: int = 0, input_fn=input, output_fn=print):
    done = load_decisions(decisions_path)
    todo = [p for p in pairs if p["evidence"] >= min_evidence
            and needs_review(p, done.get(pair_key(p["url_a"], p["url_b"])))]
    if limit:
        todo = todo[:limit]
    output_fn(f"{len(todo)} pairs to review ({len(done)} already decided). Nothing is changed on your site.")
    saved = 0
    for n, p in enumerate(todo, 1):
        note = ""
        output_fn(f"\n--- pair {n} of {len(todo)} ---")
        output_fn(_fmt(p))
        while True:
            output_fn(MENU)
            ans = input_fn("your decision: ").strip().lower()
            if ans == "q":
                output_fn(f"Stopped. {saved} decision(s) saved to {decisions_path}.")
                return saved
            if ans == "s":
                break
            if ans == "n":
                note = input_fn("note: ").strip()
                continue
            if ans in CHOICES:
                save_decision(decisions_path, p, CHOICES[ans], note)
                saved += 1
                break
            output_fn("  please choose one of the listed options")
    output_fn(f"Done. {saved} decision(s) saved to {decisions_path}.")
    return saved


def calibrate(pairs, decisions_path, output_fn=print) -> str:
    """Compare the thresholds with YOUR decisions. 'actionable' = anything except ignore."""
    dec = load_decisions(decisions_path)
    rows = []
    for p in pairs:
        d = dec.get(pair_key(p["url_a"], p["url_b"]))
        if d and d.get("content_revisions") == p.get("content_revisions"):
            rows.append((p, d["decision"] != "ignore"))
    lines = [f"Calibration from {len(rows)} decisions you made "
             f"({sum(1 for _, a in rows if a)} actionable, {sum(1 for _, a in rows if not a)} ignored)."]
    if len(rows) < 20 or sum(1 for _, a in rows if not a) < 5 or sum(1 for _, a in rows if a) < 5:
        lines.append("PROVISIONAL: with fewer than 20 decisions, or fewer than 5 of each kind, these numbers are anecdotes, "
                     "not statistics. Keep reviewing before changing any threshold.")
    total_act = sum(1 for _, a in rows if a)
    for key, label in (("dup", "near-duplicate"), ("containment", "containment"), ("topic", "topic overlap"),
                       ("title_sim", "title similarity")):
        lines.append(f"\n{label}: share of flagged pairs you judged actionable, by threshold")
        lines.append("  threshold  flagged  actionable  precision  recall")
        for t in (0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9):
            flagged = [a for p, a in rows if p[key] >= t]
            tp = sum(flagged)
            prec = tp / len(flagged) if flagged else float("nan")
            rec = tp / total_act if total_act else float("nan")
            lines.append(f"  {t:>8.0%}  {len(flagged):>7}  {tp:>10}  {prec:>9.0%}  {rec:>6.0%}")
    lines.append("\nThese metrics apply only to reviewed candidates. Unflagged pairs were not sampled. Choose thresholds by what you can tolerate: higher = fewer pairs to review but more missed duplicates.")
    text = "\n".join(lines)
    output_fn(text)
    return text
