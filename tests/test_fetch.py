import pytest

from seo_analysis.core.network import HttpOrigin

from seo_analysis.web.fetch import Fetcher, decode_body
from seo_analysis.web.robots import RobotsPolicy


def mk(site, **kw):
    kw.setdefault("origin", HttpOrigin.from_url(site.base))
    return Fetcher("t", allow_local=True, delay=0, retries=kw.pop("retries", 2), backoff_base=0, sleep=lambda s: None, **kw)


def test_redirect_chain_keeps_first_and_final_status(site):
    site.redirect("/a", site.base + "/b", 301)
    site.redirect("/b", site.base + "/c", 302)
    site.add("/c", "<html>ok</html>")
    r = mk(site).get(site.base + "/a")
    assert r.first_status == 301 and r.final_status == 200 and r.final_url.endswith("/c")
    assert [s for _, s in r.chain] == [301, 302, 200] and r.redirect_count == 2


def test_redirect_loop_detected(site):
    site.redirect("/a", site.base + "/b")
    site.redirect("/b", site.base + "/a")
    r = mk(site).get(site.base + "/a")
    assert r.redirect_note == "loop"


def test_too_many_redirects(site):
    for i in range(8):
        site.redirect(f"/h{i}", site.base + f"/h{i+1}")
    r = mk(site, max_redirects=3).get(site.base + "/h0")
    assert r.redirect_note == "too_many"


def test_external_redirect_is_blocked_before_any_request(site):
    site.redirect("/a", f"http://localhost:{site.port}/secret")
    site.add("/secret", "x")
    r = mk(site).get(site.base + "/a")
    assert r.redirect_note.startswith("blocked_external") and site.hits["/secret"] == 0


def test_redirect_into_robots_disallowed_path_is_blocked(site):
    site.redirect("/a", site.base + "/private/x")
    site.add("/private/x", "x")
    f = mk(site, robots=RobotsPolicy.parse("User-agent: *\nDisallow: /private/"))
    r = f.get(site.base + "/a")
    assert r.redirect_note.startswith("blocked_robots") and site.hits["/private/x"] == 0


def test_permanent_errors_are_not_retried(site):
    site.add("/gone", "x", status=410)
    r = mk(site).get(site.base + "/gone")
    assert r.final_status == 410 and site.hits["/gone"] == 1


def test_temporary_error_is_retried_and_retry_after_respected(site):
    slept = []
    site.routes["/t"] = lambda n: (503, [("Retry-After", "2")], b"busy") if n == 1 else (200, [("Content-Type", "text/html")], b"<p>ok</p>")
    f = Fetcher("t", allow_local=True, delay=0, retries=2, backoff_base=0, sleep=slept.append, origin=HttpOrigin.from_url(site.base))
    r = f.get(site.base + "/t")
    assert r.final_status == 200 and site.hits["/t"] == 2 and r.retries_used == 1 and 2.0 in slept


def test_retries_are_bounded(site):
    site.add("/busy", "x", status=429)
    r = mk(site, retries=2).get(site.base + "/busy")
    assert r.final_status == 429 and site.hits["/busy"] == 3


def test_body_is_capped(site):
    site.add("/big", "a" * 200_000)
    r = mk(site, max_bytes=1000).get(site.base + "/big")
    assert r.truncated and len(r.raw) == 1000


def test_windows_1256_pages_are_decoded():
    raw = "<meta charset=windows-1256><p>سلام جهان</p>".encode("cp1256")
    assert "سلام جهان" in decode_body(raw, "text/html")
    assert "سلام" in decode_body("<p>سلام</p>".encode("utf-8"), "text/html; charset=iso-8859-1")


def test_repeated_headers_are_kept_separate(site):
    site.add("/h", "<p>x</p>", headers=[("X-Robots-Tag", "googlebot: noindex"), ("X-Robots-Tag", "otherbot: nofollow"),
                                        ("Link", '<https://s.ir/c/>; rel="canonical"')])
    r = mk(site).get(site.base + "/h")
    assert r.x_robots == ["googlebot: noindex", "otherbot: nofollow"]
    assert r.link_headers == ['<https://s.ir/c/>; rel="canonical"']


def test_connection_error_is_reported_not_raised():
    f = Fetcher("t", allow_local=True, delay=0, retries=1, backoff_base=0, sleep=lambda s: None, origin=HttpOrigin.from_url("http://127.0.0.1:1"), timeout=(1, 1))
    r = f.get("http://127.0.0.1:1/")
    assert r.error and r.final_status == 0
