from contextlib import nullcontext
import json
from pathlib import Path

from seo_analysis.cli import main
from seo_analysis.connectors import performance


def _lab():
    return {
        "requestedUrl": "https://example.com/",
        "finalDisplayedUrl": "https://www.example.com/",
        "lighthouseVersion": "12.0.0",
        "fetchTime": "2026-11-22T12:00:00.000Z",
        "configSettings": {"formFactor": "desktop", "throttlingMethod": "simulate"},
        "categories": {"performance": {"score": 0.9}},
        "audits": {
            "largest-contentful-paint": {"numericValue": 1800},
            "cumulative-layout-shift": {"numericValue": 0},
            "total-blocking-time": {"numericValue": 24},
        },
    }


def _cli(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text('[paths]\ndata_dir = "data"\n', encoding="utf-8")
    return ["--config-file", str(config)]


def _report(capsys):
    run = json.loads(capsys.readouterr().out)
    report = json.loads((Path(run["out_dir"]) / "performance.json").read_text(encoding="utf-8"))
    return run, report


def test_pagespeed_uses_only_lighthouse_lab_data(tmp_path, monkeypatch, capsys):
    def reply(ctx, method, url, *, key, params):
        assert method == "GET" and url == performance.PSI_URL and key is None
        assert params == {"url": "https://example.com/", "strategy": "desktop", "category": "performance"}
        return 200, {"lighthouseResult": _lab(), "loadingExperience": {"metrics": {"INP": {"p75": 50}}}}

    monkeypatch.setattr(performance, "_request", reply)
    assert main([*_cli(tmp_path), "google", "pagespeed", "https://example.com/", "--strategy", "desktop", "--json"]) == 0
    run, report = _report(capsys)
    assert run["counts"]["measurements"] == 3
    assert report["kind"] == "lab" and report["device"] == "desktop" and report["lab_scores"] == {"performance": 0.9}
    assert report["metrics"]["CLS"]["value"] == 0
    assert report["metrics"]["FCP"]["value"] is None
    assert "INP" not in report["metrics"]


def test_local_import_reuses_the_lab_summary_and_makes_no_requests(tmp_path, capsys):
    path = tmp_path / "lighthouse.json"
    path.write_text(json.dumps(_lab()), encoding="utf-8")
    assert main([*_cli(tmp_path), "lighthouse-report", str(path), "--json"]) == 0
    run, report = _report(capsys)
    assert run["data_egress"] == []
    assert report["source_file"] == path.name
    assert report["metrics"]["LCP"] == {"value": 1800, "unit": "ms"}


def test_crux_preserves_form_factor_period_and_missing_values(tmp_path, monkeypatch, capsys):
    key = "fake-test-key-only"
    monkeypatch.setattr(performance, "performance_key", lambda _: key)

    class Response:
        status_code = 200

        def iter_content(self, chunk_size):
            yield json.dumps({
                "record": {
                    "key": {"origin": "https://example.com", "formFactor": "PHONE"},
                    "collectionPeriod": {"firstDate": {"year": 2026, "month": 10, "day": 20}},
                    "metrics": {"cumulative_layout_shift": {"percentiles": {"p75": "0.03"},
                                                             "histogram": [{"start": "0.00", "density": 0.8}]}},
                },
            }).encode()

    class Session:
        def request(self, method, url, *, headers, json, **options):
            assert method == "POST" and url == performance.CRUX_URL
            assert headers == {"X-Goog-Api-Key": key} and options["allow_redirects"] is False
            assert json["origin"] == "https://example.com" and json["formFactor"] == "PHONE"
            assert "url" not in json
            return nullcontext(Response())

    monkeypatch.setattr(performance.requests, "Session", lambda: nullcontext(Session()))
    assert main([*_cli(tmp_path), "google", "crux", "https://example.com/", "--scope", "origin",
                 "--form-factor", "PHONE", "--json"]) == 0
    run, report = _report(capsys)
    assert report["kind"] == "field" and report["scope"] == "origin" and report["form_factor"] == "PHONE"
    assert report["collection_period"]["firstDate"]["day"] == 20
    assert report["metrics"]["CLS"]["p75"] == 0.03 and report["metrics"]["INP"]["p75"] is None
    assert report["metrics"]["CLS"]["histogram"] == [{"start": "0.00", "density": 0.8}]
    assert run["data_egress"][0]["endpoint"] == performance.CRUX_URL
    assert key not in json.dumps(run | report)


def test_crux_no_record_is_distinct_from_error(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(performance, "performance_key", lambda _: "mock-key")
    monkeypatch.setattr(performance, "_request", lambda *args, **kwargs: (404, {"error": {"status": "NOT_FOUND"}}))
    cmd = [*_cli(tmp_path), "google", "crux", "https://example.com/", "--json"]
    assert main(cmd) == 3
    _, report = _report(capsys)
    assert report["status"] == "no_data" and report["metrics"] == {} and report["scope"] == "url"
    monkeypatch.setattr(performance, "_request", lambda *args, **kwargs: (404, {}))
    assert main(cmd) == 2
    run = json.loads(capsys.readouterr().out)
    assert "performance.json" not in run["artifacts"]


def test_pagespeed_rejects_nonpublic_targets_before_sending_requests(tmp_path, capsys):
    assert main([*_cli(tmp_path), "google", "pagespeed", "http://127.0.0.1/", "--json"]) == 2
    run = json.loads(capsys.readouterr().out)
    assert run["data_egress"] == []
    assert "public website" in run["warnings"][0]
