import json
from pathlib import Path

from seo_analysis.ui.audit_read import load_audit, query_pages

SITE = "https://example.org/"


def _record(url, *, status=200, indexability="indexable", evidence="", chain=None, final_url=None):
    return {"url": url, "final_url": final_url or url, "first_status": status, "final_status": status,
            "chain": chain or [], "effective_indexability": indexability,
            "indexability_reason": "no noindex or none directive for Googlebot" if indexability == "indexable" else "",
            "title": f"Title {url}", "words": 12, "evidence_id": evidence, "depth": 0}


def _write(tmp_path, pages, findings=()):
    (tmp_path / "snapshot.jsonl").write_text(
        "\n".join(json.dumps(page) for page in pages) + "\n", encoding="utf-8")
    (tmp_path / "findings.json").write_text(json.dumps({"schema_version": 1, "findings": list(findings)}),
                                            encoding="utf-8")
    return load_audit(tmp_path, {"parameters": {"source": SITE}})


def test_read_model_joins_findings_and_keeps_url_identity(tmp_path):
    audit = _write(
        tmp_path,
        [_record(SITE + "a", evidence="page-000001"),
         _record(SITE + "b", status=404, evidence="page-000002"),
         _record(SITE + "c", indexability="noindex", evidence="page-000003")],
        [{"rule": "seo.missing-title", "category": "seo", "detail": "Missing title",
          "evidence_ids": ["page-000001"]},
         {"rule": "content.overlap", "category": "content", "detail": "Same H1",
          "evidence_ids": ["page-000001", "page-000002"]}],
    )
    assert audit.site == SITE
    assert [page.url for page in audit.pages] == [SITE + "a", SITE + "b", SITE + "c"]
    assert audit.pages[1].status_text == "404"
    assert audit.pages[2].indexability_text == "noindex"
    assert audit.evidence["page-000002"].url == SITE + "b"
    assert audit.pages[0].rules == ["seo.missing-title", "content.overlap"]
    assert audit.pages[2].rules == []


def test_rule_summary_separates_occurrences_from_affected_urls(tmp_path):
    audit = _write(
        tmp_path,
        [_record(SITE + "a", evidence="page-000001"), _record(SITE + "b", evidence="page-000002")],
        [{"rule": "content.overlap", "category": "content", "detail": "Same H1",
          "evidence_ids": ["page-000001", "page-000002"]},
         {"rule": "seo.missing-title", "category": "seo", "detail": "Missing title",
          "evidence_ids": ["page-000001"]}],
    )
    summary = {row["rule"]: row for row in audit.rules()}
    assert summary["content.overlap"]["occurrences"] == 1
    assert summary["content.overlap"]["urls"] == 2
    assert summary["seo.missing-title"]["urls"] == 1
    assert audit.rules()[0]["rule"] == "content.overlap"


def test_read_model_tolerates_missing_and_legacy_artifacts(tmp_path):
    (tmp_path / "snapshot.jsonl").write_text(
        json.dumps({"url": SITE + "a"}) + "\n"
        + json.dumps({"url": SITE + "b", "final_status": 0, "effective_indexability": "not_indexable_status",
                      "indexability_reason": "HTTP status 0"}) + "\n", encoding="utf-8")
    audit = load_audit(tmp_path, {"parameters": {"sitemap": SITE}})
    page = audit.pages[0]
    assert audit.site == SITE
    assert page.status is None and page.status_text == "Unknown"
    assert page.indexability_text == "unknown" and page.words is None
    blocked = audit.pages[1]
    assert blocked.status is None and blocked.status_text == "Unknown"
    assert blocked.indexability_text == "not_indexable_status"
    assert audit.findings == []


def test_redirect_detection_ignores_encoding_only_differences(tmp_path):
    encoded = SITE + "%D8%A2/x"
    audit = _write(tmp_path, [{
        "url": encoded, "final_url": SITE + "آ/x", "first_status": 301, "final_status": 200,
        "chain": [[encoded, 301], [SITE + "آ/x", 200]], "effective_indexability": "indexable",
        "indexability_reason": "", "title": "", "words": 1, "evidence_id": "page-000001", "depth": 0,
    }])
    assert audit.pages[0].redirect_count == 1
    assert audit.pages[0].redirect_to == ""


def test_page_query_combines_filters_and_matches_decoded_text(tmp_path):
    audit = _write(tmp_path, [
        _record(SITE + "%D8%A2/test", evidence="page-000001"),
        _record(SITE + "gone", status=404, evidence="page-000002"),
        _record(SITE + "old", status=301, chain=[SITE + "old", SITE + "new"], final_url=SITE + "new",
                evidence="page-000003"),
        _record(SITE + "hidden", indexability="noindex", evidence="page-000004"),
    ], [{"rule": "seo.missing-title", "category": "seo", "detail": "Missing title",
         "evidence_ids": ["page-000002"]}])

    assert query_pages(audit.pages, url="آ").matched == 1
    assert query_pages(audit.pages, status="4xx").matched == 1
    assert query_pages(audit.pages, status="error").matched == 1
    assert query_pages(audit.pages, redirect="any").matched == 1
    assert query_pages(audit.pages, redirect="none").matched == 3
    assert query_pages(audit.pages, indexability="noindex").matched == 1
    assert query_pages(audit.pages, indexability="unknown").matched == 0
    assert query_pages(audit.pages, rule="seo.missing-title").matched == 1
    combined = query_pages(audit.pages, status="4xx", rule="seo.missing-title")
    assert combined.matched == 1 and combined.active
    assert combined.href(2) == "?status=4xx&rule=seo.missing-title&page=2"
    assert query_pages(audit.pages).href(1) == "?"


def test_page_query_paginates_clamps_and_sorts_stably(tmp_path):
    pages = [_record(f"{SITE}p{index:03d}", status=404 if index % 2 else 200,
                     evidence=f"page-{index:06d}") for index in range(35)]
    audit = _write(tmp_path, pages)
    first = query_pages(audit.pages)
    assert (first.total, first.matched, first.page_count, first.first, first.last) == (35, 35, 2, 1, 30)
    assert len(first.rows) == 30
    second = query_pages(audit.pages, page=2)
    assert len(second.rows) == 5 and (second.first, second.last) == (31, 35)
    clamped = query_pages(audit.pages, page=99)
    assert clamped.page == 2 and len(clamped.rows) == 5
    empty = query_pages(audit.pages, url="nothing-matches")
    assert (empty.matched, empty.page, empty.first, empty.last) == (0, 1, 0, 0)
    by_status = query_pages(audit.pages, status="4xx")
    assert [page.status for page in by_status.rows] == [404] * len(by_status.rows)
    assert [page.url for page in query_pages(audit.pages).rows][:3] == [SITE + "p000", SITE + "p001", SITE + "p002"]