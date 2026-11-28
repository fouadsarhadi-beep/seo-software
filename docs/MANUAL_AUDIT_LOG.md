# Manual Audit Log

Run these checks after the development batch is ready on your Windows test copy. Start with the saved Samatoos runs. For any mismatch, record the test date, commit, run ID, affected URL or source row, and what you saw.

## Windows desktop checkpoint — Stage J, Step 4

- [ ] Double-click `Start SEO Workbench.cmd` from the project folder with the existing `.venv` in the parent folder. Confirm the workbench opens and shows the usual projects and history.
- [ ] Double-click `SEO-Workbench.exe` to open the workbench. Close the browser tab, reopen it with **Open Workbench**, and confirm **Exit** stops the local server.
- [ ] From a writable checkout, use the script to start a small audit and verify it reopens from the checkout's `.seo-workbench` folder after restarting. If importing the earlier Samatoos workspace, check its projects, history and a saved report download.
- [ ] If Windows blocks writes to the workspace, accept the copy prompt and verify the same projects and history are available. Exit and reopen to check that the copied workspace is reused. Leave the original workspace in place.

## Workspace cleanup checkpoint — Stage C, Step 2

- [ ] In a disposable workspace, save two audits and archive one. Use **Delete** on the archived audit and verify that its history entry, report download and evidence are gone.
- [ ] In that workspace, open **History → Manage saved data** and verify the displayed folder. Delete all audits and confirm the sample project's other saved runs are still listed. Use **Clear workspace data** and verify that the project, saved workflows and remaining runs are removed. Start one new audit in the same workspace.

## Workbench checkpoint — Checks, comparisons and review (steps 1–3)

- [ ] **Technical checks (C3, D2–D4).** Open the saved 100-page audit from **History** and run **All checks**. Open the source link, original page evidence and CSV. Filter **Internal links** for `unknown` and confirm unobserved targets differ from recorded HTTP errors. Search for a known URL in the source audit. If you have an older snapshot without markup, check that the affected checks show partial coverage.
- [ ] **Compare audits (C4, D2).** Under **History → Compare saved audits**, choose two same-site runs with different page caps. Check both coverage summaries, page evidence links and **Finding changes**. A URL seen in one run should say **Only observed before** or **Only observed after**. An HTTP 404 or 410 recorded in the later run should appear as a change in observed status when both runs saw the URL.
- [ ] **Review similar pages (C4, G2).** Open the title match from the 100-page audit. Compare the evidence for both pages and save a decision with a note. Restart the app and find it under **Reviewed**. If a later audit still flags the pair after one page changes, check that it returns to **Needs review** with the previous decision visible.
- [ ] **Coverage and upgrade (D, J).** Confirm old runs and archived results are still accessible. For a larger authorized site, record the crawl cap, observed URL count and runtime. Keep the run ID for later comparisons.

## Local reporting checkpoint — Step 4

- [ ] **Import and reuse (D, E2–E5).** Open a saved audit and choose **Create Excel report**. Import a Search Console page or query export and a GA4 landing-page export for that site. Enter the source dates. Confirm the files appear by name and date, and can be selected again from the same audit without re-uploading.
- [ ] **Check the preview.** Spot-check a matching page and follow its evidence link. Where present, compare an unmatched row, a query-only Search Console row and a URL shared by multiple canonical candidates. Confirm the preview shows their match statuses and preserves their original source row numbers. GA4 paths use the selected audit’s origin, so use an export filtered to that site.
- [ ] **Check the workbook.** Open the download in Excel and check the **Crawl**, **Sources**, **GSC** and **GA4** sheets. Compare a few rows to the original exports and the match totals. Clicks and sessions should remain separate. Confirm the saved report can be opened again from History.

## Local research checkpoint — Step 5

- [ ] **Import and select samples (D, F1).** Open **Tools → Keyword and competitor research**. Import two search-result exports captured on different dates for the same provider, locale and device. Select both files and enter the owned hostname. Confirm **Sources and sample coverage** shows both filenames, dates, locale, device and imported row counts.
- [ ] **Spot-check observations (G1–G4).** Open a keyword, then follow a **Source row** link and compare its URL and rank with the export. Check a competitor gap and, where the samples support them, one SERP overlap, keyword cluster, rank change and content brief. Confirm ranks from different providers, locales or devices appear in separate series.
- [ ] **Reopen the report.** Download the Keyword CSV and both JSON reports, then reopen the same run in History. If you also have backlink or community exports, include them in a second run and follow one source link from each section.

