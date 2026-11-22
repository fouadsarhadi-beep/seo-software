import asyncio
import json
import sys
from pathlib import Path

from openpyxl import load_workbook
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from seo_analysis.app.operations import ExportInput, ResearchInput, SiteQAInput, WorkbookInput
from seo_analysis.app.runner import ToolRunner
from seo_analysis.core import tools
from seo_analysis.core.workspace import Workspace
from seo_analysis.web.crawl import CrawlConfig


def test_local_exports_reporting_research_and_mcp(site, tmp_path):
    ws = Workspace(tmp_path / "config", tmp_path / "data", tmp_path / "exports")
    runner = ToolRunner(ws)
    site.add("/map", f"<urlset><url><loc>{site.base}/page</loc></url></urlset>")
    site.add("/page", "<html><title>Landing</title><main>صفحه</main></html>")
    audit = runner.run(tools.AUDIT, CrawlConfig(site.base + "/map", "", allow_local=True, delay=0))

    def ingest(kind, contents, ext="csv", observed="2026-01-01"):
        file = tmp_path / (kind + "." + ext)
        file.write_text(contents, encoding="utf-8-sig")
        result = runner.run(
            tools.IMPORT, ExportInput(str(file), kind, "fixture", observed, "fa-IR", "desktop")
        )
        assert result.status == "succeeded", result.warnings
        return result.out_dir

    serp = ingest(
        "serp",
        "Keyword,Position,URL\nنرم افزار,1,https://other.test/a\nنرم افزار,2,https://mine.test/b\nبرنامه,1,https://other.test/a",
    )
    feed = ingest(
        "community",
        "<rss><channel><item><title>Which tool?</title><link>https://other.test/topic</link></item></channel></rss>",
        "rss",
    )
    gsc = ingest("gsc", "Page,Clicks,Impressions\n" + site.base + "/page,0,15")
    ga4 = ingest(
        "ga4", "# GA4 landing page report\n# Property: Fixture\n\nLanding page,Sessions\n/page,4\n/missing,2"
    )
    later = ingest("serp", "Query,Rank,URL\nنرم افزار,1,https://mine.test/b", observed="2026-01-02")
    result = runner.run(tools.RESEARCH, ResearchInput((serp, feed, later), "mine.test"))
    report = json.loads((Path(result.out_dir) / "research.json").read_text(encoding="utf-8"))
    assert report["competitors"][0]["shared_with_owned"] == 1
    assert report["serp_overlap"][0]["shared_urls"] == ["https://other.test/a"]
    series = next(s for s in report["rank_history"] if s["host"] == "mine.test")
    assert series["samples"][1]["positions_gained"] == 1
    assert report["brief_candidates"][0]["query"] == "برنامه"
    assert report["questions"][0]["evidence"]["row"] == 1
    wb = runner.run(tools.WORKBOOK, WorkbookInput(audit.out_dir, (gsc, ga4)))
    assert wb.counts["matches"] == {"requested": 2, "unmatched": 1}
    book = load_workbook(Path(wb.out_dir) / "report.xlsx", read_only=True)
    assert book.sheetnames == ["Crawl", "GSC 1", "GA4 2", "Sources"]
    book.close()
    ws.config_file.write_text('[paths]\ndata_dir="data"\nexport_dir="exports"\n')

    async def verify():
        params = StdioServerParameters(
            command=sys.executable,
            args=[
                "-m",
                "seo_analysis",
                "--config-file",
                str(ws.config_file),
                "mcp",
                "--allow-run",
                audit.run_id,
            ],
        )
        async with stdio_client(params) as (reader, writer), ClientSession(reader, writer) as session:
            await session.initialize()
            assert "page_evidence" in {t.name for t in (await session.list_tools()).tools}
            response = await session.call_tool(
                "page_evidence", {"run_id": audit.run_id, "evidence_id": "page-000001"}
            )
            assert not response.isError and json.loads(response.content[0].text)["title"] == "Landing"
            denied = await session.call_tool("run_summary", {"run_id": wb.run_id})
            assert denied.isError
            checked = await session.call_tool(
                "check_snapshot", {"run_id": audit.run_id, "check": "technical"}
            )
            assert not checked.isError
            derived = json.loads(checked.content[0].text)["run_id"]
            assert not (await session.call_tool("read_observations", {"run_id": derived})).isError

    asyncio.run(verify())


def test_build_inspection(tmp_path):
    root = tmp_path / "site"
    root.mkdir()
    (root / "index.html").write_text('<main>Hello</main><img src="absent.png">')
    ws = Workspace(tmp_path / "config", tmp_path / "data", tmp_path / "exports")
    access_log = tmp_path / "access.log"
    access_log.write_text(
        '192.0.2.1 - - [21/Nov/2026:12:00:00 +0000] "GET /absent.png?x=personal HTTP/1.1" 404 0\n'
    )
    lighthouse = tmp_path / "lighthouse.json"
    lighthouse.write_text(json.dumps({"categories": {"performance": {"score": 0.9}}}))
    axe = tmp_path / "axe.json"
    axe.write_text(json.dumps({"violations": [{"id": "image-alt", "nodes": [{}]}]}))
    result = ToolRunner(ws).run(
        tools.SITE_QA, SiteQAInput(str(root), str(lighthouse), str(axe), str(access_log))
    )
    data = json.loads((Path(result.out_dir) / "site-qa.json").read_text(encoding="utf-8"))
    reports = data["imported_reports"]
    assert reports["lighthouse"]["lab_scores"] == {"performance": 0.9}
    assert reports["axe"]["violations"][0]["nodes"] == 1
    assert reports["access_log"]["observations"] == [{"path": "/absent.png", "status": 404, "requests": 1}]
    assert any(r[1] == "missing build asset" for r in data["findings"])


def test_visual_diff_and_query_only_workbook(site, tmp_path):
    from PIL import Image
    from openpyxl import Workbook

    ws = Workspace(tmp_path / "config", tmp_path / "data", tmp_path / "exports")
    runner = ToolRunner(ws)
    build = tmp_path / "build"
    build.mkdir()
    (build / "index.html").write_text("<title>Example</title>")
    first, second = tmp_path / "baseline.png", tmp_path / "current.png"
    img = Image.new("RGB", (4, 4))
    img.save(first)
    img.putpixel((2, 1), (1, 0, 0))
    img.save(second)
    qa = runner.run(tools.SITE_QA, SiteQAInput(str(build), baseline=str(first), screenshot=str(second)))
    info = json.loads((Path(qa.out_dir) / "site-qa.json").read_text(encoding="utf-8"))["imported_reports"][
        "visual_comparison"
    ]
    assert (info["changed_pixels"], info["bounding_box"]) == (1, [2, 1, 3, 2])
    assert (Path(qa.out_dir) / "changed-pixels.png").exists()
    path = tmp_path / "performance.xlsx"
    book = Workbook()
    book.active.append(["Top queries", "Clicks", "Impressions"])
    book.active.append(["SEO software", 0, 20])
    book.save(path)
    dataset = runner.run(tools.IMPORT, ExportInput(str(path), "gsc", "GSC", "2026-01-01"))
    site.add("/map", f"<urlset><url><loc>{site.base}/</loc></url></urlset>")
    site.add("/", "<html>Hello</html>")
    audit = runner.run(tools.AUDIT, CrawlConfig(site.base + "/map", "", allow_local=True, delay=0))
    workbook = runner.run(tools.WORKBOOK, WorkbookInput(audit.out_dir, (dataset.out_dir,)))
    assert workbook.counts["matches"] == {"unattributed query": 1}
