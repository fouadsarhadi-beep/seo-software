import json
from pathlib import Path

from seo_analysis.app.agent import run_snapshot_tool
from seo_analysis.app.runner import ToolRunner
from seo_analysis.core import tools
from seo_analysis.core.workspace import Workspace
from seo_analysis.web.crawl import CrawlConfig


def test_checks_compare_and_old_snapshot_coverage(site, tmp_path):
    ws = Workspace(tmp_path / "config", tmp_path / "data", tmp_path / "exports")
    site.add("/map", f"<urlset><url><loc>{site.base}/one</loc></url><url><loc>{site.base}/gone</loc></url></urlset>")
    site.add("/one", """<html><title>First</title><main>Content</main><a href="/gone">Link</a>
             <link rel="alternate" hreflang="fa" href="/one"><img src="/image.png">
             <script type="application/ld+json">{"@type":"Article"}</script></html>""")
    cfg = CrawlConfig(site.base + "/map", "", allow_local=True, delay=0)
    runner = ToolRunner(ws)
    first = runner.run(tools.AUDIT, cfg)
    hits = dict(site.hits)
    result = run_snapshot_tool(ws, tools.CHECK.id, first.run_id)
    rows = json.loads((Path(result.out_dir) / "checks.json").read_text(encoding="utf-8"))["observations"]
    assert {r["check"] for r in rows} == {"technical", "sitemap", "links", "broken-links", "canonicals", "schema", "hreflang", "assets"}
    assert any(r["value"] == "Article" for r in rows)
    assert site.hits == hits
    site.add("/one", "<html><title>Second</title></html>")
    second = runner.run(tools.AUDIT, cfg)
    diff = run_snapshot_tool(ws, tools.COMPARE.id, second.run_id, previous=first.run_id)
    assert diff.counts["changed"] == 1
    source = Path(first.out_dir)/"snapshot.jsonl"
    original = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines()]
    for page in original:
        page.pop("markup",None)
    source.write_text("\n".join(json.dumps(p) for p in original) + "\n")
    legacy = run_snapshot_tool(ws, tools.CHECK.id, first.run_id, check="assets")
    assert legacy.status == "partial" and "markup unavailable" in legacy.warnings[0]
