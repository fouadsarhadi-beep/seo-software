import json
from pathlib import Path

from seo_analysis.cli import main


def _workspace(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text('[paths]\ndata_dir="data"\n', encoding="utf-8")
    return ["--config-file", str(config)]


def _import(prefix, tmp_path, capsys, name, kind, content, *extra):
    path = tmp_path / f"{name}.csv"
    path.write_text(content, encoding="utf-8")
    assert main([*prefix, "import-data", str(path), "--kind", kind, "--provider", "Fixture",
                 *extra, "--json"]) == 0
    return json.loads(capsys.readouterr().out)["run_id"]


def test_research_cli_builds_contextual_clusters_briefs_and_refresh_candidates(tmp_path, capsys):
    prefix = _workspace(tmp_path)
    serp = _import(prefix, tmp_path, capsys, "serp", "serp",
                   "Query,URL,Position\nنرم افزار,https://other.test/one,1\n"
                   "نرم افزار,https://other.test/two,2\nابزار نرم افزار,https://other.test/one,1\n"
                   "ابزار نرم افزار,https://other.test/two,2\n", "--observed", "2026-11-15", "--locale", "fa-IR")
    old = _import(prefix, tmp_path, capsys, "old", "gsc",
                  "Query,Page,Clicks,Impressions\nواژه,https://mine.test/a,4,20\n"
                  "مبهم,https://mine.test/b,5,30\nمبهم,https://mine.test/b,4,10\n",
                  "--observed", "2026-11-07", "--period-start", "2026-11-01")
    new = _import(prefix, tmp_path, capsys, "new", "gsc",
                  "Query,Page,Clicks,Impressions\nواژه,https://mine.test/a,0,\n"
                  "مبهم,https://mine.test/b,0,0\n",
                  "--observed", "2026-11-14", "--period-start", "2026-11-08")
    assert main([*prefix, "research", "--owned-host", "mine.test", "--dataset", serp,
                 "--dataset", old, "--dataset", new, "--json"]) == 0
    run = json.loads(capsys.readouterr().out)
    path = Path(run["out_dir"])
    plan = json.loads((path / "content-plan.json").read_text(encoding="utf-8"))
    cluster, = plan["keyword_clusters"]
    assert cluster["queries"] == ["ابزار نرم افزار", "نرم افزار"]
    assert cluster["context"] == ["Fixture", "2026-11-15", "fa-IR", ""]
    brief = next(item for item in plan["content_briefs"] if item["query"] == "نرم افزار")
    assert brief["reference_pages"][0]["evidence"] == {"run_id": serp, "row": 1}
    assert brief["related_queries"][0]["queries"] == ["ابزار نرم افزار"]
    refresh, = plan["refresh_candidates"]
    assert refresh["declines"] == {"clicks": {"before": 4, "after": 0, "change": -4}}
    assert refresh["evidence"] == [{"run_id": old, "row": 1}, {"run_id": new, "row": 1}]
    assert run["data_egress"] == []


def test_research_compares_saved_pages_only_with_matching_serp_context(site, tmp_path, capsys):
    prefix = _workspace(tmp_path)
    own = site.base
    other = own.replace("127.0.0.1", "localhost")
    site.add("/robots.txt", "User-agent: *\nAllow: /")
    site.add("/mine-map", f"<urlset><url><loc>{own}/mine</loc></url></urlset>")
    site.add("/other-map", f"<urlset><url><loc>{other}/other</loc></url></urlset>")
    site.add("/mine", "<title>Own page</title><article><h1>Own heading</h1>Owned content</article>")
    site.add("/other", "<title>Other page</title><article><h1>Other heading</h1>Competitor content</article>")
    crawls = []
    for sitemap in (own + "/mine-map", other + "/other-map"):
        assert main([*prefix, "audit", "--sitemap", sitemap, "--allow-local", "--delay", "0", "--json"]) == 0
        crawls.append(json.loads(capsys.readouterr().out)["run_id"])

    sample = _import(prefix, tmp_path, capsys, "sample", "serp",
                     f"Query,URL,Position\nexample,{own}/mine,3\nexample,{other}/other,1\n",
                     "--observed", "2026-11-15")
    assert main([*prefix, "research", "--owned-host", "127.0.0.1", "--dataset", sample,
                 "--owned-crawl", crawls[0], "--competitor-crawl", crawls[1], "--json"]) == 0
    run = json.loads(capsys.readouterr().out)
    plan = json.loads((Path(run["out_dir"]) / "content-plan.json").read_text(encoding="utf-8"))
    row, = plan["page_comparisons"]
    assert row["owned"]["title"] == "Own page" and row["owned"]["rank"] == 3
    assert row["competitor"]["crawl_evidence"]["run_id"] == crawls[1]
    assert row["competitor"]["serp_evidence"] == {"run_id": sample, "row": 2}
