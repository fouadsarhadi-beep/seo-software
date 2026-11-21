"""Search Console data: tolerant CSV loaders (Persian digits and separators, semicolon delimiters,
Persian headers) and an optional read-only API puller. Evidence only; a missing query row is NOT proof
that a page never appeared for it (the API returns top rows, hides anonymized queries)."""
from __future__ import annotations

import csv
import datetime as _dt
import json
import re
import time
from pathlib import Path

from seo_analysis.core.urls import url_key

_NUM = {**{0x06F0 + i: str(i) for i in range(10)}, **{0x0660 + i: str(i) for i in range(10)},
        0x066B: ".", 0x066C: ",", 0x066A: "%"}


def to_float(value) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    t = str(value).translate(_NUM).replace("\u00a0", "").replace(" ", "").strip()
    pct = t.endswith("%")
    t = t.rstrip("%")
    if re.fullmatch(r"\d{1,3}(,\d{3})+(\.\d+)?", t):
        t = t.replace(",", "")
    elif "," in t and "." not in t:
        t = t.replace(",", ".")
    try:
        v = float(t)
    except ValueError:
        return 0.0
    return v / 100 if pct else v


def _read(path):
    text = Path(path).read_text(encoding="utf-8-sig")
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    rows = [r for r in csv.reader(text.splitlines(), dialect) if any(c.strip() for c in r)]
    return rows


def _find(header, *needles):
    for i, h in enumerate(header):
        hl = h.lower()
        if any(n in hl for n in needles):
            return i
    return None


def load_pages(path) -> dict:
    """GSC 'Pages' export -> {url_key: {url, clicks, impressions, ctr, position}}."""
    rows = _read(path)
    header, data = rows[0], rows[1:]
    url_i = _find(header, "page", "url", "صفحه", "صفحات", "نشانی")
    if url_i is None:
        url_i = next((i for i, c in enumerate(data[0]) if c.strip().lower().startswith("http")), 0)
    ci = _find(header, "click", "کلیک")
    ii = _find(header, "impression", "نمایش")
    ti = _find(header, "ctr", "نرخ")
    pi = _find(header, "position", "جایگاه", "موقعیت")
    rest = [i for i in range(len(header)) if i != url_i]
    ci = rest[0] if ci is None and len(rest) > 0 else ci
    ii = rest[1] if ii is None and len(rest) > 1 else ii
    ti = rest[2] if ti is None and len(rest) > 2 else ti
    pi = rest[3] if pi is None and len(rest) > 3 else pi
    out = {}
    for r in data:
        if url_i >= len(r) or not r[url_i].strip():
            continue
        g = lambda i: to_float(r[i]) if i is not None and i < len(r) else 0.0
        out[url_key(r[url_i].strip())] = {"url": r[url_i].strip(), "clicks": g(ci), "impressions": g(ii),
                                          "ctr": g(ti), "position": g(pi)}
    return out


def load_query_page(path) -> dict:
    """Query x page rows -> {url_key: {query: (impressions, clicks, position)}}."""
    rows = _read(path)
    header, data = rows[0], rows[1:]
    url_i = _find(header, "page", "url", "صفحه")
    if url_i is None:
        url_i = next((i for i, c in enumerate(data[0]) if c.strip().lower().startswith("http")), 1)
    q_i = _find(header, "quer", "عبارت", "کلمه")
    if q_i is None:
        q_i = next(i for i in range(len(header)) if i != url_i)
    ci = _find(header, "click", "کلیک")
    ii = _find(header, "impression", "نمایش")
    pi = _find(header, "position", "جایگاه", "موقعیت")
    out: dict = {}
    for r in data:
        if max(url_i, q_i) >= len(r):
            continue
        g = lambda i: to_float(r[i]) if i is not None and i < len(r) else 0.0
        out.setdefault(url_key(r[url_i].strip()), {})[r[q_i].strip()] = (g(ii), g(ci), g(pi))
    return out


def shared_queries(qp: dict, url_a: str, url_b: str, top: int = 5):
    a, b = qp.get(url_key(url_a), {}), qp.get(url_key(url_b), {})
    common = [(q, a[q][0], b[q][0]) for q in a.keys() & b.keys()]
    common.sort(key=lambda x: -(x[1] + x[2]))
    return len(common), common[:top]


# ----------------------------------------------------------------- optional API puller
SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"


def default_dates(days: int = 90, lag: int = 3):
    end = _dt.date.today() - _dt.timedelta(days=lag)
    return (end - _dt.timedelta(days=days - 1)).isoformat(), end.isoformat()


def pull_api(service, site_url: str, start: str, end: str, out_csv, search_type: str = "web",
             data_state: str = "final", row_limit: int = 25000, max_rows: int = 200000, sleep=time.sleep):
    """Pages through searchanalytics.query (query x page). Returns metadata dict, also saved next to the CSV."""
    rows_total, start_row = 0, 0
    with open(out_csv, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["Query", "Page", "Clicks", "Impressions", "CTR", "Position"])
        while rows_total < max_rows:
            body = {"startDate": start, "endDate": end, "dimensions": ["query", "page"], "type": search_type,
                    "dataState": data_state, "rowLimit": row_limit, "startRow": start_row}
            resp = service.searchanalytics().query(siteUrl=site_url, body=body).execute()
            rows = resp.get("rows", [])
            for r in rows:
                q, page = r["keys"][0], r["keys"][1]
                w.writerow([q, page, r.get("clicks", 0), r.get("impressions", 0), r.get("ctr", 0), r.get("position", 0)])
            rows_total += len(rows)
            if len(rows) < row_limit:
                break
            start_row += row_limit
            sleep(0.4)
    meta = {"property": site_url, "start_date": start, "end_date": end, "dimensions": ["query", "page"],
            "search_type": search_type, "data_state": data_state, "rows": rows_total,
            "fetched_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
            "limitations": ["Search Console dates use Pacific Time.",
                            "The API returns top rows (documented ceiling 50,000 rows per day per property per search type).",
                            "Anonymized queries are not included.",
                            "A missing query row does NOT prove a page never appeared for that query.",
                            "data_state 'all' includes fresh, provisional data."]}
    Path(str(out_csv) + ".meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta
