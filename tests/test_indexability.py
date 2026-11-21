from seo_analysis.analysis.indexability import evaluate, parse_directives


def ev(meta=(), header=(), status=200, blocked=False, fetched=True):
    return evaluate(list(meta), list(header), fetched, status, blocked)


def test_meta_noindex():
    assert ev([("robots", "noindex, follow")]).effective == "noindex"


def test_header_noindex_for_googlebot_and_other_bot_ignored():
    assert ev(header=["googlebot: noindex"]).effective == "noindex"
    s = ev(header=["otherbot: noindex"])
    assert s.effective == "indexable" and "otherbot" in s.header_raw


def test_none_means_noindex_and_googlebot_meta_counts():
    assert ev([("robots", "none")]).effective == "noindex"
    assert ev([("googlebot", "noindex")]).effective == "noindex"
    assert ev([("bingbot", "noindex")]).effective == "indexable"


def test_most_restrictive_wins_across_sources():
    s = ev([("robots", "index")], ["noindex"])
    assert s.effective == "noindex" and "X-Robots-Tag" in s.reason


def test_value_directives_and_dates_do_not_confuse_parsing():
    d = parse_directives("max-snippet:20, unavailable_after: Wed, 03 Dec 2025 13:09:53 GMT, noindex")
    assert (None, "noindex") in d and (None, "max-snippet:20") in d
    assert parse_directives("otherbot: noindex, nofollow, googlebot: nosnippet") == [
        ("otherbot", "noindex"), ("otherbot", "nofollow"), ("googlebot", "nosnippet")]


def test_unknown_when_not_inspectable_and_status_pages():
    assert ev(blocked=True).effective == "unknown"
    assert ev(fetched=False).effective == "unknown"
    assert ev(status=404).effective == "not_indexable_status"


def test_missing_directives_mean_indexable_by_default_but_raw_is_kept():
    s = ev([("robots", "index, follow, max-image-preview:large")])
    assert s.effective == "indexable" and "max-image-preview" in s.meta_raw
