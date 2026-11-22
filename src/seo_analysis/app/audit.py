"""Compose the bounded crawl, offline checks and evidence-backed report."""
import json
from pathlib import Path

from seo_analysis.analysis import canon
from seo_analysis.analysis.analyze import load_snapshot, run_analyze
from seo_analysis.core.artifacts import write_json, write_text
from seo_analysis.reporting.report import write_csv
from seo_analysis.web.crawl import run_crawl


def report_findings(directory):
    pages = load_snapshot(directory / "snapshot.jsonl")
    canonical = canon.analyze(pages)
    findings = []

    def add(category, rule, detail, *ids):
        findings.append(dict(category=category, rule=rule, detail=detail, evidence_ids=list(ids)))

    evidence = {}
    for page in pages:
        url, eid = page["url"], page["evidence_id"]
        evidence[url] = eid
        state = page["fetch_state"]
        if not state.startswith("ok"):
            category = "error" if state in ("server_error", "client_error", "fetch_error") else "warning"
            add(category, "crawl." + state, f"{url} ({page['final_status'] or state})", eid)
            continue
        if page["extraction_state"] in ("fallback", "empty", "truncated"):
            add("warning", "content.extraction", page["extraction_state"], eid)
        if state == "ok_truncated":
            continue
        if page["first_status"] in (301, 302, 303, 307, 308):
            add("warning", "seo.redirect", f"{url} → {page['final_url']}", eid)
        if page["h1_count"] > 1:
            add("review", "seo.multiple-h1", url, eid)
        if page["effective_indexability"] == "noindex":
            add("warning", "seo.noindex", page["indexability_reason"], eid)
        for key in ("title", "meta", "h1"):
            if not page[key]:
                add("review", "seo.missing-" + key, url, eid)
        if canonical[url]["issues"]:
            add("warning", "seo.canonical", canonical[url]["issues"], eid)
    for pair in json.loads((directory / "pairs.json").read_text(encoding="utf-8")):
        add("review", "content.overlap", ", ".join(pair["triggers"]),
            evidence[pair["url_a"]], evidence[pair["url_b"]])
    write_json(directory / "findings.json", {"schema_version": 1, "findings": findings})
    write_csv(directory / "findings.csv", ["Category", "Rule", "Detail", "Evidence IDs"],
              ([f["category"], f["rule"], f["detail"], " ".join(f["evidence_ids"])] for f in findings))
    return findings


def run_audit(cfg, log=print, prompt=None, *, cancel=None):
    result = run_crawl(cfg, log=log, input_fn=prompt, cancel=cancel)
    directory = Path(cfg.out_dir)
    if result["status"] != "cancelled":
        if cancel is not None and cancel.is_set():
            raise KeyboardInterrupt()
        log("Preparing audit report…")
        analysis = run_analyze(directory, log=lambda message: None)
        result["counts"].update(analysis["counts"])
        findings = report_findings(directory)
        result["counts"]["findings"] = len(findings)
        lines = [f"Audit {result['status']} | {result['counts']['observed']} observed pages"]
        for category in ("error", "warning", "review"):
            group = [f for f in findings if f["category"] == category]
            lines.append(f"{category.upper()} ({len(group)})")
            lines.extend(f"  {f['rule']} [{', '.join(f['evidence_ids'])}] {f['detail']}" for f in group)
        lines.append("Content overlap is a review candidate. Coverage reflects the HTML received.")
        write_text(directory / "issues.txt", "\n".join(lines) + "\n")
        for line in lines[:20]:
            log(line)
        if len(lines) > 20:
            log(f"Full findings: {directory / 'issues.txt'}")
    return result
