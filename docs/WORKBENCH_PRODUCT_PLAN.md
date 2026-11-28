# Workbench product plan

[Step-by-step implementation checklist](WORKBENCH_IMPLEMENTATION_CHECKLIST.md)

Proposed 2026-11-28. All steps below are pending. Deliver one stage at a time and record the result in the implementation log. Add each stage's owner checks to the manual audit log when its build is ready.

The first useful session should let someone choose a site, run an audit, understand its coverage, inspect an affected page and save a report. Returning users should be able to see what changed. Build this journey on the existing run history, evidence, imports and analysis routines. Keep older run links working.

## 1. Repair the two reported failures

1. Trace the launcher's ready state and button callback on Windows. The working address confirms the server started on the reported machine. The callback currently returns on a successful webbrowser.open call, which cannot confirm a visible browser window. Try the Windows default URL handler, surface launch errors in the existing log and put Copy address next to Open Workbench. Both should use the actual server URL.
2. Trace the feed run through fetch and parsing. The reported XML error alone cannot identify the response. Distinguish an HTTP failure, empty response, HTML homepage and malformed or unsupported feed. Show the attempted source with sensitive URL parameters omitted, a short explanation and an Edit source action. For HTML, offer an advertised RSS/Atom link when available and apply the existing fetch rules to it. Hide empty downloads on failure.
3. Checkpoint: on Windows click Open Workbench twice after startup and exercise Copy address. Try a valid RSS feed, Atom feed, homepage, empty body and malformed XML. A failed import should retain enough context to correct it without recreating the project.

## 2. Give each tool a clear place

1. Make the project overview the home screen. Show the active website, Start audit, latest audit with coverage, and recent work for this project. Preserve an explicit ad hoc audit path.
2. Organize navigation by task: Website audit, Keyword & competitor research, Search & traffic, and Site QA. Keep project settings, connections and history within reach. Replace internal tool IDs in primary headings with task names. Keep run IDs in details.
3. Give each tool a short purpose, required input, example and expected output. Separate acquiring data from analyzing saved data. For example, label the feed action “Import competitor articles from RSS/Atom”; give keyword research its own start action with a choice of compatible datasets or file import.
4. Checkpoint: starting with an empty project, find the crawler, import competitor articles and identify how to analyze a keyword export. From a populated project, resume a previous result without launching another job.

## 3. Make a large audit navigable

1. Split the result into Overview, Findings, Pages and Exports. Lead with completion or limits, coverage and grouped issues. Explain partial runs in one sentence. Keep detailed counters available. Give zero findings, no pages and incomplete coverage distinct messages.
2. In Findings, group by rule and severity, show affected page counts and open the matching URLs. In Pages, replace the URL list with a table showing path, HTTP status, indexability and findings count. Search by URL or path and combine filters for status, redirects, indexability and finding type. Show unknown values explicitly on older runs.
3. Apply filters and stable sorting across the full run before pagination. Put a bottom pager on each list with previous, numbered pages, next, and “26–50 of 94”. Reset to page one when filters change. Encode list state in the URL so Back from page evidence restores the same view. Add Clear filters and a useful empty state.
4. Checkpoint: use the reported 100-page partial audit or equivalent fixture. Reconcile grouped counts with evidence, follow a redirect finding, and return to the same filtered page. Check a single-page audit, a historical run with missing fields and a larger saved run.

## 4. Produce reports people and software can use

1. Offer a readable HTML report for the full run with site, date, sample limits, prioritized findings, affected URLs, evidence and suggested next actions. Offer a spreadsheet for page-by-page work with labeled columns and distinct missing values. Explicitly label scope on filtered table exports.
2. Offer a separate analysis bundle containing a versioned manifest and an index describing each file, its schema, units and join keys. Group existing crawl evidence, analysis outputs and diagnostics inside the bundle. Include run and page references, thresholds and exclusions so a later analysis can reproduce counts. Build from allowed run artifacts and exclude credentials.
3. Checkpoint: read the report without the app, open Persian text in the spreadsheet, and reconstruct one finding and the coverage total using only the bundle. Make missing artifacts intelligible for older or failed runs.

