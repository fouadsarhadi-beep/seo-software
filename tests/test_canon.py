from seo_analysis.analysis import canon

B = "https://s.ir"


def rec(path, canonicals=(), status=200, noindex=False, header=()):
    u = f"{B}{path}"
    return {"url": u, "final_url": u, "final_status": status, "canonicals_html": [f"{B}{c}" if c.startswith("/") else c for c in canonicals],
            "canonicals_header": list(header), "effective_indexability": "noindex" if noindex else "indexable"}


def run(*records):
    return canon.analyze(list(records))


def test_self_missing_and_encoding_difference():
    out = run(rec("/a/", ["/a/"]), rec("/b/"),
              {"url": f"{B}/%d8%a7/", "final_url": f"{B}/%d8%a7/", "final_status": 200,
               "canonicals_html": [f"{B}/%D8%A7/"], "canonicals_header": [], "effective_indexability": "indexable"})
    assert out[f"{B}/a/"]["relationship"] == "self" and out[f"{B}/a/"]["issues"] == ""
    assert out[f"{B}/b/"]["relationship"] == "missing" and out[f"{B}/b/"]["issues"] == ""
    assert out[f"{B}/%d8%a7/"]["relationship"].startswith("self (written differently")


def test_points_to_another_crawled_page_and_counts():
    out = run(rec("/a/", ["/a/"]), rec("/b/", ["/a/"]), rec("/c/", ["/a/"]))
    assert out[f"{B}/b/"]["relationship"] == "points to another page"
    assert out[f"{B}/b/"]["target_status"] == "200" and out[f"{B}/b/"]["issues"] == ""
    assert out[f"{B}/a/"]["pointing_here"] == 2


def test_chain_loop_missing_broken_noindex_conflict():
    out = run(rec("/a/", ["/b/"]), rec("/b/", ["/c/"]), rec("/c/", ["/c/"]),
              rec("/x/", ["/y/"]), rec("/y/", ["/x/"]),
              rec("/m/", ["/nowhere/"]), rec("/n/", ["/gone/"]), rec("/gone/", ["/gone/"], status=404),
              rec("/p/", ["/q/"]), rec("/q/", ["/q/"], noindex=True),
              rec("/k/", ["/k1/", "/k2/"]),
              rec("/t/", ["/t"]))
    assert "chain" in out[f"{B}/a/"]["issues"]
    assert "loop" in out[f"{B}/x/"]["issues"]
    assert "not in the crawl" in out[f"{B}/m/"]["issues"] and out[f"{B}/m/"]["target_status"] == "not in crawl"
    assert "HTTP 404" in out[f"{B}/n/"]["issues"]
    assert "noindex" in out[f"{B}/p/"]["issues"]
    assert out[f"{B}/k/"]["relationship"] == "conflicting canonicals"
    assert out[f"{B}/t/"]["relationship"].startswith("variant of itself") and "trailing slash" in out[f"{B}/t/"]["issues"]


def test_link_header_canonical_parsed_and_disagreement_flagged():
    hdr = canon.header_canonicals(['<https://s.ir/a/>; rel="canonical", <https://s.ir/en/>; rel="alternate"'], B)
    assert hdr == ["https://s.ir/a/"]
    out = run(rec("/a/", ["/a/"]), rec("/b/", ["/a/"], header=["https://s.ir/c/"]))
    assert out[f"{B}/b/"]["relationship"] == "conflicting canonicals"
