import json

from seo_analysis.connectors import gsc
from seo_analysis.core.urls import url_key


def test_numbers_in_persian_locale():
    assert gsc.to_float("۱٬۲۳۴") == 1234
    assert abs(gsc.to_float("۲٫۸٪") - 0.028) < 1e-9
    assert abs(gsc.to_float("2.8%") - 0.028) < 1e-9
    assert gsc.to_float("1,234") == 1234 and gsc.to_float("12,5") == 12.5
    assert gsc.to_float("") is None and gsc.to_float(None) is None and gsc.to_float(7) == 7.0


def test_pages_export_english_headers(tmp_path):
    f = tmp_path / "p.csv"
    f.write_text("Top pages,Clicks,Impressions,CTR,Position\nhttps://s.ir/a/,12,300,4%,8.2\n", encoding="utf-8-sig")
    d = gsc.load_pages(f)["https://s.ir/a/"]
    assert d["clicks"] == 12 and d["impressions"] == 300 and abs(d["ctr"] - 0.04) < 1e-9 and d["position"] == 8.2


def test_pages_export_persian_headers_semicolons_and_digits(tmp_path):
    f = tmp_path / "p.csv"
    f.write_text("صفحه‌های برتر;کلیک‌ها;نمایش‌ها;نرخ کلیک;جایگاه\nhttps://s.ir/اتو/;۱۲;۳۰۰;۴٪;۸٫۲\n", encoding="utf-8-sig")
    d = gsc.load_pages(f)
    assert d[url_key("https://s.ir/%D8%A7%D8%AA%D9%88/")]["clicks"] == 12   # decoded vs encoded URL still matches
    assert d[url_key("https://s.ir/اتو/")]["position"] == 8.2


def test_pages_export_with_unknown_headers_falls_back_to_column_order(tmp_path):
    f = tmp_path / "p.csv"
    f.write_text("a,b,c,d,e\nhttps://s.ir/a/,5,50,10%,3\n", encoding="utf-8")
    assert gsc.load_pages(f)["https://s.ir/a/"]["impressions"] == 50


def test_shared_queries(tmp_path):
    f = tmp_path / "q.csv"
    f.write_text("Query,Page,Clicks,Impressions,CTR,Position\n"
                 "اتوماسیون اداری,https://s.ir/a/,1,100,0.01,5\nاتوماسیون اداری,https://s.ir/b/,0,40,0,9\n"
                 "فقط الف,https://s.ir/a/,0,10,0,3\n", encoding="utf-8-sig")
    qp = gsc.load_query_page(f)
    n, top = gsc.shared_queries(qp, "https://s.ir/a/", "https://s.ir/b/")
    assert n == 1 and top == [("اتوماسیون اداری", 100.0, 40.0)]


class FakeService:
    def __init__(self, rows):
        self.rows, self.calls = rows, []

    def searchanalytics(self):
        return self

    def query(self, siteUrl, body):
        self.calls.append((siteUrl, body))
        start, lim = body["startRow"], body["rowLimit"]
        chunk = self.rows[start:start + lim]
        class Req:
            def execute(self_inner):
                return {"rows": chunk}
        return Req()


def test_api_pagination_metadata_and_readonly_scope(tmp_path):
    rows = [{"keys": [f"q{i}", f"https://s.ir/{i}/"], "clicks": i, "impressions": i * 10, "ctr": 0.1, "position": 3} for i in range(5)]
    svc = FakeService(rows)
    out = tmp_path / "qp.csv"
    meta = gsc.pull_api(svc, "sc-domain:s.ir", "2026-08-01", "2026-10-30", out, row_limit=2, sleep=lambda s: None)
    assert [c[1]["startRow"] for c in svc.calls] == [0, 2, 4] and meta["rows"] == 5
    assert svc.calls[0][1]["dimensions"] == ["query", "page"] and svc.calls[0][1]["dataState"] == "final"
    assert out.read_text(encoding="utf-8-sig").count("\n") == 6
    m = json.loads((tmp_path / "qp.csv.meta.json").read_text(encoding="utf-8"))
    assert any("Pacific" in x for x in m["limitations"]) and any("does NOT prove" in x for x in m["limitations"])
    assert gsc.SCOPE.endswith("webmasters.readonly")


def test_missing_csv_metrics_remain_unknown(tmp_path):
    source = tmp_path / "pages.csv"
    source.write_text("Page,Impressions,Position\nhttps://example.org/,0,\n")
    row = gsc.load_pages(source)["https://example.org/"]
    assert row["impressions"] == 0 and row["clicks"] is None and row["position"] is None
