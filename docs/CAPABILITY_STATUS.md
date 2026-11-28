# Capability status

What is available offline, what is verified with fixtures, and what has actually been run live. **Authentication is not retrieval, and retrieval is not publishing** — each is recorded separately below. Status as of 2026-11-28.

| Capability | Offline | Fixture-verified | Live-verified | Notes |
| --- | --- | --- | --- | --- |
| Website audit and crawl | Yes | Yes | **Yes** | 100-page sample on samatoos.ir; one noindex page excluded |
| Snapshot technical checks | Yes | Yes | Not applicable | Offline by design; makes no requests |
| Snapshot comparison | Yes | Yes | Not applicable | Needs two runs of the same origin |
| Review queue | Yes | Yes | Not applicable | Decisions stored per project, rule and page |
| HTML report, page CSV, bundle | Yes | Yes | Not applicable | Verified on the saved 5- and 100-page runs |
| Excel workbook from imported files | Yes | Yes | Not applicable | — |
| Content research from imported samples | Yes | Yes | Not applicable | Persian fixtures |
| Local build QA (static) | Yes | Yes | Not applicable | Also exercised in CI against a local HTML file |
| Local Lighthouse run | Yes | Yes | **Yes** | Lighthouse 13.6 and Chromium 156 on a loopback build |
| Chromium capture, axe checks | Yes | Yes | **Yes** | axe-core 4.11.1; skipped when no system Chromium is present |
| MCP stdio server | Yes | Yes | **Yes** | Client subprocess, allowlist and derived runs verified |
| Search Console — file import | Yes | Yes | Not applicable | — |
| Search Console — API fetch | Needs connection | Yes | **Pending** | Mocked pagination, quotas and partial pulls only |
| Search Console — URL Inspection | Needs connection | Yes | **Pending** | Requires a real property |
| GA4 — API fetch | Needs connection | Yes | **Pending** | Mocked quota and missing-value cases only |
| PageSpeed Insights | Needs key (optional) | Yes | **Partial** | A keyless live request returned HTTP 429 |
| CrUX | Needs key | Yes | **Pending** | Requires an API key |
| Google Sheets publish | Needs connection | Yes | **Pending** | Literal cells, retry and duplicate avoidance mocked |
| Brave Search sampling | Needs key | Yes | **Pending** | Needs a plan that permits storing results |
| Public RSS/Atom feed | Yes | Yes | **Pending** | The cloud environment could not open a direct connection |
| WordPress inventory | Public reads | Yes | **Pending** | Authenticated reads need an Application Password |
| Desktop launcher, Windows | Not applicable | Yes | **Pending** | Unit-tested dispatch; not run on Windows here |

## What "pending" means here

Pending means the code path exists, is covered against fixtures, and has **never been observed against the real provider**. Do not read those rows as working integrations. When an owner runs one, record the date, environment, source and outcome in [MANUAL_AUDIT_LOG.md](MANUAL_AUDIT_LOG.md) and promote the row.

## Known limits that are not defects

- A capped crawl leaves pages unassessed; the UI says so and comparison marks them rather than calling them fixed.
- A capability absent from a sample is not evidence of absence — research states this wherever samples are compared.
- Similarity is not cannibalisation, and Clarity of field versus lab metrics is preserved separately.
- Google may omit rows (anonymised or low-volume queries); a missing row is never treated as zero.