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
- Stage D, Steps 2–4 follow-up — Added a project list with on-demand forms and reversible run archiving on 2026-11-22. Simplified the audit summary, clarified the private-network option and moved common report downloads near the top of the results.

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

## Content planning and competitor evidence

- Stage G, Steps 2 and 3 — Added sample-scoped keyword clusters, evidence-linked editorial briefs, Search Console refresh candidates and comparisons from selected owned and competitor crawl runs on 2026-11-22. CLI tests cover Persian queries, missing versus zero values, duplicate source rows and links to both crawl and SERP evidence.

## CMS and site quality

- Stage H, Step 1 — Added a read-only inventory of published WordPress posts and pages and installation-scoped Application Password storage on 2026-11-22. Verified bounded pagination, credential isolation, metadata shaping and redirect refusal with fixtures. Live authorization, media and custom types remain open.

- Stage H, Step 3 — Added local Chromium screenshots, navigation timings, optional axe checks and approved baseline comparisons on 2026-11-22. Verified the CLI against a local HTML fixture with Chromium and axe-core 4.11.1.

- Stage H, Step 1 follow-up — Added WordPress media metadata and registered custom post type inventory on 2026-11-22. Fixtures verify media field selection, catalogue filtering and same-installation route selection.

## Scoped agent workflows

- Stage I, Steps 1–3 — Added MCP crawl comparisons, content analysis, paginated reads of saved decisions and retrieval of existing Sheets and Looker Studio links on 2026-11-22. A stdio client verified the allowlist, derived runs and report evidence.

## Performance and distribution checkpoint

- Stage J, Steps 1–2 — Profiled a 300-page audit fixture and replayed ten saved real pages on 2026-11-22. Consolidated default HTML exclusions into one traversal. The fixture's median audit time moved from 2.10 seconds to 1.77 seconds and real-page extraction results matched exactly.
- Stage J, Step 4 — Built the 0.4.0 Python wheel and extended the cross-platform CI smoke test to run static site QA outside the checkout on 2026-11-22.
- Stage J, Step 4 follow-up — Added a single-file Windows workbench launcher, a writable workspace copy option and a Windows executable build workflow on 2026-11-28.
- Stage J, Step 4 follow-up — Added a double-click Windows script that reuses the project's Python environment and limited executable builds to version tags and manual runs on 2026-11-28.
- Stage C, Step 2 follow-up — Added individual run deletion, bulk audit and run deletion, workspace reset and retryable file cleanup on 2026-11-28. Added a storage write check to terminal startup and recovery guidance for read-only browser requests.
- Stage J, Step 4 follow-up — Added a writable profile fallback for launcher logs and workspace recovery when Windows denies Local AppData access on 2026-11-28.
- Stage J, Step 4 follow-up — Changed the Windows checkout launcher to store its configuration, logs and audit database inside the project on 2026-11-28.

- Stage H, Step 3 follow-up — Added the local Lighthouse runner on 2026-11-22. Lighthouse 13.6 and Chromium 156 produced six lab measurements from a local fixture. The HTTP fixture verified that external requests and paths outside the build are refused.

- Stage C, Step 3 and Stage D, Steps 2–4 follow-up — Added offline technical checks and searchable results to the browser workbench on 2026-11-24. Verified that browser and CLI checks produce matching reports, preserve source evidence and make no requests to the audited site. Saved snapshots with missing markup fields report partial coverage for affected checks.
- Stage C, Step 4, Stage D, Step 2 and Stage G, Step 2 follow-up — Added comparison of saved same-site runs and a browser queue for reviewing similar pages on 2026-11-24. Comparisons preserve source evidence and coverage. Review decisions use the shared CLI format and reopen when a still-flagged pair changes.
- Stage D and Stage E, Steps 2–5 follow-up — Added local Search Console and GA4 imports, match previews and Excel downloads to the workbench on 2026-11-24. Moved pending Windows checks into the [manual audit log](MANUAL_AUDIT_LOG.md).
- Stage D, Stage F, Step 1 and Stage G, Steps 1–4 follow-up — Added browser research from user-selected exports on 2026-11-24. Results link to source rows and show capture context and sample coverage. Added the research checkpoint to the manual audit log.
- Stage D, Stage E, Steps 2–3 and Stage H, Steps 2–4 follow-up — Added saved Google API datasets to the workbook picker and local build QA to the Tools page on 2026-11-24. The QA results display static findings and selected Lighthouse, axe, screenshot and log summaries. Added both checkpoints to the manual audit log.
- Stage F, Steps 2–3 and 5 follow-up — Added public feed sampling and saved Brave datasets to browser research on 2026-11-24. Added a dataset view with source rows, downloads and request logs where available. Live provider checks are in the manual audit log.
- Stage I, Step 4 follow-up — Added reusable project audit workflows on 2026-11-24. Workflows store a target and crawl options. Runs record the workflow name and settings used. Added a Windows checkpoint to the manual audit log.
- Stage I, Step 4 follow-up — Added a noninteractive CLI for saved audit workflows on 2026-11-24. The CLI and workbench share execution and a per-workflow lock. Documented Windows Task Scheduler setup and added a manual checkpoint.
- Stage H, Step 3 follow-up — Added Chromium captures and explicit saved baselines to the workbench on 2026-11-24. The results show the screenshot, local navigation timings, baseline link and changed-pixel mask. Added Windows verification to the manual audit log.

- Stages A–C review follow-up — Improved cross-origin redirect guidance and sitemap parsing, added Python 3.13 and CI quality checks, updated FileLock, separated integration CLI commands, and added stratified calibration sampling on 2026-11-28.

## Workbench stage 1 — first session recovery

- Workbench Stage 1, Step 1 — Traced the launcher ready state, button callback and browser dispatch on 2026-11-28. The Windows URL handler now opens the bound server address and each dispatch attempt is recorded in `launcher.log`.
- Workbench Stage 1, Step 1 follow-up — Added **Copy address** beside **Open Workbench** on 2026-11-28, with clipboard confirmation and a selectable address when dispatch fails.
- Workbench Stage 1, Step 3 — Classified a feed response before parsing on 2026-11-28: empty body, HTML page, malformed XML, prohibited XML, well-formed non-feed XML, HTTP and redirect failures. The RSS/Atom root decides validity, so a valid feed with an inaccurate content type still imports.
- Workbench Stage 1, Step 4 — Added a feed failure view with the reason, the attempted source, **Edit source**, an advertised feed link and no empty downloads on 2026-11-28. URL credentials and sensitive parameters are hidden from the diagnostic copy.
- Workbench Stage 1, Step 5 — Added coverage for the launcher dispatch fallback, every feed classification, credential redaction and the workbench recovery flow on 2026-11-28. The suite passed 167 tests with Hazm and Chromium skipped.

[Current scope and remaining work](ROADMAP.md)
