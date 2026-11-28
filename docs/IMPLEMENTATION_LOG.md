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

## Workbench stage 2 — project-centered navigation

- Workbench Stage 2, Step 1 — Inventoried the GET screens and POST actions by task and gave each a visible parent in the shared shell on 2026-11-28. Existing run, evidence, archive, deletion, download and bookmark URLs are unchanged.
- Workbench Stage 2, Step 2 — Made the project overview the home screen on 2026-11-28. It offers project creation on an empty workspace, and for a selected project shows targets, the latest audit with coverage, saved workflows and recent project work, with one-off audits listed separately.
- Workbench Stage 2, Step 3 — Added one layout: a persistent rail with the project switcher, task navigation (Overview, Website audit, Keyword and competitor research, Search and traffic, Site QA), History and Manage saved data, plus a breadcrumb and primary action on every screen. The shell uses system fonts only, so no external resource is requested, and collapses to a single column at 900px.
- Workbench Stage 2, Step 4 — Added a dedicated Start an audit screen that explains the page cap and the local-network permission beside their fields, separated importing a source from analyzing saved sources, and replaced internal tool identifiers with task names in results, history and deletion screens.
- Workbench Stage 2, Step 5 — Added a Search and traffic landing screen that states which entries are import-ready and which need a connected property. Added coverage for the empty workspace, the selected project, two projects, an ad hoc run, task navigation and active state. The suite passed 169 tests with Hazm and Chromium skipped.

## Workbench stage 3 — exploring an audit

- Workbench Stage 3, Step 1 — Added a read model over saved audit runs on 2026-11-28 (`ui/audit_read.py`). It maps each observed page from `snapshot.jsonl` to its requested URL, final URL, HTTP status, redirect target, indexability and reason, title, word count and evidence ID, then joins `findings.json` through those evidence IDs. One finding with two evidence IDs resolves to one finding and two affected pages. Missing fields stay Unknown instead of defaulting to a value.
- Workbench Stage 3, Step 2 — Added one page query used by the table and, later, filtered exports. It combines a URL term (matching the stored and decoded forms), an HTTP status or status class, a redirect state, an indexability state and a finding rule; sorts with a stable URL tie-breaker; clamps the page; and returns total observed, total matched, bounds and a filter-preserving link.
- Workbench Stage 3, Step 2 follow-up — Captured the results-route baseline before changing it: a 100-page fixture observed 100 URLs in 102 requests and the results request took 0.2145 s.

- Workbench Stage 3, Step 3 — Rebuilt the run screen around four views on 2026-11-28: Overview leads with the site, date, status and coverage, explains a capped sample once, and groups findings by rule with occurrence and affected-URL counts. Each counter links to the page table with the filter that reproduces it.
- Workbench Stage 3, Step 4 — Added rule detail with what was observed, why it matters and what to check next, including an explicit question about intended exclusion for noindex. The Pages table shows path, status, indexability and finding links, and explains rows without page evidence. Exports carries the downloads, technical files and the offline checks form.
- Workbench Stage 3, Step 5 — Put list state in the query string, with 30-row pages, range text, bounded page numbers and a filter-preserving link. Older `q`, `url_q`, `category` and `page` bookmarks still resolve. Returning from page evidence restores the filtered view, and an invalid return target falls back to the run.
- Workbench Stage 3, Step 6 — Verified against the saved runs on disk, including a 5-page capped audit, a 100-page audit, a cancelled run with an empty snapshot, a failed feed and a 0.3.0 legacy run: every view answered 200 with no unresolved template. The 100-page fixture moved the results request from 0.2145 s to 0.2723 s, still inside the one-second local-response target.

## Workbench stage 4 — reports people and software can use