## Build QA checkpoint — Step 8 (Stage H)

- [ ] **Inspect a build.** Open **Tools → Local build QA** and enter the full path to a local HTML build folder. Check that a missing image or page title appears with its relative build path. Open the same run from History and download the CSV and JSON.
- [ ] **Compare selected files.** Add a Lighthouse JSON, an axe JSON, a small access log and same-sized baseline/current PNGs where available. Compare one lab metric, one accessibility rule and one path count with the source files. For different screenshots, open the changed-pixel PNG. Check that the displayed log paths omit query strings and client addresses.
- [ ] **Capture and compare in Chromium.** Install the browser extra and Chromium using the [browser QA instructions](../README.md#capture-browser-qa-for-a-local-build). In **Local build QA**, open **Capture browser screenshot** and capture `/` from a trusted local build. Reopen the capture from History and check the PNG export. Use it as a baseline, capture a revised build with the same page path and viewport, and confirm the report links back to the first capture. If pixels differ, check the displayed mask and the PNG download.

## Connected Google checkpoint — Step 6 (Stages E and I)

Use authorized properties and the documented [Google connection and CLI commands](../README.md#connect-a-google-property). These checks require access on the computer where you grant consent.

- [ ] **Search Console.** Connect the Samatoos property, pull a finished date range with page and query dimensions, and compare a few URLs and metrics against an export with matching filters. Record the date range, filters and any partial coverage. Inspect one known URL and compare the returned index or canonical assessment with Search Console.
- [ ] **GA4 and the workbook.** Retrieve landing pages for the same site and one suitable stream using its origin. From the saved audit, select both API datasets under **Create Excel report**. Verify the source property IDs, one page match and separate clicks, sessions and key events. If you run a GA4 pull without an origin, its relative paths should show **Landing origin unknown**.
- [ ] **Performance.** Run keyed PageSpeed Insights and CrUX for a public page. Check the selected device or form factor and recorded values. If CrUX has no URL-level data, check the result status before trying an origin-level query.
- [ ] **Sheets and Looker Studio.** Preview a small dataset with approved columns, publish it to a new spreadsheet, and check row count and values before opening its **Data** tab in Looker Studio. Repeat publication of the same saved preview to check that it returns the existing receipt.

## Research source checkpoint — Step 7 (Stages F and G)

- [ ] **Public feed.** Open **Tools → Keyword and competitor research → Sample a public RSS or Atom feed**. Fetch a public feed you know with a small limit. Check the saved dates and links against the feed. The request log should show the feed and robots.txt requests. If the feed has more entries than the limit, check that the run shows partial coverage. Run research on the saved dataset and follow a community topic to its source row.
- [ ] **Brave Search.** With an eligible plan that permits keeping samples, save a key and use the [Brave sample command](../README.md#collect-live-research-samples). Try a small set of relevant queries and locales. Record returned rows, elapsed time, cost where available and how many results are relevant. In the workbench, select the saved sample and check the provider, locale, position and unknown device label. Results are positions in the Brave sample.
- [ ] **Other provider exports.** Where you have authorized CSV exports, import a search-results sample and a backlinks sample. Check their field mappings and source-row references before using them for a project.

## Saved audit workflow checkpoint — Step 8 (Stage I)

- [ ] **Save and replay.** Open an existing project and select **Create audit workflow**. Save a named workflow for one target with a small page limit. Restart the app, run the workflow, and confirm the result shows its name, target and page cap. Launch it again to confirm each run has a separate History entry.
- [ ] **Edit safely.** Change the workflow name or page cap, rerun it, and verify that an older run still displays the name and settings it used. Check that the project’s other targets and audit history are still available after the workspace upgrade.
- [ ] **Local access is per run.** If you have a trusted local or private staging site, opt in on one workflow run. On a later run, confirm the option starts unchecked.
- [ ] **Scheduler handoff.** Copy the workflow ID from `seo-analysis workflow list`. Run it from the CLI and verify the workflow name, target, page cap and run ID in History. Then configure a one-time run in Windows Task Scheduler using the [scheduler instructions](../README.md#run-a-saved-workflow-from-a-scheduler). Check that the result appears in the same workspace. While the workflow is running, try launching it again and confirm the second attempt does not start another crawl.

## Review follow-up — 2026-11-28

- [ ] **Windows installation and redirects.** Try a clean install with Python 3.13. If a known alternate URL for your site redirects to its HTTPS or `www` address, check that the workbench names the destination origin. Start a new audit at the intended URL and record its coverage against your sitemap. The earlier Windows run covered a 100-page Samatoos sample.
- [ ] **Calibrate a saved audit.** Create a stratified sample using the [CLI instructions](../README.md#replay-and-review). Review both flagged and unflagged pairs. Confirm the report lists the population, sampled and reviewed counts. After all decisions are saved, check that the report includes weighted estimates for that snapshot.

## Workbench stage 1 checkpoint — first session recovery (pending owner check)

- [ ] **Open Workbench and Copy address.** Start the workbench from `Start SEO Workbench.cmd`. Click **Open Workbench** twice, close the browser tab and reopen it from the launcher window. If the browser does not appear, use **Copy address**, paste the address manually and confirm the address stays selectable.
- [ ] **Feed failure reasons.** Open **Tools → Keyword and competitor research → Import articles from RSS or Atom** and try a site homepage, an empty address, a malformed XML endpoint and a real feed. Each failure should name what was returned and offer **Edit source**. A homepage that advertises a feed should offer that link.
- [ ] **No empty downloads.** Confirm a failed import keeps no CSV or JSON downloads and that the failed run is still listed in **History**.

## Workbench stage 2 checkpoint — project-centered navigation (pending owner check)

- [ ] **Empty workspace.** Open the workbench with no projects. The home screen should offer **Create your first project** and a one-off audit path, with the rail showing the five task areas.
- [ ] **Selected project.** Create a project, add a target and run one audit. The overview should show the target, the latest audit with its coverage counts and a link to the results, recent work for this project, and the project selector set to that project.
- [ ] **Two projects and one-off runs.** Add a second project. Switching between them should change the overview, a project without audits should say so, and one-off audits should appear in their own list.
- [ ] **Task navigation and layout.** Move through Overview, Website audit, Keyword and competitor research, Search and traffic and Site QA. Each should mark itself as current, keep **History** and **Manage saved data** reachable, and use task names rather than internal tool IDs.
- [ ] **Start an audit.** Confirm the page-cap and local-network explanations sit beside their fields, and that choosing a project pre-selects it.
- [ ] **Search and traffic.** Confirm the screen explains what each entry answers and which are import-ready versus unavailable, without claiming a live connection.
- [ ] **Keyboard and narrow window.** Tab through the rail and the primary action with a visible focus ring. Narrow the window below 900px and confirm the rail becomes a horizontal bar and mixed Persian/Latin text stays readable.

## Workbench stage 3 checkpoint — exploring an audit (pending owner check)

- [ ] **Overview first.** Open the saved 100-page audit. The site, date and status should lead, the capped sample should be explained once without repeating the crawler's own limit warning, and findings should be grouped with separate occurrence and URL counts.
- [ ] **A count opens exactly its pages.** Click **Redirecting** on a run that reported redirects. The page table should show exactly that many rows, with the destination under each path.
- [ ] **A finding explains itself.** Open a content-overlap finding. It should say what was observed, why it matters and what to check next, and list both affected pages. For a noindex finding, confirm it asks whether exclusion was intended.
- [ ] **Filters and paging.** Filter by a URL fragment, a status class, indexability and a finding. Confirm the range text (for example “1–30 of 94”), numbered pages, and that changing a filter returns to page one. On the last page, open a page's evidence and use **Back to results** to return to the same filtered view.
- [ ] **Missing data stays unknown.** Open an older run or one with unfetched pages and confirm Unknown appears instead of a blank or a zero, and that rows without page evidence say so.
- [ ] **Exports.** Confirm the CSV and text downloads still work, technical files stay collapsed, and running technical checks from Exports produces a separate run.

## Workbench stage 4 checkpoint — reports and bundles (pending owner check)

- [ ] **Read the report offline.** Open **Exports → Read audit report**, then close the workbench and reopen the page from the download. It should still show site, date, coverage, findings and the affected pages, with its internal links working and no broken images or scripts.
- [ ] **Check the spreadsheet.** Download the page CSV from a filtered table and open it in Excel. The first line should state the run, site, filters and counts; Persian titles should display correctly; header cells and page counts should match the table.
- [ ] **Reconstruct a finding from the bundle alone.** Unzip the analysis bundle and use only `index.json` to go from a finding in `analysis/findings.json` to its page in `crawl/snapshot.jsonl`. With the workbench closed, confirm the index names every file, the join keys and what was skipped.
- [ ] **Outputs that cannot exist.** Open a cancelled or failed run's Exports tab and confirm the report and spreadsheet are shown as unavailable with a reason, while the bundle still downloads.

## Workbench stage 5 checkpoint — Search and traffic (pending owner check)

- [ ] **Not connected is honest.** Open **Search and traffic** with no Google connection. Both providers should say **Not connected**, show the exact consent command, and offer no fetch form. No control should look like it works when it cannot.
- [ ] **Connect from the screen.** In **Search and traffic**, give the path to a Desktop OAuth client JSON and press Connect. A browser consent window should open, the page should say it is waiting, and after consent it should list the properties to choose from. Picking one should show the connected property and reveal the fetch form. The terminal command `seo-analysis google connect gsc` remains available and must produce the same state.
- [ ] **Fetch a small date range.** Pull one week with query and page dimensions. The run should appear in History and as a saved measurement with its period and row count, and its Excel-style dataset should be selectable from an audit's **Create Excel report**.
- [ ] **A failure is not empty data.** Disconnect, then try to fetch again. The screen should report the credential problem explicitly rather than showing zero rows.
- [ ] **Disconnect scope.** Disconnect Search Console on one project and confirm another project's connection is untouched.

## Workbench stage 6 checkpoint — comparing audits (pending owner check)

- [ ] **Comparable runs are chosen for you.** Open **Compare saved audits** from a project with two audits. The two most recent should be preselected, and each option should state its date, observed URL count and page cap.
- [ ] **A fix reads as resolved.** Compare a pair where you know a finding was fixed, one that stayed the same, and one that appeared. They should read **resolved**, **persistent** and **new**, and the evidence link on each should open the observation from the correct run.
- [ ] **A capped run does not fake a fix.** Compare a full run against a run with a lower page cap. Pages that fell outside the later sample should read **unassessed**, never resolved.
- [ ] **An older audit still compares.** Include a run from before the current version and confirm its findings are still placed on the right pages.
- [ ] **Record a decision.** Open an audit, choose a finding, pick an affected page and save a decision with a note. It should appear in **Review queue** with that page, status and note.
- [ ] **A decision survives a restart, and reopens when the page changes.** Restart the workbench and confirm the decision is still there. Run a new audit where that page's title or status changed, then reopen the queue: the item should read **needs re-review** with the previous note still visible.

## Workbench stage 7 checkpoint — research sources (pending owner check)

- [ ] **The picker explains itself.** Open **Keyword and competitor research**. Each saved dataset should say what it can answer, and the page should explain that two comparable samples support a gap comparison while an absent query is not proof of no ranking.
- [ ] **A gap uses comparable samples only.** Import two search-result exports from the same provider, locale and device but different sites. The competitor section should show **Shared**, **Owned sample only** and **Competitor sample only** counts, each expandable to example queries that open their source rows. Confirm the page states that a missing query is a property of these samples, not of the site.
- [ ] **Mismatched samples are called out.** Run the same research with two samples captured on different devices or locales. The report should warn that the samples are not comparable, instead of presenting the difference as a ranking change.
- [ ] **Question relationships import.** Import a CSV with seed, parent and child columns that includes one duplicated edge, one shared child under two parents, and one row missing a value. The saved dataset should keep both relationships for the shared child, list the duplicate as collapsed and the incomplete row as skipped, and preserve the Persian spelling exactly.
- [ ] **Explore a question branch.** Open the questions dataset and choose a seed. The outline should expand with Persian text reading right to left, mark a question that loops back as **cycle**, cap children with a working **Show more**, and open the source row from any question. Export the branch and re-import the file as question relationships: the parent links must come back.
- [ ] **Restore a backup on your machine.** Stop the workbench, copy the configuration file and the whole data directory somewhere safe, then restore that copy and start with `--config-file` pointing at it. Projects, run history and downloads should be there; connected Google accounts should require connecting again.
- [ ] **A gap query becomes a brief item.** In a competitor gap row, use **Brief** on a query. It should appear under **Content brief** with a link back to the research run. Add the same query again with a note and confirm there is still one row with the new note, then remove it.
- [ ] **Compare two question captures.** Import the same question set twice with different observation dates, dropping one question and adding another. Open the outline, choose the earlier capture under **Compare with another capture**, and confirm the panel reports what appeared and what was no longer observed, without implying the question stopped being asked.
- [ ] **Every advertised task leads somewhere.** Work through the navigation and confirm each entry reaches a working screen or explains its prerequisite; nothing should be a dead link. Run a local HTML build through **Site QA** and follow one observation to its evidence.
