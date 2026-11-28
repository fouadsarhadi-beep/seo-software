import json
from types import SimpleNamespace

from seo_analysis.analysis.checks import compare_snapshots

ORIGIN = {"scheme": "https", "host": "example.com", "port": 443}


def _run(root, name, *, pages, findings, observed, capped=False):
    folder = root / name
    folder.mkdir(parents=True)
    (folder / "crawl_manifest.json").write_text(json.dumps({
        "config": {"status": "partial" if capped else "succeeded", "origin": ORIGIN, "max_pages": 10,
                   "target": "https://example.com/", "kind": "website"},
        "counts": {"observed": observed, "skipped": {"page_limit": 1} if capped else {}}}), encoding="utf-8")
    (folder / "snapshot.jsonl").write_text("\n".join(json.dumps({
        "url": page["url"], "final_url": page["url"], "first_status": page.get("status", 200),
        "final_status": page.get("status", 200), "fetch_state": "ok", "effective_indexability": "indexable",
        "title": page.get("title", "T"), "meta": "", "h1": "", "canonicals_html": [], "canonicals_header": [],
        "content_hash": page.get("hash", "h"), "evidence_id": page["evidence"],
    }) for page in pages) + "\n", encoding="utf-8")
    (folder / "findings.json").write_text(
        json.dumps({"schema_version": 1, "findings": findings}), encoding="utf-8")
    return folder


def _compare(tmp_path, before, after):
    out = tmp_path / "out"
    out.mkdir()
    compare_snapshots(SimpleNamespace(directory=out), SimpleNamespace(before=str(before), after=str(after)))
    return json.loads((out / "comparison.json").read_text(encoding="utf-8"))


def test_comparison_classifies_new_persistent_and_resolved_findings(tmp_path):
    before = _run(tmp_path, "before", pages=[
        {"url": "https://example.com/a", "status": 404, "evidence": "page-000001"},
        {"url": "https://example.com/b", "evidence": "page-000002"},
    ], findings=[
        {"rule": "crawl.client_error", "category": "error", "detail": "https://example.com/a (404)",
         "evidence_ids": ["page-000001"], "urls": ["https://example.com/a"]},
        {"rule": "seo.missing-title", "category": "review", "detail": "https://example.com/b",
         "evidence_ids": ["page-000002"], "urls": ["https://example.com/b"]},
    ], observed=2)
    after = _run(tmp_path, "after", pages=[
        {"url": "https://example.com/a", "evidence": "page-000001"},
        {"url": "https://example.com/b", "evidence": "page-000002"},
    ], findings=[
        {"rule": "seo.missing-title", "category": "review", "detail": "https://example.com/b",
         "evidence_ids": ["page-000002"], "urls": ["https://example.com/b"]},
        {"rule": "seo.missing-meta", "category": "review", "detail": "https://example.com/b",
         "evidence_ids": ["page-000002"], "urls": ["https://example.com/b"]},
    ], observed=2)
    report = _compare(tmp_path, before, after)
    states = {row["finding"]["rule"]: row["state"] for row in report["findings"]}
    assert states == {"crawl.client_error": "resolved", "seo.missing-title": "persistent",
                      "seo.missing-meta": "new"}
    pages = {row["url"]: row["state"] for row in report["pages"]}
    assert pages["https://example.com/a"] == "changed"


def test_comparison_marks_a_page_outside_a_capped_sample_as_unassessed(tmp_path):
    before = _run(tmp_path, "before", pages=[
        {"url": "https://example.com/a", "evidence": "page-000001"},
        {"url": "https://example.com/b", "evidence": "page-000002"},
    ], findings=[{"rule": "seo.missing-title", "category": "review", "detail": "https://example.com/b",
                  "evidence_ids": ["page-000002"]}], observed=2)
    after = _run(tmp_path, "after", pages=[
        {"url": "https://example.com/a", "evidence": "page-000001"},
    ], findings=[], observed=1, capped=True)
    report = _compare(tmp_path, before, after)
    pages = {row["url"]: row["state"] for row in report["pages"]}
    assert pages["https://example.com/b"] == "unassessed: outside the later sample"
    # A finding without a urls field still participates, resolved through its page evidence.
    assert [row["state"] for row in report["findings"]] == ["resolved"]