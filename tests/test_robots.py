from seo_analysis.web.robots import RobotsPolicy

TXT = """
User-agent: *
Disallow: /wp-admin/
Allow: /wp-admin/admin-ajax.php
Disallow: /*?replytocom=
Disallow: /private$
Disallow:

User-agent: googlebot
Disallow: /only-google-blocked/
Disallow: /%d9%85%d9%82%d8%a7%d9%84%d9%87-%d8%ae%d8%b5%d9%88%d8%b5%db%8c/
Sitemap: https://samatoos.ir/sitemap_index.xml
"""


def test_longest_match_and_allow_override():
    p = RobotsPolicy.parse(TXT)
    assert not p.allowed("https://s.ir/wp-admin/x.php")
    assert p.allowed("https://s.ir/wp-admin/admin-ajax.php")


def test_wildcard_and_end_anchor():
    p = RobotsPolicy.parse(TXT)
    assert not p.allowed("https://s.ir/a/?replytocom=5")
    assert not p.allowed("https://s.ir/private")
    assert p.allowed("https://s.ir/private/page")


def test_agent_specific_group_replaces_star_group():
    p = RobotsPolicy.parse(TXT)
    assert p.allowed("https://s.ir/wp-admin/x.php", "googlebot")
    assert not p.allowed("https://s.ir/only-google-blocked/x", "googlebot")
    assert p.allowed("https://s.ir/only-google-blocked/x", "samatoos")


def test_persian_paths_match_whatever_the_encoding():
    p = RobotsPolicy.parse(TXT)
    assert not p.allowed("https://s.ir/مقاله-خصوصی/", "googlebot")
    assert not p.allowed("https://s.ir/%D9%85%D9%82%D8%A7%D9%84%D9%87-%D8%AE%D8%B5%D9%88%D8%B5%DB%8C/", "googlebot")


def test_sitemaps_listed_and_empty_policy_allows_all():
    assert RobotsPolicy.parse(TXT).sitemaps == ["https://samatoos.ir/sitemap_index.xml"]
    assert RobotsPolicy.allow_all().allowed("https://s.ir/anything")
