"""Compose the bounded crawl, offline checks and evidence-backed report."""
import json
from pathlib import Path

from seo_analysis.analysis import canon
from seo_analysis.analysis.analyze import load_snapshot, run_analyze
from seo_analysis.core.artifacts import write_json
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
    return len(findings)


def run_audit(cfg, log=print, prompt=None):
    result = run_crawl(cfg, log=log, input_fn=prompt)
    directory = Path(cfg.out_dir)
    if result["status"] != "cancelled":
        analysis = run_analyze(directory, log=log)
        result["counts"].update(analysis["counts"])
        result["counts"]["findings"] = report_findings(directory)
    return result
