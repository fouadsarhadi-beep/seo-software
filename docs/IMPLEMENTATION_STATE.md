# Implementation state

[Dated implementation log](IMPLEMENTATION_LOG.md)

## Workbench product work

The seven-stage plan in [WORKBENCH_IMPLEMENTATION_CHECKLIST.md](WORKBENCH_IMPLEMENTATION_CHECKLIST.md) sits on top of the foundation described below. Stages 1–6 are implemented; stage 7 has its source picker and is otherwise open.

- **Screens.** Project overview and task navigation; a four-view audit explorer (Overview, Findings, Pages, Exports); Search and traffic with connection state and fetch; a project review queue; comparison of two runs.
- **Exports.** A self-contained HTML report, a page spreadsheet scoped to the current filter, and a ZIP analysis bundle carrying a versioned index of grain, join keys, thresholds, coverage and skipped files.
- **Google.** Connection state per project, in-app consent with property selection, Search Console and GA4 fetches, URL inspection and disconnect, all through the same operations the CLI uses.
- **Verification.** 186 tests pass; Hazm and a missing system Chromium are the only skips. The comparison and queue paths are covered for capped samples, fixes, persistent findings, changed evidence and a server restart.
- **Known limits.** The results route re-reads `snapshot.jsonl` per request (0.2723 s for 100 pages on this machine). Review-queue priority does not use traffic data. No live Google consent or retrieval has been observed yet; the reference [capability status](CAPABILITY_STATUS.md) marks every provider action separately.
- **References.** [Audit rules](AUDIT_RULES.md) and [tools and routes](TOOL_CATALOGUE.md).

## Foundation checklist

- [x] Stage A. Installable Python package, workspace configuration, diagnostics and built-in tool catalogue.
- [x] B1. Accept explicit website, sitemap and URL-list inputs. Validate the selected origin and pin each connection to an approved address.
- [x] B2. Discover sitemaps and support an opt-in, bounded link crawl. Apply shared request and time budgets, save observations incrementally and record coverage.
- [x] B3. Produce technical and content findings, evidence references and terminal, JSON and CSV reports. Exercise the installed CLI against offline fixture sites.
- [x] C1. Route audit, crawl, offline analysis, variants, review and calibration through typed requests and a shared tool runner.
- [x] C2. Support ad hoc runs, optional projects and saved targets, transactional SQLite migrations, run history, artifact and evidence indexes and interrupted-run recovery.

## Workbench capabilities in 0.4.0

| Stage | Verified workflow | Follow-on work |
| --- | --- | --- |
| C3–C5 | Run eight technical checks on captured observations, compare same-origin snapshots and reopen changed review pairs. CLI calibration can sample both flagged and unflagged pairs. | Real review labels are needed to calibrate a site. JSON-LD supports syntax and observed types. |
| D | Run and cancel audits, read evidence, archive runs and manage projects. Start saved-snapshot checks, comparisons, review, reporting, research and build QA in the workbench. | Verify the combined workflow on Windows using the manual audit log. |
| E | Import Search Console and GA4 exports and produce a local Excel report. Every row carries a match status. Ambiguous URLs, unattributed queries and unmatched rows remain visible. | Live verification of Google consent and data retrieval, keyed performance API checks and live Sheets publication. |
| F | Normalize local CSV, TSV, XLSX, RSS and Atom. Keep source hash, column mapping, date, locale, device, import limits and row references. | Public feed and Brave Search adapters have fixture coverage. Live provider benchmarking and browser account export exchange remain open. |
| G | Normalize keywords, compare sampled competitor coverage, find shared search results, follow rank across comparable captures, collect community topics and group imported backlinks by referring host. Content plans include sample-based clusters, editorial briefs, refresh candidates and optional paired crawl evidence. | Discovery beyond selected samples and optional Ads/Trends access. |
| H | Inspect static HTML and local asset paths, import Lighthouse and axe reports, count status codes by path in common/combined access logs and compare two explicitly selected PNGs. | Read-only WordPress posts, pages, media and registered custom types are fixture-tested. Local Chromium capture, axe checks and visual comparisons are verified. Lighthouse 13.6 generated a lab report from a loopback-served build. Live WordPress authorization remains open. |
| I | An MCP stdio client can analyze or compare selected crawls and save derived local runs. It can read selected evidence, editorial decisions and reporting links. The saved workflow CLI can be invoked from Windows Task Scheduler. | Manual Windows scheduling verification and optional hosted reporting. |
| J | Profile and optimize content comparison in Python. Bundle the UI and language resources in the wheel and single-file Windows launcher. | Live audits on larger owner-provided sites and manual acceptance on Windows. |

## Verification