- Workbench Stage 4, Step 1 — Rebuilt the Exports tab around three outputs on 2026-11-28: a readable report, a spreadsheet of the current filter, and an analysis bundle. Each states its format, scope and purpose; outputs a run cannot produce are hidden with the reason, and the saved manifest files stay available below.
- Workbench Stage 4, Step 2 — Added a self-contained HTML report. It carries the site, date, status and completion reason, coverage, findings grouped by rule with internal anchors, example affected pages and the next check, plus embedded styling and print rules. It requests nothing external and contains no application links, so a recipient can read it with the workbench closed.
- Workbench Stage 4, Step 3 — Added a page spreadsheet export that applies the stage 3 query across every matching page rather than the visible slice, and writes the scope into the file: run, site, matching and observed counts, filters and export time. Cells pass through the existing formula guard, and the file keeps a UTF-8 BOM so Persian text opens correctly in Excel.
- Workbench Stage 4, Step 4 — Added a ZIP analysis bundle with `crawl/`, `analysis/` and `diagnostics/` groups and a versioned `index.json` describing each file's format, row grain, identifiers, join keys, missing-value rules and byte size, plus the join map, thresholds and limitations from the analysis manifest, coverage, and every skipped file with its reason. Files over 25 MB are skipped rather than truncated, and page observations are not duplicated because each repeats one snapshot record.
- Workbench Stage 4, Step 5 — Verified against the saved 5-page and 100-page runs: the report renders with no application links, the spreadsheet returns exactly 100 rows for the 100-page run with a BOM, and the bundle carries 11 files with the real threshold set and the `observations/` skip explained. Added coverage for escaping crawled text, the filtered export spanning two UI pages, and a run that cannot produce an output. The suite passed 177 tests with Hazm and Chromium skipped.

## Workbench stage 5 — Search Console and GA4 in the workbench

- Workbench Stage 5, Step 1 — Traced each Google action from its CLI parser to the shared operation on 2026-11-28: `google status`, `connect`, `disconnect`, `search-analytics`, `inspect-url`, `landing-pages`, `pagespeed`, `crux` and `publish-sheets`. The UI now calls the same `GoogleConnection` and the same tool runner the CLI uses, so a fetched dataset is written by the identical pipeline.
- Workbench Stage 5, Step 2 — Rebuilt **Search and traffic** as a working screen on 2026-11-28. It shows each provider's connected property and its identifier, or an explicit not-connected state with the exact consent command; lists saved Search Console and GA4 measurements with period, row count and status; and links recent project audits straight to their Excel report, which is where measurements join observed pages. Removing a connection states that it is scoped to this project only.
- Workbench Stage 5, Step 3 — Wired the report journey on 2026-11-28. Recent project audits link straight to their Excel report, and the picker now names any measurement whose period ends before or starts after the audit date, or whose origin differs from the audited site. The rows still join, but the operator is told the comparison describes a different picture.

- Workbench Stage 5, Step 4 — Wired fetching, inspection, disconnection and in-app consent to the shared operations on 2026-11-28. Fetch and disconnect cannot be presented as empty data: the connector's own message returns to the screen, so an expired credential reads as “Reconnect gsc to restore its credentials.” Consent runs in a background thread through the same `GoogleConnection.connect` the CLI uses; the page reports that it is waiting, then lists the properties the account can read so the operator picks one. A timed-out or rejected consent ends with the reason, not a silent failure.

- Workbench Stage 5, Step 5 — Verified with fixtures and a deterministic credential vault: consent start, property choice, the completed connection, the expired-credential fetch path, project-scoped disconnect, and two projects holding different properties. Live consent and data retrieval stay in the manual audit log until an owner runs them with real credentials. The suite passed 182 tests with Hazm and Chromium skipped.

## Workbench stage 6 — comparing audits and following up

- Workbench Stage 6, Step 1 — Made the comparison entry project-aware on 2026-11-28. It lists only runs for the selected project, preselects the two most recent, and every option states the run's date, observed count and page cap so the operator can judge comparability before generating anything.
- Workbench Stage 6, Step 2 — Classified changes from evidence rather than from URLs alone. Findings now read **new**, **persistent** or **resolved**, and a page that fell outside a capped sample reads **unassessed: outside the sample** instead of disappearing or looking fixed. Findings from runs that predate the `urls` field resolve their pages through page evidence, so an older audit still compares. Evidence links on each row point at the correct run's observation.

- Workbench Stage 6, Step 3 — Added a project review queue on 2026-11-28. A decision is stored once per project, rule and page in a new `finding_reviews` table, with the status, note, evidence reference and an evidence fingerprint. Repeating a save updates the same record. When a later audit changes that page's fingerprint the queue marks the item **needs re-review** and keeps the note; a page no longer reported is marked as such rather than silently dropped. Clearing workspace data removes the queue with the rest of the project's records.
- Workbench Stage 6, Step 4 — Verified the comparison and queue paths on 2026-11-28: different page caps, an observed fix, an unchanged issue, a page that changed after a decision, a repeated save, and a fresh server reading the persisted queue. Priority ranking informed by traffic data is not part of this pass; the queue is ordered by decision recency and shows each item's standing. The suite passed 185 tests with Hazm and Chromium skipped.

