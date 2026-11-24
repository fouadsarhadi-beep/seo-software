# Manual Audit Log

Run these checks after the development batch is ready on your Windows test copy. Start with the saved Samatoos runs. For any mismatch, record the test date, commit, run ID, affected URL or source row, and what you saw.

## Workbench checkpoint — Checks, comparisons and review (steps 1–3)

- [ ] **Technical checks (C3, D2–D4).** Open the saved 100-page audit from **History** and run **All checks**. Open the source link, original page evidence and CSV. Filter **Internal links** for `unknown` and confirm unobserved targets differ from recorded HTTP errors. Search for a known URL in the source audit. If you have an older snapshot without markup, check that the affected checks show partial coverage.
- [ ] **Compare audits (C4, D2).** Under **History → Compare saved audits**, choose two same-site runs with different page caps. Check both coverage summaries, page evidence links and **Finding changes**. A URL seen in one run should say **Only observed before** or **Only observed after**. An HTTP 404 or 410 recorded in the later run should appear as a change in observed status when both runs saw the URL.
- [ ] **Review similar pages (C4, G2).** Open the title match from the 100-page audit. Compare the evidence for both pages and save a decision with a note. Restart the app and find it under **Reviewed**. If a later audit still flags the pair after one page changes, check that it returns to **Needs review** with the previous decision visible.
- [ ] **Coverage and upgrade (D, J).** Confirm old runs and archived results are still accessible. For a larger authorized site, record the crawl cap, observed URL count and runtime. Keep the run ID for later comparisons.

## Local reporting checkpoint — Step 4

- [ ] **Import and reuse (D, E2–E5).** Open a saved audit and choose **Create Excel report**. Import a Search Console page or query export and a GA4 landing-page export for that site. Enter the source dates. Confirm the files appear by name and date, and can be selected again from the same audit without re-uploading.
- [ ] **Check the preview.** Spot-check a matching page and follow its evidence link. Where present, compare an unmatched row, a query-only Search Console row and a URL shared by multiple canonical candidates. Confirm the preview shows their match statuses and preserves their original source row numbers. GA4 paths use the selected audit’s origin, so use an export filtered to that site.
- [ ] **Check the workbook.** Open the download in Excel and check the **Crawl**, **Sources**, **GSC** and **GA4** sheets. Compare a few rows to the original exports and the match totals. Clicks and sessions should remain separate. Confirm the saved report can be opened again from History.