The latest published workbench checkpoint, `45ec331`, passed Foundation checks on Windows and Ubuntu. The review follow-up adds Python 3.13 to the matrix alongside 3.12 and runs Ruff error checks, mypy, Bandit and a locked dependency audit. Test skips are printed by reason. Hazm stays optional. [GitHub Actions run for the published checkpoint](https://github.com/fouadsarhadi-beep/seo-software/actions/runs/45386868511)

On 2026-11-28, the review changes passed 153 tests on Linux under both Python 3.12 and 3.13. Both runs skipped Hazm and reported the Starlette test-client deprecation warning. The built wheel installed into a clean Python 3.13 environment and the workflow CLI ran outside the checkout. Ruff, mypy and Bandit passed at their configured scopes. The locked dependency audit found no known advisories after the FileLock update to 4.3.2.

The offline tests use local HTTP fixtures for redirects, robots, sitemap discovery, incomplete crawls and Persian content. They also cover concurrent schema creation, recovery from interrupted runs, snapshot replay, content-aware review and history reconstruction. The workbench tests exercise an actual audit through the HTTP interface, follow a page evidence link and download a CSV. A separate Chromium run exercised the same form and download. An MCP integration test starts the installed package in a subprocess, initializes a stdio session, reads allowed evidence, rejects an unselected run and reads the results of a derived check.

Reporting tests join local analytics exports to observed pages and retain a query-only row without page attribution. Research tests compare two dated Persian SERP captures and preserve RSS evidence. Build QA tests check missing assets, import a browser report, summarize an access log and locate a changed pixel in a selected screenshot pair.

On the deterministic 600-page synthetic corpus, three runs of content preparation plus comparison had a median of 2.661 seconds with exhaustive pairing and 0.349 seconds with indexed candidate selection. Both returned 27 pairs. The index uses shared shingles, TF-IDF terms, title tokens and H1s. A regression test compares the scored results with exhaustive pairing and covers zero thresholds. This measures offline analysis on one corpus. Crawl duration and memory use on owner sites remain unmeasured. Reproduce with `python benchmarks/similarity.py` from an installed checkout.

## Stage J audit benchmark

Reproduce the larger audit with `python benchmarks/audit.py --pages 300`. It serves generated HTML over loopback and measures crawl wall time, offline analysis, report generation, SQLite indexing, the results HTTP request, and Linux peak process RSS. Use `--html-dir` to replay saved HTML responses. Results timing measures the HTTP response for the workbench results route.

| Measure | Before | After |
| --- | ---: | ---: |
| Audit wall time | 2.10 s | 1.77 s |
| Crawl wall time | 1.38 s | 1.19 s |
| Offline analysis | 0.66 s | 0.55 s |
| SQLite index writes | 19 ms | 17 ms |
| Results HTTP request | 22 ms | 22 ms |
| Peak process RSS | 105 MiB | 105 MiB |

Values are medians of three runs per version on this Linux machine. The fixture contains 300 pages and makes 302 requests including sitemap and robots discovery. The profile showed repeated HTML scans for default exclusions. The updated extractor removes those elements with one traversal and retains the existing order for custom exclusions. All ten saved Samatoos HTML responses produced identical extraction results before and after the update. Their loopback audit replay processed nine pages for comparison because one had `noindex`. Live network conditions and larger owner-site workloads remain outside these measurements.

The Python wheel and `SEO-Workbench.exe` are the distribution checkpoints. CI installs the wheel and runs QA against a local HTML file. The Windows desktop workflow checks the executable with a workspace path containing spaces and Persian characters before uploading it. A Windows x64 build was smoke-tested under Wine for startup, project creation and shutdown. Recovery from a read-only database preserved the original database, the project and a saved report. The [manual audit log](MANUAL_AUDIT_LOG.md#windows-desktop-checkpoint--stage-j-step-4) covers acceptance on the operator's Windows computer.

## Stage E handoff

Stage E1 implements read-only consent for Search Console and GA4 separately, property selection by workspace or project, and local disconnect with optional Google revocation. OAuth uses Google's installed-app library with PKCE and a loopback callback. The OS credential manager holds the refresh token and client secret. SQLite holds property metadata. Automated tests exercise the schema migration, scoped selection, and disconnect with a substitute credential store. A local Desktop OAuth client, credential manager and property owner are required for the live check. Stage E2 adds paginated Search Analytics export into the workbook's dataset format and explicit single-URL access to Google's indexed assessment. Mocked Google responses cover empty and partial exports, duplicate source rows and property boundaries. Stage E3 adds GA4 landing-page sessions and key events with web stream and session channel filters. The workbook uses an operator-supplied origin for API landing paths and records the URL basis, normalized candidate and matching tier. Mocked API and workbook tests cover quota errors, missing values, unknown origins and ambiguous canonical matches. Stage E4 adds standalone local Lighthouse import and PageSpeed Insights lab tests, plus CrUX URL and origin field queries. It uses an OS-stored key for CrUX and supports the same key for PageSpeed Insights. Local and mocked checks verify the reports. A live keyless PageSpeed request received HTTP 429, and a live CrUX check requires a key. Stage E5 adds local CSV and Excel previews for selected normalized dataset columns and publishes an approved preview to a new spreadsheet with a dedicated app-file grant. Mocked Google responses verified literal cells, successful retries and duplicate avoidance when the create outcome is unknown. A live Sheets publish still requires authorization. Stage F builds on the existing local imports with public feed retrieval and an official Brave Search adapter.

## Coverage and inputs

A live sample from samatoos.ir confirmed that a theme can place an empty `main` before the actual article. The extractor now tries usable matches in other containers after removing excluded elements, and records the selector attempts. The reported article recovered 43 words from `.entry-content`. The direct crawler connection failed from the cloud environment. Verification used ten raw HTTP responses retrieved separately and replayed through a local HTTP server. The original run's local artifacts were unavailable.

A later Windows workbench run of Samatoos reached its 100-page cap. The operator reported text extracted on all 100 HTML pages, 99 eligible for comparison and one Persian CRM article with 1,213 extracted words. This verifies the capped live run. Site-wide coverage and connected-provider checks remain open. [Manual audit log](MANUAL_AUDIT_LOG.md)


Each audit records the HTTP requests attempted and the pages actually observed. A page seen in only one snapshot can reflect a crawl limit. When older snapshots lack markup, applicable checks report partial coverage. SERP overlap uses observations with the same provider, capture date, locale and device. Rank history uses the best imported position per host and capture date, with changes between observed samples. Aggregated competitor counts describe the combined selected sample. For a single market or device, select the corresponding datasets.

The verified reporting route uses selected local files. The connected Stage E reporting milestone requires a live provider test.

[Architecture](../SEO_ANALYSIS_SOFTWARE_ARCHITECTURE.md) · [Foundation decision](adr/0001-foundation.md)