## Workbench stage 7 — keyword gaps and question trees

- Workbench Stage 7, Step 1 — Added a source picker that says what each saved dataset can answer on 2026-11-28: search-result samples support keyword overlap and competitor gaps, keyword lists carry no observed rankings, Search Console data describes the owned site's performance, backlinks are sample-limited and community sources are articles rather than rankings. The picker also states that a query absent from a sample is not proof that a site never ranks for it, and how to select two comparable samples for a gap comparison. Keyword-gap rendering already exists inside the research report's competitor section; a dedicated gap view and the question-relationship work (7.2–7.5) remain.

## Workbench documentation and inventories

- Workbench acceptance, docs — Added the reference set the plan asks for on 2026-11-28: [AUDIT_RULES.md](AUDIT_RULES.md) catalogues every crawl rule and saved-snapshot check with its evidence and coverage limits, including the three distinct link cases; [TOOL_CATALOGUE.md](TOOL_CATALOGUE.md) lists each task's entry screen, shared operation, prerequisite, example input and output, and separates the CLI-only utilities; [CAPABILITY_STATUS.md](CAPABILITY_STATUS.md) records offline, fixture-verified and live-verified status per provider action, keeping authentication, retrieval and publishing apart. Refreshed the roadmap, product plan, implementation state and README so they describe the delivered workbench instead of the pre-workbench plan. The audit overview now surfaces how many saved-snapshot checks are available and links to them.

- Workbench Stage 7, Step 2 (partial) — Split the competitor report into three evidence-scoped sets on 2026-11-28: shared with the owned site, owned sample only, and competitor sample only. The computation moved into `competitor_gaps` so it is unit-tested directly, and the page states that "owned sample only" means the competitor was not seen for that query in these captures, not that it never ranks. Still open in 7.2: an explicit warning when the selected samples differ in provider, locale or device, and an add-to-brief action from a gap row.

- Workbench Stage 7, Step 2 follow-up — Warned when the selected search samples are not comparable on 2026-11-28. The research report detects two or more SERP sources whose provider, locale or device differ and states that rank history and gaps stay within each capture, so a difference between them is not a ranking change. The last open part of 7.2 is an add-to-brief action from a gap row; that needs a product decision about what a brief is before it is built.

- Workbench Stage 7, Step 3 — Added a question-relationship import on 2026-11-28. A file needs `parent` and `child` columns (aliases accepted, `seed` optional); each row is validated separately, incomplete rows are counted as skipped, and an identical parent-child edge appearing twice collapses into one relationship while a child under two different parents stays as two. Original spelling is preserved, and the saved source keeps provider, locale and observation date. A file missing the relationship columns is rejected with the missing names. The preview is the saved dataset view, which lists the kept relationships and reports both the skipped and collapsed counts; a pre-commit preview is not built.

- Workbench Stage 7, Step 4 — Built the question outline on 2026-11-28. A question dataset lists its seeds (named seeds when the source has them, otherwise the roots no edge points at); choosing one expands that branch into a nested, screen-reader-navigable list with each question in its own direction so Persian renders right to left. Children are capped per question with an explicit "Show more", a question that repeats on its own path is marked as a cycle instead of expanding again, and every row links back to the source row it came from. The visible branch exports as CSV with parent, child and source row, and that export re-imports with its parent relationships intact (tested).
- Workbench Stage 7, Step 5 (partial) — Verified with a Persian fixture covering duplicate edges, a child under two parents and a cycle, plus the branch-export round trip. Still open: comparing two dated captures of the same tree side by side, and exporting an arbitrary user-selected subset rather than the expanded branch.

## Workbench acceptance — interrupted work, backup and responsiveness

- Workbench acceptance, Step 3.6 — Verified recovery on 2026-11-28 in `tests/test_interrupted.py`. A run stays discoverable in history after the client abandons the job; cancelling keeps what was already observed and a retry creates a distinct run instead of overwriting; a manifest left `running` by a crash is reconciled by `reindex` into `partial` with the finalization warning and a rebuilt snapshot; and a second submission while an audit is running is refused with 409 rather than creating a duplicate job.
- Workbench acceptance, Step 4.5 — Documented the stopped-app backup and restore procedure in the README: finding the paths, what to copy, restoring to a different location, `history reindex`, and which credentials must be reconnected because a Google connection is keyed to the data-directory path. Followed it on a disposable copy of the workspace: reindex found 3 runs, and the overview, a page-evidence page and a saved file all answered 200 from the restored copy. Measurements: a 300-page fixture renders the results route in 0.4667 s; a 100-page run answers its overview, the first page table and its last page in 0.044–0.049 s warm. Every measured local response stays inside the one-second target.

