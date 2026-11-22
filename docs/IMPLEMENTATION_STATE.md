# Implementation state

[Dated implementation log](IMPLEMENTATION_LOG.md)

## Foundation checklist

- [x] Stage A. Installable Python package, workspace configuration, diagnostics and built-in tool catalogue.
- [x] B1. Accept explicit website, sitemap and URL-list inputs. Validate the selected origin and pin each connection to an approved address.
- [x] B2. Discover sitemaps and support an opt-in, bounded link crawl. Apply shared request and time budgets, save observations incrementally and record coverage.
- [x] B3. Produce technical and content findings, evidence references and terminal, JSON and CSV reports. Exercise the installed CLI against offline fixture sites.
- [x] C1. Route audit, crawl, offline analysis, variants, review and calibration through typed requests and a shared tool runner.
- [x] C2. Support ad hoc runs, optional projects and saved targets, transactional SQLite migrations, run history, artifact and evidence indexes and interrupted-run recovery.

## Local workbench checklist for 0.3.0

| Stage | Verified workflow | Follow-on work |
| --- | --- | --- |
| C3–C5 | Run eight technical checks on captured observations, compare same-origin snapshots, reopen changed review pairs and invoke offline tools by workspace run ID. | JSON-LD covers syntax and observed types. Rich-result eligibility requires additional rules. |
| D | Run and monitor a website audit through a loopback browser UI, cancel acquisition and inspect completed observations, review history, drill into evidence, download files and manage projects and targets. | Research, build QA and reporting are launched from the CLI. Their results appear in history. |
| E | Import Search Console and GA4 exports and produce a local Excel report. Every row carries a match status. Ambiguous URLs, unattributed queries and unmatched rows remain visible. | Live verification of Google consent and data retrieval, keyed performance API checks and Sheets publication. |
| F | Normalize local CSV, TSV, XLSX, RSS and Atom. Keep source hash, column mapping, date, locale, device, import limits and row references. | Provider benchmarking, permitted live feed retrieval and the browser account export adapter. |
| G | Normalize keywords, compare sampled competitor coverage, find shared search results, follow rank across comparable captures, collect community topics and group imported backlinks by referring host. Brief candidates link to the observed pages. | Broader topical clustering, completed editorial briefs, refresh prioritization and selected competitor page analysis. |
| H | Inspect static HTML and local asset paths, import Lighthouse and axe reports, count status codes by path in common/combined access logs and compare two explicitly selected PNGs. | WordPress REST authorization, automated browser capture and generating fresh Lighthouse/axe measurements. |
| I | An MCP stdio client can inspect selected run evidence and invoke an offline check. Derived results are readable in the same session. Excel reports may reference an existing Looker Studio URL. | Hosted reporting connectors, scheduled jobs and agent-assisted editorial decisions. |
| J | Profile and optimize content comparison in Python. Build an installable wheel with bundled UI and language resources. | Windows runtime execution, evaluation on larger owner-provided sites and any standalone executable. |

## Verification

On Linux with CPython 3.12.14, the checkout and an isolated installation of the 0.3.0 wheel each passed 108 tests. Each run skipped the optional Hazm test and reported a Starlette test-client deprecation warning. The isolated CLI also completed dataset import, keyword research and static build inspection outside the checkout. The Stage D cancellation follow-up passed 109 tests on Linux with the same optional skip and deprecation warning. A regression test interrupts a 30-second retry wait and opens the completed observation from the cancelled run. Chromium again passed the normal audit, evidence and export flow. The Windows CI job awaits execution.

The offline tests use local HTTP fixtures for redirects, robots, sitemap discovery, incomplete crawls and Persian content. They also cover concurrent schema creation, recovery from interrupted runs, snapshot replay, content-aware review and history reconstruction. The workbench tests exercise an actual audit through the HTTP interface, follow a page evidence link and download a CSV. A separate Chromium run exercised the same form and download. An MCP integration test starts the installed package in a subprocess, initializes a stdio session, reads allowed evidence, rejects an unselected run and reads the results of a derived check.

Reporting tests join local analytics exports to observed pages and retain a query-only row without page attribution. Research tests compare two dated Persian SERP captures and preserve RSS evidence. Build QA tests check missing assets, import a browser report, summarize an access log and locate a changed pixel in a selected screenshot pair.

On the deterministic 600-page synthetic corpus, three runs of content preparation plus comparison had a median of 2.661 seconds with exhaustive pairing and 0.349 seconds with indexed candidate selection. Both returned 27 pairs. The index uses shared shingles, TF-IDF terms, title tokens and H1s. A regression test compares the scored results with exhaustive pairing and covers zero thresholds. This measures offline analysis on one corpus. Crawl duration and memory use on owner sites remain unmeasured. Reproduce with `python benchmarks/similarity.py` from an installed checkout.

## Stage E handoff

Stage E1 implements read-only consent for Search Console and GA4 separately, property selection by workspace or project, and local disconnect with optional Google revocation. OAuth uses Google's installed-app library with PKCE and a loopback callback. The OS credential manager holds the refresh token and client secret. SQLite holds property metadata. Automated tests exercise the schema migration, scoped selection, and disconnect with a substitute credential store. A local Desktop OAuth client, credential manager and property owner are required for the live check. Stage E2 adds paginated Search Analytics export into the workbook's dataset format and explicit single-URL access to Google's indexed assessment. Mocked Google responses cover empty and partial exports, duplicate source rows and property boundaries. Stage E3 adds GA4 landing-page sessions and key events with web stream and session channel filters. The workbook uses an operator-supplied origin for API landing paths and records the URL basis, normalized candidate and matching tier. Mocked API and workbook tests cover quota errors, missing values, unknown origins and ambiguous canonical matches. Stage E4 adds standalone local Lighthouse import and PageSpeed Insights lab tests, plus CrUX URL and origin field queries. It uses an OS-stored key for CrUX and supports the same key for PageSpeed Insights. Local and mocked checks verify the reports. A live keyless PageSpeed request received HTTP 429, and a live CrUX check requires a key. The next step is selected exports and Google Sheets publication.

## Coverage and inputs

A live sample from samatoos.ir confirmed that a theme can place an empty `main` before the actual article. The extractor now tries usable matches in other containers after removing excluded elements, and records the selector attempts. The reported article recovered 43 words from `.entry-content`. The direct crawler connection failed from the cloud environment. Verification used ten raw HTTP responses retrieved separately and replayed through a local HTTP server. The original run's local artifacts were unavailable.


Each audit records the HTTP requests attempted and the pages actually observed. A page seen in only one snapshot can reflect a crawl limit. When older snapshots lack markup, applicable checks report partial coverage. SERP overlap uses observations with the same provider, capture date, locale and device. Rank history uses the best imported position per host and capture date, with changes between observed samples. Aggregated competitor counts describe the combined selected sample. For a single market or device, select the corresponding datasets.

The verified reporting route uses selected local files. The connected Stage E reporting milestone requires a live provider test.

[Architecture](../SEO_ANALYSIS_SOFTWARE_ARCHITECTURE.md) · [Foundation decision](adr/0001-foundation.md)
