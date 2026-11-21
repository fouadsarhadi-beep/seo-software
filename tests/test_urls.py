from seo_analysis.core import urls


def test_percent_encoding_case_and_decoding_are_equal():
    a = "https://samatoos.ir/%d8%a7%d8%aa%d9%88%d9%85%d8%a7%d8%b3%db%8c%d9%88%d9%86/"
    b = "https://samatoos.ir/%D8%A7%D8%AA%D9%88%D9%85%D8%A7%D8%B3%DB%8C%D9%88%D9%86/"
    c = "https://samatoos.ir/اتوماسیون/"
    assert urls.url_key(a) == urls.url_key(b) == urls.url_key(c)
    assert urls.relation(a, b)[0] == "same_encoding"
    assert urls.relation(a, a)[0] == "same"


def test_variants_are_named():
    base = "https://samatoos.ir/page/"
    assert urls.relation(base, "https://samatoos.ir/page")[1] == "differs only by trailing slash"
    assert "scheme" in urls.relation(base, "http://samatoos.ir/page/")[1]
    assert "www" in urls.relation(base, "https://www.samatoos.ir/page/")[1]
    assert urls.relation(base, "https://samatoos.ir/other/")[0] == "other"


def test_idn_host_equals_punycode():
    uni = "https://سماتوس.ایران/"
    puny = "https://" + "سماتوس.ایران".encode("idna").decode() + "/"
    assert urls.url_key(uni) == urls.url_key(puny)


def test_default_ports_and_fragments_ignored():
    assert urls.url_key("https://samatoos.ir:443/a/#top") == urls.url_key("https://samatoos.ir/a/")


def test_origin_scope_requires_same_host_scheme_and_port():
    from seo_analysis.core.network import HttpOrigin
    origin = HttpOrigin.from_url("https://example.org/sitemap.xml")
    assert origin.allows("https://example.org:443/article")
    assert not origin.allows("https://www.example.org/article")
    assert not origin.allows("https://example.org:8443/article")
    assert not origin.allows("http://example.org/article")
