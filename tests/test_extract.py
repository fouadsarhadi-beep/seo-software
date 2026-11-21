from seo_analysis.web.extract import extract_page

HTML = """<!doctype html><html lang="fa-IR"><head><title> سامانه
 اتوماسیون </title>
<meta name="description" content="توضیح کوتاه"><meta name="robots" content="index, max-snippet:-1">
<meta name="googlebot" content="noindex"><base href="https://s.ir/blog/">
<link rel="canonical" href="post/"><link rel="canonical" href="https://s.ir/blog/post/"></head>
<body><header>MENU</header><nav>NAV</nav><h1>تیتر اول</h1><h1>تیتر دوم</h1><h2>x</h2>
<div class="entry-content"><p>متن اصلی مقاله درباره اتوماسیون اداری</p><div class="related">پیشنهادها</div>
<script>var a=1</script></div><footer>FOOT</footer></body></html>"""


def test_head_data_and_all_robots_tags():
    p = extract_page(HTML, "https://s.ir/x/")
    assert p.title == "سامانه اتوماسیون" and p.meta_description == "توضیح کوتاه"
    assert p.h1_list == ["تیتر اول", "تیتر دوم"] and p.h2_count == 1 and p.lang == "fa-IR"
    assert ("robots", "index, max-snippet:-1") in p.robots_meta and ("googlebot", "noindex") in p.robots_meta


def test_relative_canonical_resolved_with_base_and_all_candidates_kept():
    p = extract_page(HTML, "https://s.ir/x/")
    assert p.canonicals == ["https://s.ir/blog/post/", "https://s.ir/blog/post/"]


def test_content_selector_exclusions_and_state():
    p = extract_page(HTML, "https://s.ir/x/", exclude_selectors=[".related"])
    assert p.selector == ".entry-content" and p.state == "success"
    assert "پیشنهادها" not in p.text and "MENU" not in p.text and "FOOT" not in p.text and "var a" not in p.text
    assert p.words == 6


def test_user_selector_that_matches_nothing_is_reported_as_fallback():
    p = extract_page(HTML, "https://s.ir/x/", content_selector=".nope")
    assert p.state == "fallback" and p.selector == ".entry-content"


def test_body_fallback_and_empty_state():
    p = extract_page("<html><body><div>فقط یک متن</div></body></html>", "https://s.ir/")
    assert p.selector == "body" and p.state == "fallback" and p.words == 3
    e = extract_page("<html><body><script>x</script></body></html>", "https://s.ir/")
    assert e.state == "empty" and e.words == 0
