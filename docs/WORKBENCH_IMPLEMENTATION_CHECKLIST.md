# Workbench implementation checklist

**Status on 2026-11-28:** planned. Start at **1.1**. These numbers expand the six stages in the [product plan](WORKBENCH_PRODUCT_PLAN.md). Stage 7 expands its research follow-up. The first release target is stages 1–4: launch, crawl, investigate, share. The second is stages 5–7: explain performance, track decisions, explore opportunities.

## How to pick up the work

Take the first unchecked implementation item whose dependency is complete. Read its named entry points and their callers. Implement through the normal UI and reuse the operation behind the CLI. Mark an item complete in the same commit as the working change. In the [implementation log](IMPLEMENTATION_LOG.md), record stage, step, result and date. At the end of each stage, run its grouped checks and append the owner walkthrough to the [manual audit log](MANUAL_AUDIT_LOG.md). Mark Windows or live provider checks pending until an owner reports the result. Independent offline stages can proceed while those checks are pending.

Use the current FastAPI/Jinja UI, project-local workspace and run manifests. All proposed screens below can be server-rendered. Existing POST actions retain token validation, and downloads retain manifest-based access. Preserve direct run, evidence, archive, deletion and CLI entry points. A stage that introduces stored data must cover restart, old workspaces and deletion of the new data through the existing management flow.

## Why these screens

