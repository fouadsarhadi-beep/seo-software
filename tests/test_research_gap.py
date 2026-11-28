from seo_analysis.research.intelligence import competitor_gaps


def test_competitor_gaps_separates_shared_from_both_one_sided_sets():
    domains = {
        "mine.test": {"alpha", "beta", "gamma"},
        "rival.test": {"beta", "delta"},
        "other.test": {"delta", "epsilon"},
    }
    rows = {row["host"]: row for row in competitor_gaps(domains, "mine.test")}
    assert set(rows) == {"rival.test", "other.test"}
    rival = rows["rival.test"]
    assert rival["shared_with_owned"] == 1
    assert rival["only_in_owned_sample"] == ["alpha", "gamma"]
    assert rival["only_in_competitor_sample"] == ["delta"]
    assert rows["other.test"]["shared_with_owned"] == 0


def test_competitor_gaps_stays_empty_when_the_owned_host_is_not_in_the_sample():
    rows = competitor_gaps({"rival.test": {"delta"}}, "mine.test")
    assert rows[0]["shared_with_owned"] == 0
    assert rows[0]["only_in_owned_sample"] == []
    assert rows[0]["only_in_competitor_sample"] == ["delta"]