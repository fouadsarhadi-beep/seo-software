import csv
import json

import pytest

from seo_analysis.analysis import analyze
from seo_analysis import cli
from seo_analysis.web import crawl
from seo_analysis.web.crawl import INVENTORY_HEADER
from seo_analysis.analysis.analyze import PAIR_HEADER
from test_similarity import PA, PB, PC, PD, PE

NS = 'xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:image="http://www.google.com/schemas/sitemap-image/1.1"'
ORIGINAL_INVENTORY = ["URL", "Title", "H1", "Meta description", "Words", "Declared canonical", "HTTP status", "Robots meta", "Redirected to"]
ORIGINAL_PAIRS = ["URL A", "URL B", "Title similarity", "Near-duplicate score", "Topic overlap score", "Same H1"]


def page(title, h1, body, head=""):
    return (f'<!doctype html><html lang="fa"><head><meta charset="utf-8"><title>{title}</title>'
            f'<meta name="description" content="توضیح {h1}">{head}</head><body><nav>منو</nav>'
            f'<main><h1>{h1}</h1><p>{body}</p></main><footer>پایین</footer></body></html>')


def build(site):
    b = site.base
    site.add("/robots.txt", "User-agent: *\nDisallow: /private/\n", ctype="text/plain")
    site.add("/sitemap_index.xml", f'<sitemapindex {NS}><sitemap><loc>{b}/post-sitemap.xml</loc></sitemap><sitemap><loc>{b}/author-sitemap.xml</loc></sitemap></sitemapindex>', ctype="application/xml")
    urls = ["/p1/", "/p2/", "/p3/", "/p4/", "/old/", "/gone/", "/private/x/", "/noidx/", "/%d8%a7%d8%aa%d9%88/", "/evil/"]
    entries = "".join(f"<url><loc>{b}{u}</loc></url>" for u in urls)
    entries = entries.replace(f"<loc>{b}/p1/</loc>", f"<loc>{b}/p1/</loc><image:image><image:loc>{b}/a.jpg</image:loc></image:image>")
    site.add("/post-sitemap.xml", f"<urlset {NS}>{entries}</urlset>", ctype="application/xml")
    site.add("/author-sitemap.xml", f"<urlset {NS}><url><loc>{b}/author/x/</loc></url></urlset>", ctype="application/xml")
    site.add("/p1/", page("اتوماسیون اداری چیست؟ | سماتوس", "اتوماسیون اداری چیست؟", PA * 2, f'<link rel="canonical" href="{b}/p1/">'))
    site.add("/p2/", page("اتوماسیون اداری چیست و چه مزایایی دارد؟ | سماتوس", "مزایای اتوماسیون اداری", PA * 2 + PC, f'<link rel="canonical" href="{b}/p2/">'))
    site.add("/p3/", page("مدیریت ارتباط با مشتری | سماتوس", "سی آر ام", PB + PD + PE, f'<link rel="canonical" href="{b}/p3/">'))
    site.add("/p4/", page("نسخه چاپی | سماتوس", "اتوماسیون اداری چیست؟", PA * 2, f'<link rel="canonical" href="{b}/p1/">'))
    site.redirect("/old/", b + "/new/")
    site.add("/new/", page("صفحه جدید | سماتوس", "صفحه جدید", PD + PE, f'<link rel="canonical" href="{b}/new/">'))
    site.add("/gone/", "missing", status=404)
    site.add("/private/x/", page("خصوصی", "خصوصی", "راز"))
    site.add("/noidx/", page("بدون ایندکس | سماتوس", "بدون ایندکس", PC + PD, ""), headers=[("X-Robots-Tag", "noindex")])
    site.add("/اتو/", page("اتو | سماتوس", "اتو", PE + PB, '<link rel="canonical" href="' + b + '/%D8%A7%D8%AA%D9%88/">'))
    site.add("/evil/", page('=HYPERLINK("http://x")', "عنوان خطرناک", PD, f'<link rel="canonical" href="{b}/evil/">'))
    return b


def rows(path):
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh)), next(csv.reader(open(path, encoding="utf-8-sig", newline="")))


@pytest.fixture
def crawled(site, tmp_path):
    b = build(site)
    cfg = crawl.CrawlConfig(allow_local=True, sitemap=b + "/sitemap_index.xml", out_dir=str(tmp_path), delay=0, retries=0, skip_sitemap=r"author")
    crawl.run_crawl(cfg, log=lambda *_: None)
    return site, tmp_path


def test_crawl_inventory_is_correct_and_compatible(crawled):
    site, out = crawled
    data, header = rows(out / "inventory.csv")
    assert header[:9] == ORIGINAL_INVENTORY and header == INVENTORY_HEADER
    by = {r["URL"].replace(site.base, ""): r for r in data}
    assert len(data) == 10                                                     # image URL and author sitemap not crawled
    assert site.hits["/a.jpg"] == 0 and site.hits["/author-sitemap.xml"] == 0 and site.hits["/private/x/"] == 0
    old = by["/old/"]
    assert (old["HTTP status"], old["First HTTP status"], old["Redirect count"]) == ("200", "301", "1")
    assert old["Redirected to"].endswith("/new/") and old["Fetch state"] == "ok_after_redirect"
    assert by["/gone/"]["HTTP status"] == "404" and by["/gone/"]["Fetch state"] == "client_error"
    assert by["/private/x/"]["HTTP status"] == "ROBOTS_DISALLOWED" and by["/private/x/"]["Effective indexability"] == "unknown"
    assert by["/noidx/"]["Effective indexability"] == "noindex" and "X-Robots-Tag" in by["/noidx/"]["Indexability reason"]
    assert by["/p4/"]["Canonical relationship"] == "points to another page" and by["/p1/"]["Pages pointing here"] == "1"
    persian = [r for r in data if "%d8%a7%d8%aa%d9%88" in r["URL"]][0]
    assert persian["Canonical relationship"].startswith("self (written differently")
    assert persian["URL (decoded)"].endswith("/اتو/")
    assert persian["Extraction state"] == "success" and persian["Robots.txt allowed (Googlebot)"] == "yes"