- Workbench Stage 7, Step 2 — Completed the gap-to-brief loop on 2026-11-28. A query in a gap row (and in a keyword cluster) now carries a small **Brief** action that collects it into a project-level content brief stored in the database, one row per project and query, so adding the same query again updates its note instead of duplicating. A **Content brief** screen adds, lists and removes items and links each back to the research run that produced it; clearing workspace data removes them. Scope travels with the exported `research.json`, which keeps each source's provider, locale and device, so the gap can be re-read without the workbench.

- Workbench Stage 7, Step 5 — Completed the question work on 2026-11-28. The outline can be compared against an earlier capture of the same seed: it reports how many question links appeared, how many were no longer observed and how many persist, listing the ones that dropped out, and states that a missing question is a property of the sample rather than proof it stopped being asked. Every question in the outline also carries a **Brief** action, so a chosen question joins the project brief. Verification used a Persian fixture covering duplicate edges, a child under two parents, a cycle, two observation dates and an empty seed column, plus the branch export being re-imported with its parent relationships intact.

## DS delivery plan — batch 1: finding comparison and review standing

- Batch 1 — Reproduced the defect before changing anything: on `f68c6f5` a finding whose page the capped follow-up never reached was reported as `resolved`. Finding identity is now the rule plus its affected page identities, so a changed redirect destination or pair detail is one **changed** issue carrying the previous detail, not a resolution plus a new one. A finding is only **resolved** when the later crawl could actually run that rule on every page it depends on — markup-dependent rules need captured markup and the content rules reject truncated extraction — and otherwise reads **unassessed** with the reason; an earlier unassessed page can no longer prove a **new** problem. The page summary, finding table and finding CSV all read these same states.
- Batch 1 — Review standing now asks the database for the latest audit of the project **and the target that review belongs to**, so 25 intervening imports and a newer audit for a second target leave the verdict untouched. A page fingerprint includes the final URL, so a changed redirect destination reopens the review.
- Batch 1 — Focused regression: 36 tests across comparison, the read model and the workbench, replacing the old test that asserted the false resolution. Full locked CI (Ruff, mypy, Bandit, matrix) is deferred to batch 7 as the plan requires.

## DS delivery plan — batch 2: project context from click through storage

- Batch 2 — The rail now carries the selected project into every task link (audit, research, traffic, Site QA, review queue, brief), so opening a tool from Beta keeps Beta selected instead of silently reverting to the first project.
- Batch 2 — Research imports, feed samples and research runs accept the submitted project and record it on the run, so their datasets and reports belong to that project. A dataset owned by another project is refused before any work starts.
- Batch 2 — The content brief validates its destination instead of writing under an unknown name, and the question explorer collects into the project it was opened from rather than the workspace's first project. An unknown project now produces a recoverable 400 rather than a silent workspace-level record; the Google fetch, inspect and disconnect routes use the same check.
- Batch 2 — Acceptance test drives the Beta journey end to end: rail links carry Beta, the research screen posts Beta, a brief item lands only in Beta, an unknown project is rejected, a research run is recorded under Beta, and a dataset owned by Alpha is refused. Ad-hoc auditing is unchanged.
- Batch 2 — Not covered in this pass: pickers still list workspace-wide datasets (compatibility is enforced on submit, the list is not scoped), shared dataset rows do not yet label their owning project, and collecting a one-off run into a project still defaults rather than asking explicitly.

## DS delivery plan — batch 3: report and feed protections

- Batch 3 — Bundle reads now go through one resolver that applies the same rules as the run-file handler: a candidate must be a plain file inside the run directory and listed in the run manifest (with `run.json` as the single explicit exception). A link is not followed, a file the run never wrote is reported as skipped with its reason, and an unlisted file is refused rather than packaged.
- Batch 3 — A signed feed address is now transient. `FeedInput` declares which of its parameters must not be written down, the runner honours that hook for any request that provides it, and the feed tool stores the redacted address in `dataset.json` and in the request log. Existing runs keep their stored original, while the dataset view, source-row view and research report redact the address when displaying it.
- Batch 3 — A failed feed now says that parameters were removed from the address shown and that a signed address must be pasted again in Edit source.
- Batch 3 — Focused regression: bundle entry rules, unlisted and missing files, a successful signed feed and a failed signed feed, plus the existing workbench and source suites. The symlink refusal is covered by a test that skips on machines where creating a link needs elevation, so it stayed unverified here.

