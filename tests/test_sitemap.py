import gzip

import pytest

from seo_analysis.core.network import HttpOrigin

from seo_analysis.web import sitemap
from seo_analysis.web.fetch import Fetcher

NS = 'xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"'


def fetcher(site):
    return Fetcher("t", allow_local=True, delay=0, retries=0, origin=HttpOrigin.from_url(site.base), sleep=lambda s: None)


def test_image_extension_locs_are_not_pages():
    xml = (f'<urlset {NS} xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">'
           '<url><loc>https://s.ir/a/</loc><lastmod>2026-01-02</lastmod>'
           '<image:image><image:loc>https://s.ir/a.jpg</image:loc></image:image></url></urlset>').encode()
    kind, items = sitemap.parse_sitemap(xml)
    assert kind == "urlset" and items == [("https://s.ir/a/", "2026-01-02")]


def test_prefixed_namespace_and_index():
    xml = b'<sm:sitemapindex xmlns:sm="http://www.sitemaps.org/schemas/sitemap/0.9"><sm:sitemap><sm:loc>https://s.ir/p.xml</sm:loc></sm:sitemap></sm:sitemapindex>'
    assert sitemap.parse_sitemap(xml) == ("index", [("https://s.ir/p.xml", "")])


def test_gzip_supported_and_bomb_refused():
    xml = f'<urlset {NS}><url><loc>https://s.ir/a/</loc></url></urlset>'.encode()
    assert sitemap.parse_sitemap(gzip.compress(xml))[1][0][0] == "https://s.ir/a/"
    bomb = gzip.compress(b"<urlset>" + b"a" * 5_000_000)
    with pytest.raises(ValueError):
        sitemap.parse_sitemap(bomb, cap=100_000)


@pytest.mark.parametrize("encoding", ["utf-8", "utf-16"])
def test_dtd_entities_refused(encoding):
    with pytest.raises(ValueError):
        sitemap.parse_sitemap('<!DOCTYPE x [<!ENTITY a "b">]><urlset></urlset>'.encode(encoding))


def test_collect_nested_recursive_duplicates_and_skip(site):
    b = site.base
    site.add("/index.xml", f'<sitemapindex {NS}><sitemap><loc>{b}/post.xml</loc></sitemap><sitemap><loc>{b}/category-sitemap.xml</loc></sitemap><sitemap><loc>{b}/index.xml</loc></sitemap><sitemap><loc>{b}/broken.xml</loc></sitemap></sitemapindex>', ctype="application/xml")
    site.add("/post.xml", f'<urlset {NS}><url><loc>{b}/a/</loc></url><url><loc>{b}/a/</loc></url><url><loc>http://evil.example/x/</loc></url><url><loc>{b}/b/</loc></url></urlset>', ctype="application/xml")
    site.add("/category-sitemap.xml", f'<urlset {NS}><url><loc>{b}/cat/</loc></url></urlset>', ctype="application/xml")
    site.add("/broken.xml", "<urlset><url>", ctype="application/xml")
    entries, warnings, files = sitemap.collect(fetcher(site), f"{b}/index.xml", r"category")
    assert [e.url for e in entries] == [f"{b}/a/", f"{b}/b/"]
    assert entries[0].source == f"{b}/post.xml"
    text = " | ".join(warnings)
    assert "already visited" in text and "skipped by pattern" in text and "outside the allowed hosts" in text
    assert "malformed sitemap" in text and "duplicate URL" in text
    assert site.hits["/category-sitemap.xml"] == 0
