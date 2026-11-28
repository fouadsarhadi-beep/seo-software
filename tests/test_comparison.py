import json
from types import SimpleNamespace

from seo_analysis.analysis.checks import compare_snapshots

ORIGIN = {"scheme": "https", "host": "example.com", "port": 443}


def _run(root, name, *, pages, findings, observed, capped=False):
    """Write a disposable run. A page gets captured markup unless the case withholds it."""
    folder = root / name
    folder.mkdir(parents=True)
    (folder / "crawl_manifest.json").write_text(json.dumps({
        "config": {"status": "partial" if capped else "succeeded", "origin": ORIGIN, "max_pages": 10,
                   "target": "https://example.com/", "kind": "website"},
        "counts": {"observed": observed, "skipped": {"page_limit": 1} if capped else {}}}), encoding="utf-8")
    records = []
    for page in pages:
        record = {"url": page["url"], "final_url": page["url"], "first_status": page.get("status", 200),
                  "final_status": page.get("status", 200), "fetch_state": "ok",
                  "effective_indexability": "indexable", "title": page.get("title", "T"), "meta": "", "h1": "",
                  "canonicals_html": [], "canonicals_header": [], "content_hash": page.get("hash", "h"),
                  "extraction_state": "success", "evidence_id": page["evidence"]}
        if page.get("markup", True):
            record["markup"] = {}
        records.append(json.dumps(record))
    (folder / "snapshot.jsonl").write_text("\n".join(records) + "\n", encoding="utf-8")
    (folder / "findings.json").write_text(
        json.dumps({"schema_version": 1, "findings": findings}), encoding="utf-8")
    return folder


def _compare(tmp_path, before, after):
    out = tmp_path / "out"
    out.mkdir()
    compare_snapshots(SimpleNamespace(directory=out), SimpleNamespace(before=str(before), after=str(after)))
    return json.loads((out / "comparison.json").read_text(encoding="utf-8"))


def _states(report):
    return {row["finding"]["rule"]: row for row in report["findings"]}


def test_an_omitted_page_in_a_capped_follow_up_is_unassessed(tmp_path):
    """The follow-up never reached the page, so its absence proves nothing about the issue."""
    before = _run(tmp_path, "before", pages=[
        {"url": "https://example.com/a", "evidence": "page-000001"},
        {"url": "https://example.com/b", "evidence": "page-000002"},
    ], findings=[{"rule": "seo.missing-title", "category": "review", "detail": "https://example.com/b",
                  "evidence_ids": ["page-000002"], "urls": ["https://example.com/b"]}], observed=2)
    after = _run(tmp_path, "after", pages=[
        {"url": "https://example.com/a", "evidence": "page-000001"},
    ], findings=[], observed=1, capped=True)
    row = _states(_compare(tmp_path, before, after))["seo.missing-title"]
    assert row["state"] == "unassessed"
    assert "not observed" in row["reason"]


def test_a_page_without_captured_markup_cannot_resolve_the_issue(tmp_path):
    """The page was fetched but the evidence that rule needs was not captured."""
    before = _run(tmp_path, "before", pages=[{"url": "https://example.com/b", "evidence": "page-000001"}],
                  findings=[{"rule": "seo.missing-title", "category": "review", "detail": "https://example.com/b",
                             "evidence_ids": ["page-000001"], "urls": ["https://example.com/b"]}], observed=1)
    after = _run(tmp_path, "after", pages=[{"url": "https://example.com/b", "evidence": "page-000001",
                                            "markup": False}], findings=[], observed=1)
    row = _states(_compare(tmp_path, before, after))["seo.missing-title"]
    assert row["state"] == "unassessed"
    assert "evidence" in row["reason"]


def test_a_comparable_clean_follow_up_resolves_the_issue(tmp_path):
    before = _run(tmp_path, "before", pages=[{"url": "https://example.com/b", "evidence": "page-000001"}],
                  findings=[{"rule": "seo.missing-title", "category": "review", "detail": "https://example.com/b",
                             "evidence_ids": ["page-000001"], "urls": ["https://example.com/b"]}], observed=1)
    after = _run(tmp_path, "after", pages=[{"url": "https://example.com/b", "evidence": "page-000001"}],
                 findings=[], observed=1)
    assert _states(_compare(tmp_path, before, after))["seo.missing-title"]["state"] == "resolved"


def test_a_page_unassessed_before_cannot_prove_a_new_problem(tmp_path):
    before = _run(tmp_path, "before", pages=[{"url": "https://example.com/a", "evidence": "page-000001"}],
                  findings=[], observed=1, capped=True)
    after = _run(tmp_path, "after", pages=[
        {"url": "https://example.com/a", "evidence": "page-000001"},
        {"url": "https://example.com/b", "evidence": "page-000002"},
    ], findings=[{"rule": "seo.missing-title", "category": "review", "detail": "https://example.com/b",
                  "evidence_ids": ["page-000002"], "urls": ["https://example.com/b"]}], observed=2)
    assert _states(_compare(tmp_path, before, after))["seo.missing-title"]["state"] == "unassessed"


def test_a_changed_redirect_destination_is_one_changed_issue_not_a_resolution(tmp_path):
    before = _run(tmp_path, "before", pages=[{"url": "https://example.com/old", "evidence": "page-000001"}],
                  findings=[{"rule": "seo.redirect", "category": "warning", "detail": "/old → /first",
                             "evidence_ids": ["page-000001"], "urls": ["https://example.com/old"]}], observed=1)
    after = _run(tmp_path, "after", pages=[{"url": "https://example.com/old", "evidence": "page-000001"}],
                 findings=[{"rule": "seo.redirect", "category": "warning", "detail": "/old → /second",
                            "evidence_ids": ["page-000001"], "urls": ["https://example.com/old"]}], observed=1)
    row = _states(_compare(tmp_path, before, after))["seo.redirect"]
    assert row["state"] == "changed"
    assert row["finding"]["previous_detail"] == "/old → /first"
    assert row["finding"]["detail"] == "/old → /second"


def test_persistent_and_new_findings_still_classify_as_before(tmp_path):
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
    assert {row["url"]: row["state"] for row in report["pages"]}["https://example.com/a"] == "changed"


def test_pages_outside_a_capped_sample_stay_unassessed(tmp_path):
    before = _run(tmp_path, "before", pages=[
        {"url": "https://example.com/a", "evidence": "page-000001"},
        {"url": "https://example.com/b", "evidence": "page-000002"},
    ], findings=[{"rule": "seo.missing-title", "category": "review", "detail": "https://example.com/b",
                  "evidence_ids": ["page-000002"]}], observed=2)
    after = _run(tmp_path, "after", pages=[{"url": "https://example.com/a", "evidence": "page-000001"}],
                 findings=[], observed=1, capped=True)
    report = _compare(tmp_path, before, after)
    assert {row["url"]: row["state"] for row in report["pages"]}["https://example.com/b"] == (
        "unassessed: outside the later sample")
    # A finding without a urls field resolves its pages through evidence, and inherits the verdict.
    assert [row["state"] for row in report["findings"]] == ["unassessed"]