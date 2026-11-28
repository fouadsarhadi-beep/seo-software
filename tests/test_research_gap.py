import json
from pathlib import Path
from uuid import uuid4

from seo_analysis.app.runner import ToolRunner
from seo_analysis.core import tools
from seo_analysis.core.workspace import Workspace
from seo_analysis.research.intelligence import ResearchInput, competitor_gaps
from seo_analysis.storage.history import History


def _dataset(ws, *, device, domain, query):
    rid = uuid4().hex
    folder = ws.runs_dir / rid
    folder.mkdir(parents=True)
    source = {"kind": "serp", "provider": "Export", "observed": "2026-11-20", "locale": "en-US",
              "device": device, "skipped": 0, "capped": False}
    (folder / "dataset.json").write_text(json.dumps(
        {"schema_version": 1, "source": source,
         "rows": [{"row": 1, "query": query, "url": f"https://{domain}/a", "rank": 1}]}), encoding="utf-8")
    (folder / "run.json").write_text(json.dumps(
        {"run_id": rid, "tool_id": "research.import", "status": "succeeded", "project": None,
         "saved_target": None, "started_at": "2026-11-20T00:00:00Z", "finished_at": "2026-11-20T00:00:05Z",
         "parameters": {"kind": "serp", "provider": source["provider"], "observed": source["observed"],
                        "locale": source["locale"], "device": source["device"]},
         "counts": {"rows": 1}, "warnings": [], "artifacts": ["dataset.json"]}), encoding="utf-8")
    History(ws).index(folder)
    return folder


def test_a_desktop_owned_result_cannot_share_a_query_with_a_mobile_competitor(tmp_path):
    ws = Workspace(tmp_path / "config", tmp_path / "data", tmp_path / "exports")
    desktop = _dataset(ws, device="desktop", domain="mine.test", query="alpha")
    mobile = _dataset(ws, device="mobile", domain="rival.test", query="alpha")
    result = ToolRunner(ws).run(tools.RESEARCH, ResearchInput((str(desktop), str(mobile)), "mine.test"),
                                log=lambda _: None)
    report = json.loads((Path(result.out_dir) / "research.json").read_text(encoding="utf-8"))
    captures = report["captures"]
    assert len(captures) == 2 and {capture["device"] for capture in captures} == {"desktop", "mobile"}
    # Nothing can be shared across two captures that were not measured the same way.
    assert [row for capture in captures for row in capture["competitors"] if row["shared_with_owned"]] == []
    assert report["competitors"][0]["scope"] == "combined across every selected sample"


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