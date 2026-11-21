import pytest

from seo_analysis.analysis import analyze
from seo_analysis.web import crawl
from test_cli_e2e import build

hazm = pytest.importorskip("hazm")


def test_hazm_normalizer_and_stemmer_are_optional_extras(site, tmp_path):
    b = build(site)
    out = tmp_path / "h"
    crawl.run_crawl(crawl.CrawlConfig(sitemap=b + "/sitemap_index.xml", out_dir=str(out), delay=0, retries=0), log=lambda *_: None)
    r = analyze.run_analyze(out, normalizer="hazm", stem=True, log=lambda *_: None)
    assert r["counts"]["pairs_flagged"] >= 1
    import json
    m = json.loads((out / "analysis_manifest.json").read_text(encoding="utf-8"))
    assert m["config"]["normalizer"] == "hazm" and m["config"]["stem"] is True