## 5. Surface Google workflows with offline inputs first

1. Add a Search & traffic page per project. Give Search Console search performance, URL inspection and GA4 landing pages distinct entries. Explain which question each answers. Show property, date range, source, last successful import and connection status where applicable.
2. Start with the existing file imports, saved datasets and audit workbook. Allow a user to select an audit and appropriate datasets and open the joined report. Preserve missing metrics, incompatible property warnings and the distinction between zero traffic and unavailable data.
3. Wire connection status, property selection, fetch and disconnect controls to the same services as the existing Google CLI. Keep actions requiring authorization visibly unavailable until configured. Defer live consent, API calls and Sheets publishing verification to the owner integration stage.
4. Checkpoint: with no credentials, import fixture exports and trace one landing page from an audit finding to its traffic metrics. Test disconnected, empty, mismatched and expired connection states. Record live checks separately.

## 6. Make repeat audits useful

1. Expose the existing comparison workflow from the project overview. Select a baseline and surface new, persistent and resolved findings. Show coverage differences and mark pages outside either sample as unassessed.
2. Add a project review queue linked to evidence. Let the user mark a finding for review, record a decision and revisit it after the next crawl. Use impact data when available and show why an item appears high on the list.
3. Final owner walkthrough: launch from Windows, audit a real site, filter pages, review an issue, export both formats, import analytics and compare a second run. Record each outcome and unresolved issue. Prioritize further tools using the tasks the owner repeats in practice.

## Design references and the features they inform

- **Stage 3, Ahrefs Page Explorer.** Give common questions one-click presets. In the example audit, selecting “2 redirecting” should open Pages with Redirects active, show the two matching rows and let the user inspect each destination. Implement presets using the same query as the table and its export. [Ahrefs Page Explorer](https://ahrefs.com/academy/how-to-use-ahrefs/site-audit/page-explorer)
- **Stage 3, Semrush Site Audit.** Opening a rule should answer three questions in order: What did we observe? Why might it matter? What should I check next? For a noindex finding, show the directive and ask whether exclusion is intentional before suggesting a change. [Semrush Issues report](https://www.semrush.com/kb/541-site-audit-issues-report)
- **Stage 6, Ahrefs crawl comparison.** Let a user open an affected URL from the change summary and inspect the two dated observations side by side. Test disappearance from a capped sample separately from a verified fix. [Ahrefs crawl comparison](https://help.ahrefs.com/en/articles/5192078-how-to-compare-changes-between-two-crawls-in-site-audit)
- **Research follow-up, Semrush Keyword Gap.** After Stage 5, compare the owned site's keyword export with a competitor sample for a compatible locale and period. Offer Shared and Seen only in competitor sample views, with the source row behind each term. A sample can support a content lead without establishing that a site never ranks. [Semrush Keyword Gap](https://www.semrush.com/kb/28-keyword-gap)

### Research follow-up: question trees

Use AlsoAsked's branching question view as the reference. Start with an imported dataset containing seed, parent question, child question, source, language, country and observation date. An ordinary keyword list can support a flat view until relationship data is supplied. [AlsoAsked FAQ](https://alsoasked.com/faqs)

1. Under Keyword & competitor research, add Explore questions. Select a seed and expand branches. Provide a keyboard-accessible outline alongside the visual tree, support Persian right-to-left text and link each relationship to its source.
2. Let the user select a branch and send its questions to an editorial brief. Export parent-child rows with their provenance so another analyst can reconstruct the tree.
3. Verify with a small Persian fixture covering a shared child, repeated edges, a cycle and a seed with no recorded questions. Expansion must terminate and preserve distinct observed parents. Evaluate a live provider after the offline workflow is useful.
