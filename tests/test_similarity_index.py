from seo_analysis.analysis import similarity as sim


def test_indexed_matches_exhaustive_comparison(monkeypatch):
    items = [
        dict(url=str(i), text=f"word{i} other{i} description{i}", title=f"title{i}", h1=f"heading{i}")
        for i in range(43)
    ]
    items[1]["h1"] = items[0]["h1"]
    items[3]["text"] = items[2]["text"]
    items[5]["title"] = items[4]["title"]
    corpus = sim.prepare(items, sim.Settings(shingle=2))
    indexed = sim.compare(corpus)
    assert {(p.url_a, p.url_b) for p in indexed} == {("0", "1"), ("2", "3"), ("4", "5")}
    corpus.settings.thr_title = 0
    all_pairs = sim.compare(corpus)
    assert len(all_pairs) == len(items) * (len(items) - 1) // 2
    monkeypatch.setattr(
        sim, "candidate_rows", lambda c: (range(i + 1, len(c.docs)) for i in range(len(c.docs)))
    )
    corpus.settings.thr_title = 0.6
    assert indexed == sim.compare(corpus)