## DS delivery plan — batch 4: question captures, bounds and export

- Batch 4 — The seed is now the capture topic. Rows are grouped by their seed, so two topics that share a parent–child edge stay separate and an update under one topic leaves another untouched; a seed that is only a heading, with no supplied edge from it, shows the questions observed under that capture and is marked as a topic heading rather than an edge.
- Batch 4 — Traversal is bounded. Children per question default to 50 and can be raised to 200, total rendered nodes stop at 200, depth stops at 6, and a node that stopped early is marked so the outline never truncates silently.
- Batch 4 — The branch export carries the seed, applies spreadsheet-formula protection to every cell so a question beginning with `=` cannot execute, and re-imports with its parent links intact.
- Batch 4 — The bundle's link guard now has a deterministic test instead of skipping on machines where creating a symlink needs elevation.
- Batch 4 — Comparison is restricted to compatible captures: only another capture of the same seed for the same project, provider and locale is offered; the panel names both dates and the direction of change; a seed absent from the compared capture says so; captures whose provider or locale is unrecorded are marked as of unknown comparability; and excluded captures are counted so their absence is explained.
- Batch 4 — The Persian fixture now runs through the real UI import and explorer: a shared child under two parents, a path-local cycle, a deep branch and 55 siblings all render, and the sibling cap is reachable by raising the limit. Roots in the same capture that the chosen seed does not reach are listed separately, so a branch cannot be silently unreachable.
- Batch 4 — The transient-secret hook is documented as general: only a feed request carries a signed address, while every other connector keeps its secret in the OS credential store and puts only identifiers in the request.

## DS delivery plan — batch 5: brief provenance

- Batch 5 — Collect and Edit are now separate actions. Collecting a query creates the item once, records the run and source row it came from, and never overwrites an edited note; **Save note** edits the human decision on its own. The brief screen lists every source with a link to its row and a **Remove source** action, so removing one leaves the decision and the remaining evidence readable.
- Batch 5 — Sources are validated: collecting from a run that no longer exists is refused with a recoverable error instead of filing a broken reference.
- Batch 5 — The migration adds `brief_sources` and backfills each existing item's stored source, so earlier briefs keep their notes and gain provenance rather than being rewritten.
- Batch 5 — Gaps are computed inside each capture. Queries are grouped by provider, locale, device and date, and each capture reports its own shared, owned-only and competitor-only sets with its scope named in the heading. When more than one capture is present, the report states that no combined gap is shown, because a query seen on desktop in one sample and on mobile in another cannot establish a shared ranking; the legacy combined table is kept only as a single labelled capture.
- Batch 5 — The acceptance case is proven at tool level: a desktop-only owned result and a mobile-only competitor result produce two captures and no shared query at all.
- Batch 5 — A brief source whose run has since been deleted is shown as **unavailable** with its short run id, and the note stays readable.

## DS delivery plan — batch 6: launch, navigation and recovery

- Batch 6 — Old bookmark semantics are restored on an audit run: `?page=2` and `?evidence_page=2` both open the page table at page two, `?q=` filters findings again (rule id, label or detail) instead of being read as a URL search, and `?url_q=` still filters pages. `?category=` continues to open findings.
- Batch 6 — A known indexing exclusion is now distinct from an unknown verdict. `not_indexable_status` is filtered as **Excluded by HTTP status** in the page table, the overview links and the filtered spreadsheet, while **Unknown** means the directive genuinely could not be read.
- Batch 6 — Interrupted runs are recoverable from a discoverable action: **Manage saved data → Recover interrupted runs** reuses the existing reindex, reports how many runs it recovered, and leaves completed runs and active writers alone. Startup still runs only a writable check, not a workspace rebuild.
- Batch 6 — The everyday `seo.bat` and `SEO-Workbench.bat` now pass `--config-file` for the project-local `.seo-workbench` workspace when it exists, so the CLI, the browser launcher and `Start SEO Workbench.cmd` share one history instead of the launcher writing to a different workspace.
- Batch 6 — Verified by test: page-two and evidence-page bookmarks, a findings search, the exclusion filter and the filtered CSV. The actual Windows launch from a path with spaces and Persian text stays owner-pending until observed.

[Current scope and remaining work](ROADMAP.md)
