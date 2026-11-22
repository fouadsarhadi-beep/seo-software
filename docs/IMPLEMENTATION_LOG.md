# Implementation log

Dates use Tehran time and reflect when the work was recorded in Git. Step numbers follow [Section 14 of the architecture](../SEO_ANALYSIS_SOFTWARE_ARCHITECTURE.md#14-implementation-sequence--stable-foundation-and-working-vertical-slices).

## Stages A–D

- Stage A, Step 1 — Inventoried the baseline package and its six CLI commands on 2026-11-22.
- Stage A, Step 2 — Reproduced the baseline suite with 75 passing tests and one optional skip on 2026-11-22.
- Stage A, Step 3 — Set Python 3.12 as the supported runtime, locked dependencies and documented Windows installation on 2026-11-22.
- Stage A, Step 4 — Established the package structure, shared configuration and network policy on 2026-11-22.
- Stage A, Step 5 — Set up application-data storage, the CLI entry point and the workspace diagnostic on 2026-11-22.
- Stage B, Step 1 — Added website, sitemap and URL-list inputs plus interactive target selection on 2026-11-22.
- Stage B, Step 2 — Enforced same-origin fetches and redirect checks with explicit local-site opt-in on 2026-11-22.
- Stage B, Step 3 — Added sitemap discovery and opt-in internal link crawling on 2026-11-22.
- Stage B, Step 4 — Added shared crawl budgets, durable observations and coverage manifests on 2026-11-22.
- Stage B, Step 5 — Combined crawling, analysis and reporting in one audit command on 2026-11-22.
- Stage B, Step 6 — Added terminal, JSON and CSV reports with evidence IDs on 2026-11-22.
- Stage B, Step 7 — Verified target inputs and crawl behavior against local fixtures on 2026-11-22.
- Stage C, Step 1 — Unified crawl, audit, offline analysis, variants, review and calibration under a shared tool runner on 2026-11-22.
- Stage C, Step 2 — Added SQLite history, projects, saved targets and recovery from run artifacts on 2026-11-22.
- Stage C, Step 3 — Added eight offline checks for technical SEO, sitemaps, links, broken links, canonicals, JSON-LD, hreflang and assets on 2026-11-22.
- Stage C, Step 4 — Added same-origin snapshot comparisons and reopened review decisions when page content changed on 2026-11-22.
- Stage C, Step 5 — Added structured CLI output and offline agent invocation by run ID on 2026-11-22.
- Stage D, Step 1 — Built a loopback-only FastAPI workbench with server-rendered pages on 2026-11-22.
- Stage D, Step 2 — Added audit forms, progress, cancellation, findings, evidence, downloads and project management on 2026-11-22.
- Stage D, Step 3 — Reused the CLI tool runner and workspace history in the browser on 2026-11-22.
- Stage D, Step 4 — Enforced host, origin and form-token checks, and paginated history and findings on 2026-11-22.
- Stage D, Step 2 follow-up — Made cancellation interrupt retry waits and linked completed observations from cancelled runs on 2026-11-22. The Linux suite passed 109 tests with one optional skip. Chromium passed the audit, evidence and CSV download flow.

- Stage B, Steps 5–7 and Stage D, Step 2 follow-up — Fixed main text extraction for pages with empty containers and clarified crawl and comparison coverage on 2026-11-22. On the first ten current post sitemap pages from samatoos.ir, the old extractor returned zero words for all ten. The updated extractor recovered text from all ten, including 43 words from the reported article. A local replay through the full audit compared nine pages and excluded one marked noindex.

## Offline work in later stages

- Stage E, Steps 2, 3 and 5 (offline) — Added Search Console and GA4 file imports, URL matching against crawl observations and Excel reporting on 2026-11-22.
- Stage F, Steps 1 and 5 — Added local CSV, TSV, XLSX, RSS and Atom imports with source hashes, field mappings, dates and row references on 2026-11-22.
- Stage G, Steps 1–4 (partial) — Added keyword normalization, query-to-page mapping, SERP overlap, brief candidates, sampled competitor gaps, rank history and backlink grouping on 2026-11-22.
- Stage H, Steps 2–4 (offline) — Added static build checks, Lighthouse and axe report imports, screenshot comparison and server log summaries on 2026-11-22.
- Stage I, Steps 1–3 (partial) — Added a scoped MCP server for selected runs and optional Looker Studio report links in workbook metadata on 2026-11-22.
- Stage J, Steps 1 and 2 (partial) — Benchmarked and optimized offline content comparison on 2026-11-22. Built and tested the 0.3.0 Python wheel on Linux.

## Connected Google work

- Stage E, Step 1 — Added separate read-only Google consent flows, OS credential storage, property selection and disconnect on 2026-11-22. Verified the flow with simulated consent and API responses. Live authorization is awaiting an owner's property and Desktop OAuth client.

- Stage E, Step 2 — Added bounded Search Analytics pulls and single-URL Inspection for the selected property on 2026-11-22. Verified pagination, missing measurements, duplicate rows, partial pulls and property boundaries using mocked Google responses.

- Stage E, Step 3 — Added bounded GA4 Data API retrieval for web landing-page sessions and key events on 2026-11-22. Verified pagination, quota errors and missing values with mocked responses. Verified that the workbook keeps unscoped paths unresolved and retains all evidence for an ambiguous canonical match.

- Stage E, Step 4 — Added standalone Lighthouse report import, PageSpeed Insights lab tests and CrUX field queries on 2026-11-22. Mocked responses verified separation of lab and field metrics, missing measurements, collection periods and unavailable records. The live keyless PageSpeed check returned HTTP 429.

- Stage E, Step 5 — Added offline CSV and Excel previews and checksum-approved Google Sheets publication on 2026-11-22. Mocked responses verified app-file consent, literal cell writes, upload retry and duplicate avoidance after an uncertain create result. Live publication requires a Sheets connection.

## Live research sources

- Stage F, Steps 2, 3 and 5 — Added one-page Brave Search samples and bounded public RSS and Atom retrieval on 2026-11-22. Both feed the existing research dataset format. Verified feed retrieval with a local HTTP fixture and Brave with mocked responses. Live benchmarking needs a Brave key on a plan permitting storage. The cloud could not establish a direct connection for the W3C feed check.

[Current scope and remaining work](ROADMAP.md)