def test_spreadsheet_formula_in_a_title_is_neutralised(crawled):
    _, out = crawled
    data, _ = rows(out / "inventory.csv")
    evil = [r for r in data if r["URL"].endswith("/evil/")][0]
    assert evil["Title"].startswith("'=HYPERLINK")


def test_analyze_outputs(crawled):
    site, out = crawled
    analyze.run_analyze(out, log=lambda *_: None)
    pairs, header = rows(out / "similar_pairs.csv")
    assert header[:6] == ORIGINAL_PAIRS and header == PAIR_HEADER
    key = {(r["URL A"].replace(site.base, ""), r["URL B"].replace(site.base, "")): r for r in pairs}
    assert ("/p1/", "/p4/") in key and key[("/p1/", "/p4/")]["Same H1"] == "YES"
    assert float(key[("/p1/", "/p4/")]["Containment"]) == 1.0
    assert ("/p1/", "/p2/") in key and key[("/p1/", "/p2/")]["Shared terms"]
    assert not any("/noidx/" in k[0] + k[1] for k in key)                      # noindex pages are left out by default
    assert (out / "pairs.json").exists() and (out / "analysis_manifest.json").exists()
    canon_rows, _ = rows(out / "canonical_report.csv")
    assert any(r["URL"].endswith("/p4/") for r in canon_rows)
    text = (out / "issues.txt").read_text(encoding="utf-8")
    assert "ERRORS" in text and "WARNINGS" in text and "REVIEW" in text and "not proof" in text
    manifest = json.loads((out / "analysis_manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "2" and manifest["limitations"]


def test_review_flow_through_the_cli(crawled):
    _, out = crawled
    analyze.run_analyze(out, log=lambda *_: None)
    args = cli.build_parser().parse_args(["review", "--in-dir", str(out), "--limit", "2"])
    answers = iter(["1", "i"])
    cli.cmd_review(args, input_fn=lambda prompt="": next(answers))
    lines = (out / "decisions.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2 and json.loads(lines[0])["decision"] == "merge_a_into_b"
    assert (out / "decisions.csv").exists()
    cal = cli.build_parser().parse_args(["calibrate", "--in-dir", str(out)])
    cli.cmd_calibrate(cal)
    assert "PROVISIONAL" in (out / "calibration.txt").read_text(encoding="utf-8")


def test_non_interactive_cli_end_to_end(site, tmp_path, capsys):
    b = build(site)
    out = tmp_path / "o"
    assert cli.main(["crawl", "--allow-local", "--sitemap", b + "/sitemap_index.xml", "--out-dir", str(out), "--delay", "0",
                     "--retries", "0", "--yes", "--robots", "respect"]) == 0
    assert cli.main(["analyze", "--in-dir", str(out), "--yes"]) == 0
    assert (out / "similar_pairs.csv").exists()


def test_unreadable_robots_txt_asks_the_human(site, tmp_path):
    b = build(site)
    site.add("/robots.txt", "down", status=503)
    cfg = crawl.CrawlConfig(allow_local=True, sitemap=b + "/sitemap_index.xml", out_dir=str(tmp_path / "a"), delay=0, retries=0, limit=2)
    with pytest.raises(RuntimeError, match="robots.txt could not be read"):
        crawl.run_crawl(cfg, log=lambda *_: None)
    asked = []
    crawl.run_crawl(crawl.CrawlConfig(allow_local=True, sitemap=b + "/sitemap_index.xml", out_dir=str(tmp_path / "b"), delay=0, retries=0, limit=2),
                    input_fn=lambda q: asked.append(q) or "y", log=lambda *_: None)
    assert asked and (tmp_path / "b" / "inventory.csv").exists()
    crawl.run_crawl(crawl.CrawlConfig(allow_local=True, sitemap=b + "/sitemap_index.xml", out_dir=str(tmp_path / "c"), delay=0, retries=0,
                                      limit=2, robots="ignore"), log=lambda *_: None)
    assert (tmp_path / "c" / "inventory.csv").exists()


def test_variants_command_asks_and_analyze_uses_the_answer(site, tmp_path):
    b = site.base
    site.add("/robots.txt", "", ctype="text/plain")
    site.add("/sitemap.xml", f'<urlset {NS}><url><loc>{b}/a/</loc></url><url><loc>{b}/b/</loc></url></urlset>', ctype="application/xml")
    text_a = "این نرم افزار اداری برای سازمان ها ساخته شده و نرم افزار پیوند همه کارها را انجام می دهد " * 3
    text_b = text_a.replace("نرم افزار", "نرمافزار", 3) + " نرمافزار نرمافزار"
    site.add("/a/", page("الف", "الف", text_a))
    site.add("/b/", page("ب", "ب", text_b))
    out = tmp_path / "v"
    cli.main(["crawl", "--allow-local", "--sitemap", b + "/sitemap.xml", "--out-dir", str(out), "--delay", "0", "--retries", "0", "--yes"])
    args = cli.build_parser().parse_args(["variants", "--in-dir", str(out), "--min-count", "2"])
    cli.cmd_variants(args, input_fn=lambda prompt="": "y")
    saved = json.loads((out / "persian_variants.json").read_text(encoding="utf-8"))
    assert saved.get("نرمافزار") == "نرم افزار"
