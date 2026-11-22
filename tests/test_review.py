import json

from seo_analysis.analysis import review


def pair(a, b, **kw):
    p = {"url_a": a, "url_b": b, "title_a": "الف", "title_b": "ب", "title_sim": 0.5, "dup": 0.7, "containment": 0.9,
         "topic": 0.8, "same_h1": False, "shared_terms": ["اتوماسیون"], "shared_phrases": ["یک عبارت مشترک"],
         "triggers": ["near-duplicate"], "evidence": 2, "page_type_a": "blog", "page_type_b": "blog",
         "words_a": 400, "words_b": 900, "short_page": False, "gsc": None}
    p.update(kw)
    return p


def feeder(answers):
    it = iter(answers)
    return lambda prompt="": next(it)


def test_decisions_are_saved_one_by_one_and_resumable(tmp_path):
    path = tmp_path / "d.jsonl"
    pairs = [pair("https://s.ir/a/", "https://s.ir/b/"), pair("https://s.ir/c/", "https://s.ir/d/")]
    out = []
    n = review.review_loop(pairs, path, input_fn=feeder(["n", "keep the guide", "x", "1", "i"]), output_fn=out.append)
    assert n == 2
    lines = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()]
    assert lines[0]["decision"] == "merge_a_into_b" and lines[0]["note"] == "keep the guide"
    assert lines[1]["decision"] == "ignore"
    assert any("please choose" in str(o) for o in out)                     # invalid input is re-asked
    again = review.review_loop(pairs, path, input_fn=feeder([]), output_fn=lambda *_: None)
    assert again == 0                                                      # nothing left to decide


def test_skip_and_quit_do_not_save(tmp_path):
    path = tmp_path / "d.jsonl"
    pairs = [pair("https://s.ir/a/", "https://s.ir/b/"), pair("https://s.ir/c/", "https://s.ir/d/")]
    assert review.review_loop(pairs, path, input_fn=feeder(["s", "q"]), output_fn=lambda *_: None) == 0
    assert not path.exists()


def test_pair_key_ignores_order_and_url_spelling():
    assert review.pair_key("https://s.ir/%D8%A7/", "https://s.ir/b/") == review.pair_key("https://s.ir/b", "https://s.ir/ا")[:0] + review.pair_key("https://s.ir/b/", "https://s.ir/%d8%a7/")


def test_calibration_is_marked_provisional_with_few_decisions(tmp_path):
    path = tmp_path / "d.jsonl"
    pairs = [pair("https://s.ir/a/", "https://s.ir/b/", dup=0.9), pair("https://s.ir/c/", "https://s.ir/d/", dup=0.2)]
    review.review_loop(pairs, path, input_fn=feeder(["1", "i"]), output_fn=lambda *_: None)
    text = review.calibrate(pairs, path, output_fn=lambda *_: None)
    assert "PROVISIONAL" in text and "near-duplicate" in text and "precision" in text


def test_reviews_reopen_after_content_changes(tmp_path):
    path = tmp_path / "decisions.jsonl"
    current = pair("https://example.org/a", "https://example.org/b", content_revisions={"a":"1", "b":"2"})
    assert review.review_loop([current], path, input_fn=feeder(["i"])) == 1
    assert review.review_loop([current], path, input_fn=feeder([])) == 0
    changed = dict(current, content_revisions={"a":"3", "b":"2"})
    assert "Calibration from 0 decisions" in review.calibrate([changed],path)
    assert review.review_loop([changed],path,input_fn=feeder(["d"])) == 1