| Reference pattern | Implementation decision |
| --- | --- |
| Ahrefs Page Explorer offers presets that narrow a crawl to relevant URLs. | A summary count is a link to its exact table query. A user can add another filter, inspect evidence and return to the same rows. [Ahrefs Page Explorer](https://ahrefs.com/academy/how-to-use-ahrefs/site-audit/page-explorer) |
| Semrush leads from an issue to an explanation and a list of affected pages. | Each rule has an observation, reason to care, next check and evidence. Keep a finding count distinct from its affected URL count. [Semrush Issues](https://www.semrush.com/kb/541-site-audit-issues-report) |
| Semrush exports the data appropriate to the report being viewed. | Put Export matching pages by the table, and Full audit report on the overview. State the scope inside both files. [Semrush audit exports](https://www.semrush.com/kb/905-exporting-site-audit) |
| Ahrefs allows inspection of changes between two crawls down to a single URL. | Show both observations and their coverage. Partial crawls require an unassessed state. [Ahrefs crawl comparison](https://help.ahrefs.com/en/articles/5192078-how-to-compare-changes-between-two-crawls-in-site-audit) |
| Semrush Keyword Gap compares terms across domains. AlsoAsked shows relationships between questions. | Use compatible domain samples for overlap. Require observed parent–child relationships for question trees. Every result links to its source. [Semrush Keyword Gap](https://www.semrush.com/kb/28-keyword-gap) · [AlsoAsked](https://alsoasked.com/faqs) |

## Stage 1 — Make the first session recoverable

Entry points: `desktop.py`, `research/sources.py:read_feed`, `ui/server.py` at `/tools/research/feed`, `ui/research.html` and the failed-run view. Source paths in this document are relative to `src/seo_analysis/`.

- [ ] **1.1 Trace Open Workbench.** Follow server-ready notification, enabled button, click callback and browser dispatch. Record the chosen method and any OS error in the project launcher log. Use the bound server address for every open action. Preserve double-click startup and shutdown.
- [ ] **1.2 Implement a Windows launch fallback.** Once ready, use the Windows default URL handler for the loopback HTTP URL. Keep the existing cross-platform opener elsewhere. Put Copy address beside Open Workbench, give clipboard confirmation, and keep the URL selectable on dispatch failure. Reopening the browser uses the running server.
- [ ] **1.3 Classify feed responses before parsing.** Preserve existing fetch, robots, redirect and size limits. Classify failed request, HTTP error, empty body, HTML, malformed XML and well-formed unsupported XML. Verify the RSS/Atom root so a valid feed with an inaccurate content type still works. Where HTML advertises a feed, display a validated candidate that the user can select.
- [ ] **1.4 Close the recovery loop.** Call this action “Import articles from RSS or Atom”. Show what input it takes and what an article sample contains. On failure, display a short reason and Edit source, retain project context, redact URL credentials and sensitive parameters in diagnostics, and hide empty exports. A failed run remains available in History.
- [ ] **1.5 Verify together.** Extend `test_desktop.py`, `test_research_sources.py` and the relevant `test_ui.py` flow. Cover dispatch error, repeated click, HTML served with status 200, valid Atom, malformed XML and an empty feed. Owner: start the CMD file, close the browser tab, reopen from the small window, then try a homepage and its real feed.

## Stage 2 — Make navigation project-centered

Depends on the stage 1 entry points. Start in `ui/server.py`, `ui/workbench.html`, `ui/research.html`, `ui/workbook.html` and `app/workflows.py`.

- [ ] **2.1 Map existing routes to tasks.** Inventory GET pages and POST actions for projects, targets, workflows, audit jobs, results, research, workbook, QA and history. Assign each one a visible parent and a return destination. Keep `POST /audit`, job progress and saved run URLs working.
- [ ] **2.2 Build the project overview.** On first launch offer Create project and Run a one-off audit. With projects present, show a project list or explicit selection. The selected project shows target, Start audit, latest audit coverage and recent project work. Pass the selected project with links and validate on submission. A one-off run stays ad hoc.
- [ ] **2.3 Establish the layout once.** Use a consistent project selector, task navigation, page title, primary action and breadcrumb. Website Audit, Research, Search & Traffic and Site QA each get a landing screen. Keep History and Manage saved data reachable. Preserve keyboard focus, native links and readable mixed Persian/Latin URLs at narrow widths.
- [ ] **2.4 Clarify inputs and empty states.** Put project creation fields behind Create project, targets under their project, audit settings under Start audit. Explain the page cap and local/staging permission beside their fields. Separate Import a source from Analyze saved sources. Give an empty tool one example and one usable next action.
- [ ] **2.5 Verify together.** Exercise empty workspace, two projects with different runs, ad hoc run, archived run link and direct bookmark. Owner: choose the right tool for a crawl, an article feed and a traffic import using only the labels.

## Stage 3 — Explore an audit from a finding down to a page

Depends on 2.3. Today `GET /runs/{rid}` in `ui/server.py` filters findings and URL strings in memory and slices each into groups of 30. Different tools share that dispatcher. Isolate the audit branch before changing it. Keep checks and research result rendering covered.

- [ ] **3.1 Define a read model against saved runs.** Inspect current and older manifests, stored evidence, inventory, findings and snapshot. Map requested URL, observed destination, HTTP status, indexability and reason, finding rule/category, evidence ID and run ID to their actual sources. Record one row per observed page; join findings through evidence IDs. One overlap finding with two evidence IDs yields one finding and two affected pages. Missing fields display Unknown. Keep stored URL identity, including encoded separators.
- [ ] **3.2 Build one query for the page table.** Accept URL text, HTTP status/class, redirect, indexability, finding rule, sort and page. Combine filters with AND; validate allowed values. Match decoded display text as well as original URLs. Apply filters, count matches, stable-sort with a unique tie-breaker, then slice 30 rows. Return total observed, total matched and page bounds. Reuse this query for presets and filtered exports.
- [ ] **3.3 Build Overview.** At the run URL show site, date, status and coverage first. Explain a 100-page cap once. Group findings by rule and category with separate occurrence and URL counts. Make page-level counters clickable only where the destination can reproduce the count. Put request totals and discovery diagnostics under run details.
- [ ] **3.4 Build Findings and Pages.** Link Overview / Findings / Pages / Exports within the run. Rule detail opens with observed behavior, why it matters, next check and matching URLs. For noindex, ask whether exclusion was intended. On Pages show path, status, indexability and findings; link rows to existing evidence and show redirect destinations. When a row has missing evidence, explain the gap.
- [ ] **3.5 Finish list navigation.** Persist tab, filters, sort and page in GET parameters. Preserve older bookmarked searches using `q`, `url_q`, `category`, `evidence_page` and `page`. At the bottom show range, matched count, previous/next and bounded page numbers. Reset page on filter change, clamp out-of-range pages and offer Clear filters on zero matches. Return from evidence to the same list using validated local state.
- [ ] **3.6 Verify together.** On a fixture shaped like the owner's audit, “2 redirecting” opens exactly two observed source URLs. A pair finding resolves to both pages. Use the last page of an unfiltered 100-page run (rows 91–100), then filter and use Back. Check a one-page run, older run with unknown fields and failed run. Time the larger repo benchmark fixture before and after; if list rendering is slow, profile the reads before adding indexes.

## Stage 4 — Deliver human reports and a reusable data bundle

Depends on 3.1–3.5. Start in `reporting/report.py`, `reporting/workbook.py`, `reporting/dataset_export.py`, `core/artifacts.py` and the existing run-file handler.

- [ ] **4.1 Design the Exports tab.** Lead with “Read audit report” (offline HTML), “Work with pages” (spreadsheet), and “Download analysis bundle” (ZIP). Give format, scope and purpose. Keep existing manifest downloads available in details. Hide outputs that cannot be produced and explain older-run limitations.
- [ ] **4.2 Implement the standalone report.** Include site and date, completion reason, coverage, top issues, affected page examples and next checks. Escape crawled text and URLs. Use embedded styling and internal anchors for supporting rows so a recipient can read it without the workbench running.
- [ ] **4.3 Implement the table export.** Use the stage 3 query across all matching pages. Include original and destination URLs, HTTP status, reason for exclusion, rule references and scope metadata. Keep formulas inert and preserve Persian text. Retain the existing multi-source Excel workbook as a separate reporting task.
- [ ] **4.4 Implement the machine bundle.** Package manifest-approved artifacts under crawl, analysis and diagnostics. Include a versioned index describing file paths, formats, row grain, identifiers, join keys, units, missing values, thresholds, coverage and skipped files. Where artifacts lack a common join key, include an explicit mapping. Stream or write atomically to avoid serving half-written exports. Keep logins, tokens and unrelated workspace data outside the bundle.
- [ ] **4.5 Verify together.** Reconcile counts across Overview, HTML, workbook and ZIP. Open the HTML offline and the workbook in Excel. Use the index alone to trace one finding to evidence. Exercise a filtered export spanning two pages, missing legacy artifacts, unsafe filenames and repeated download. Existing run history remains readable.

## Stage 5 — Bring Search Console and GA4 into the workbench

Depends on the project navigation and existing workbook flow. Start with `cli_integrations.py`, `connectors/{google,search_console,gsc,ga4}.py`, `ui/workbook.html` and `/runs/{rid}/report`.

- [ ] **5.1 Map UI actions to existing operations.** Trace google status/connect/disconnect, search-analytics, inspect-url and landing-pages from CLI parsing to provider calls and stored datasets. Have the UI call the shared application operation. Make the existing credential scope explicit, especially where disconnect affects other projects.
- [ ] **5.2 Ship the offline Search & Traffic screen.** Offer Search Console queries/pages for search visibility, GA4 landing pages for visits, and URL Inspection for one URL's recorded Google status. Show site/property, date range, source type and last import. Without a connection offer import wherever supported.
- [ ] **5.3 Wire the report journey.** Select a project audit, compatible saved datasets or a file, preview matching and unmatched rows, then open the existing workbook. Preserve query-only rows, GA4 path origin, missing versus zero, multiple match candidates and original source-row references. Warn when scope or dates do not align.
- [ ] **5.4 Wire authenticated actions.** Reuse existing read-only consent and credential storage. Select property, dates and operation before fetching, show progress or recoverable failure, then persist the returned dataset through the same pipeline as the CLI. Present permission denied, expired consent, no rows and partial coverage separately. Keep publishing to Sheets an explicit later action.
- [ ] **5.5 Verify together.** Use provider fixtures and existing Google, GA4 and workbook tests. Trace a landing page to sessions and a query to clicks. Switch projects and verify the selected property. Owner can complete the offline walkthrough immediately. Log live consent, property discovery, data retrieval and Sheets separately when credentials are available.

## Stage 6 — Compare audits and follow up findings

Depends on stages 2–3; traffic context uses stage 5 when available. Reuse `/compare`, `ui/comparison.html`, `analysis/checks.py`, `analysis/review.py` and existing pair decisions.

- [ ] **6.1 Choose comparable runs.** Start from a project/target, preselect the latest two compatible audits and let the user change either. Display dates, limits, observed counts and which checks ran before generating a comparison.
- [ ] **6.2 Define changes using evidence.** Both crawls assessed a page/rule: show new, persistent or resolved as appropriate. Missing observation or unavailable check: show unassessed and the reason. A changed URL or redirect destination retains the recorded identities. Link each side to evidence from the correct date.
- [ ] **6.3 Add a review queue.** Start from an issue or page; save status, note, project, rule, affected page identities and evidence reference. Reuse pair review for pairs. For other findings define a stable identity and evidence fingerprint. Repeated saves update the same decision; changed evidence reopens review while retaining the prior note. Scope queue records to their project and integrate with cleanup.
- [ ] **6.4 Verify together.** Compare different caps, an observed fix, an unchanged issue and a changed pair. After restart verify the queue and note. With traffic data show its source/date beside priority; without data use observable severity and affected pages. Owner: follow one fix through two saved runs.

## Stage 7 — Make research actionable with keyword gaps and question trees

Depends on stage 2 and existing research datasets. Can follow stage 5 offline work without waiting for live credentials. Entry points: `research/imports.py`, `research/intelligence.py`, `research/content_plan.py`, `ui/research.html` and the source-row route.

- [ ] **7.1 Add a source picker.** Show dataset type, domain, date, locale, device and row count. Explain whether it supports keyword overlap, article discovery or question relationships. Offer an example import for each new format. A feed remains a source of articles.
- [ ] **7.2 Build keyword gap.** Select owned and competitor samples; check locale, date, device and source compatibility. Group comparable normalized queries while retaining original strings and provenance. Offer Shared, Owned sample only and Competitor sample only. Include scope in labels and exports. Pick a query to inspect contributing source rows or add it to a brief.
- [ ] **7.3 Import question relationships.** Require seed, parent and child; preserve source row, locale, country and observation date. Validate rows individually with a preview and explicit skipped-row count. Preserve original Persian spelling for display. Deduplicate identical edges within a source, retain provenance across samples and preserve multiple parents. Flat keyword imports open as lists.
- [ ] **7.4 Build Explore questions.** Choose seed and dataset, expand one branch at a time, provide an accessible outline and RTL display, and detect cycles on the current traversal path. Limit expansion per page with a visible “show more” action. Selecting a question opens the source. Export selected edges or add selected questions to an existing editorial brief. Leave a live question provider for a later integration.
- [ ] **7.5 Verify together.** Use a Persian fixture with duplicate edges, a child shared by two parents, a cycle, two dates and an empty seed. Re-import the branch export and recover its parent relationships. Use asymmetric keyword samples and confirm an absent query is described only within the selected sample.

## Release walkthrough

Run the existing CI suite at release checkpoints using the locked environment in `.github/workflows/test.yml`. Windows and Ubuntu cover installation and regression checks. The owner supplies the real browser, Excel, live site and consent checks. Record the commit, run IDs, fixture or live source, expected result and actual result in the manual log. Never substitute synthetic provider data for a live verification.

- [ ] **Release 1, after stage 4.** Double-click the launcher, choose the project, run a capped audit, open a grouped finding, filter pages, inspect one page and return, then share the offline report and reconstruct that finding from the bundle.
- [ ] **Release 2, after stage 7.** Import search and traffic data, trace a metric to its source, compare two audits, save a decision, select a competitor opportunity and turn a question branch into a brief. Record unresolved owner checks beside their stage.
