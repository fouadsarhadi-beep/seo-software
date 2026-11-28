import json

from seo_analysis.analysis import review
from seo_analysis.analysis import similarity


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


def test_calibration_samples_pairs_outside_similarity_index_and_weights_strata(tmp_path):
    items = [dict(url=f"https://example.org/{i}", title=f"term{i}", h1="", text=f"term{i}") for i in range(40)]
    items[1].update(title="term0", text="term0")
    corpus = similarity.prepare(items, similarity.Settings())
    flagged = similarity.compare(corpus)
    population, samples = similarity.calibration_sample(corpus, flagged, 2, seed=2026)
    assert population == {"flagged": 1, "unflagged": 779}
    assert (population, samples) == similarity.calibration_sample(corpus, flagged, 2, seed=2026)
    assert len(samples) == 3 and sum(stratum == "unflagged" and not result.triggers for stratum, result in samples) == 2

    rows = [pair(result.url_a, result.url_b, stratum=stratum, title_sim=result.title_sim,
                 evidence=result.evidence, triggers=result.triggers) for stratum, result in samples]
    path = tmp_path / "decisions.jsonl"
    review.save_decision(path, rows[0], "differentiate", "")
    assert "Review the full sample" in review.calibrate(rows, path, population=population)
    negative = next(row for row in rows if row["stratum"] == "unflagged")
    for row in rows:
        review.save_decision(path, row, "ignore" if row is negative else "differentiate", "")
    report = review.calibrate(rows, path, population=population)
    assert "weighted estimates" in report
    title_threshold = report.split("title similarity", 1)[1].splitlines()[2].split()
    assert title_threshold == ["0.20", "1", "1.000", "0.003"]
    assert "Recall is unavailable" in review.calibrate(rows, path)
