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
