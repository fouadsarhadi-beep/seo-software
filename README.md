# SEO Analysis Software

A local SEO workbench. Enter a website URL to crawl its pages and flag issues such as missing titles, broken links to checked pages, and similar content across pages. The app shows which pages it reached, links findings to the pages it checked, and saves reports you can download or revisit in **History**.

You can also compare saved audits, turn Search Console and GA4 exports into an Excel report, or check a local site build before publishing. A basic audit needs access to the site, with no API keys or accounts.

## Quick start

Open a terminal in the downloaded repository folder with Python 3.12 installed.

On Windows, use CMD or PowerShell.

```bat
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -e .
.venv\Scripts\seo-analysis serve
```

On macOS or Linux, use these commands.

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/seo-analysis serve
```

Open [http://127.0.0.1:8765](http://127.0.0.1:8765), enter your website URL, and click **Run audit**. Under **Crawl options**, enable **Follow internal links if no sitemap is available** if your site has no sitemap. When the audit finishes, check the crawl coverage, open a finding to see its evidence, and download the report. On later visits, run only the `serve` command to reopen the app. Press Ctrl+C in the terminal to stop it.

For a reproducible development environment with uv, run `uv sync --locked` then `uv run --locked pytest`.

To install a built wheel, download the `seo-analysis-wheel` artifact from a successful Foundation checks run and extract it. In the virtual environment, replace the editable install above with `.venv\Scripts\python -m pip install path\to\seo_analysis-0.4.0-py3-none-any.whl`. The Python wheel contains the CLI, workbench templates and Persian stopwords.

## Run an audit

With the virtual environment active, choose a website, a sitemap or a single-origin list of URLs. A CSV list needs a `URL` column. A text list takes one URL per line.

```sh
seo-analysis audit https://example.org --max-pages 100 --max-depth 2
seo-analysis audit --sitemap https://example.org/sitemap.xml --max-requests 150
seo-analysis audit --urls-file seeds.csv --json
```

For a website, the crawler checks robots declarations and conventional sitemap paths. Use `--link-crawl` to follow links when discovery finds no usable sitemap. With no arguments, an interactive terminal prompts for a target. Scripts can use `--non-interactive`. An approved local test server requires `--allow-local` for that run. A saved target stores the URL and input kind. It confers no network or account permission.

`audit --help` lists page, depth, request, duration, retry, response-size, pacing and per-path query-variant controls. Scope is one exact origin. The transport connects to validated numeric addresses and retains the origin hostname for HTTPS verification. Robots, sitemap requests, redirects and retries share the request budget.

The result includes a run ID and directory. Read `issues.txt` for findings, or use `findings.json` / `findings.csv` and look up each evidence ID under `observations/`. `requests.json` records attempted destinations and HTTP responses when received. `run.json` contains the tool version, inputs, outcome, timestamps, coverage, warnings and file references. A response cap or request limit can produce a partial result. Exit codes are 0 for success, 3 for partial, 130 for cancellation and 2 for a failed or empty audit or invalid input.

## Replay and review

```sh
seo-analysis variants --in-dir "<crawl directory>"
seo-analysis analyze --in-dir "<crawl directory>" --json
seo-analysis review --in-dir "<analysis directory>"
seo-analysis calibrate --in-dir "<analysis directory>"
```

Each execution receives its own run directory. Use the analysis directory printed by `analyze` for review and calibration. Decisions are saved alongside the selected pair set. The review and calibration runs retain copies of their outputs. Existing Search Console CSVs can enrich an offline replay. The `crawl --sitemap` command runs acquisition on its own.

## Local workbench and snapshot checks

**Projects** lists saved projects. Open **Create project** to enter a name and optionally save a website. Open a project to view its targets or add another. In **History**, use **Archive** to hide a run from the history and recent-runs lists. You can open or restore it under **View archived runs**. Its evidence and files remain available.

Audit results show the sampled coverage and link to the findings CSV, page inventory CSV and text report under **Downloads**. Expand **Technical files** for the raw data and request log. The local or private-network crawl option applies to one audit of a trusted local site, internal staging site or test server on a nonstandard port.

Open a saved audit from **History**, select **All checks** or an individual check, and click **Run technical checks**. The report uses the saved snapshot and appears as a separate run with a CSV and links to the original page evidence. Search and filters narrow the visible findings, observations and crawled URLs. The downloads contain the full reports.

From **History → Compare saved audits**, select an earlier and later run from the same site. The report links to both runs and shows observed page changes, coverage and differences between the saved findings. From an audit with similar-page data, choose **Review similar pages** to see the matching signals and record a decision. The workbench saves decisions in `decisions.jsonl` in the workspace data directory. Pass that file to the CLI with `--decisions` to reuse them for review or calibration.

Use **Cancel audit** to stop a crawl in progress. Completed observations stay available in the cancelled run. Cancellation interrupts pacing and retry waits. An active network read may take until its timeout to return.

Use run IDs printed by the CLI or listed under History. The following commands read existing snapshots offline.

```sh
seo-analysis check --run <crawl-id> --check broken-links --json
seo-analysis check --run <crawl-id> --check hreflang
seo-analysis compare --before <older-crawl-id> --after <newer-crawl-id>
```

Omit `--check` to run all eight checks. A broken-link result requires an observed HTTP error at the target. A link to an uncrawled page has unknown status. Older snapshots can lack the new markup inventory. To continue editorial review across crawls, pass the same `--decisions path/to/decisions.jsonl` to successive review and calibration commands. Changed page content reopens its pair for review.

## Research and reports from local exports

For a report in the browser, open a saved audit and choose **Create Excel report**. Import or select Search Console and GA4 exports, then choose **Preview matches**. The preview shows example rows and links to their crawl evidence. The Excel download contains every imported row and its match status.

Import an export with its source and observation date. Use `--period-start` for an aggregated measurement and `--locale` and `--device` for search results. Each import prints a dataset run ID. CSV, TSV and the active worksheet in XLSX are supported. Community imports also accept local RSS or Atom feeds. Map custom column headers with `--columns`, a JSON object from normalized field names to original headers.

```sh
seo-analysis import-data rankings.csv --kind serp --provider "Account export" --observed 2026-11-21 --locale fa-IR --device desktop
seo-analysis research --dataset <rankings-id> --owned-host example.org
seo-analysis import-data pages.csv --kind gsc --provider "Search Console" --period-start 2026-11-01 --observed 2026-11-21
seo-analysis import-data landing-pages.csv --kind ga4 --provider "GA4" --period-start 2026-11-01 --observed 2026-11-21
seo-analysis workbook --crawl <crawl-id> --dataset <gsc-id> --dataset <ga4-id>
```

Supply repeated `--dataset` arguments to compare dated SERP samples or include keyword, community and backlink exports. The research output includes a keyword map, competitor gaps, overlapping results, sampled rank history, brief candidates and source-row references. The Excel workbook keeps Search Console and GA4 on separate sheets with row-level match status. Query-only Search Console exports retain their clicks and impressions without page attribution. GA4 paths from imported files assume the crawl origin, so select an export filtered to that host when the property covers several hosts. An optional `--report-url` records an existing Looker Studio report link in the report metadata.

## Local site QA and agent access

```sh
seo-analysis site-qa ./build
seo-analysis site-qa ./build --lighthouse lighthouse.json --axe axe.json --access-log access.log --baseline approved.png --screenshot current.png
seo-analysis tools run seo.check --run <crawl-id> --check canonicals
seo-analysis mcp --allow-run <crawl-id>
```

Each QA input is optional. The PNG comparison requires an explicitly chosen baseline and identical dimensions. The log summary counts paths and HTTP statuses and discards client addresses and query strings. For an MCP client, configure the installed `seo-analysis` executable with arguments `mcp --allow-run <crawl-id>`. Repeat the flag to select additional runs. The stdio server exposes selected summaries, page evidence, and paginated findings. It exits when the client disconnects.

Select both crawl IDs to compare snapshots, or select one crawl to run offline technical checks and content analysis. Derived runs remain available in the same session. Select a saved review run to read editorial decisions, a workbook run to read its recorded Looker Studio link, or a publication run to read its published Sheets link. The session can create up to 20 offline runs. Reads are limited to 100 rows per page and 32 MB per artifact. Reports returned by these tools are local references and excerpts.

## Optional projects and history

```sh
seo-analysis project create Personal
seo-analysis target add blog https://example.org --project Personal
seo-analysis audit --project Personal --target blog
seo-analysis history list --project Personal
seo-analysis history show <run-id> --json
seo-analysis history reindex
```

History includes ad hoc runs. `history show` resolves artifact paths and page evidence within a run. `history reindex` rebuilds index entries from manifests, skips active writers and recovers completed observations from a process that exited before finalization. The recovered run shows incomplete coverage. Saved targets use website input by default. Specify `--kind sitemap` to save a sitemap URL.

## Collect live research samples

Brave Search is an optional source for keyword and competitor research. It samples which pages rank for a query in Brave's web results. Saved samples can help compare competing sites, group queries with overlapping results, or track observed ranking changes across comparable dates. The website audit runs independently, and Google rankings require a separate source.

```sh
seo-analysis research-feed https://example.com/feed.xml --max-items 25
python -m pip install -e '.[research]'
seo-analysis research-key set
seo-analysis research-search "example topic" --country us --language en --count 10 --allow-storage
seo-analysis research --dataset <sample-run-id> --owned-host example.com
```

The feed reader requests the selected public RSS or Atom feed and its robots.txt. It follows redirects within the same origin and saves entry titles, links and available publication dates. Each response is limited to 2 MB.

The search command sends the selected query and locale to the official Brave Search API. Use a plan that permits storing the selected results and pass `--allow-storage` to confirm. The key is stored in the OS credential manager and can be removed with `research-key delete`. Each request samples up to 20 Brave web results. The dataset preserves sample rank, the requested locale, retrieval time and elapsed time. Device class is unavailable. Add multiple research datasets with repeated `--dataset` flags.

## Plan content from research evidence

```sh
seo-analysis research --owned-host example.com --dataset <serp-run> --dataset <older-gsc-run> --dataset <newer-gsc-run>
seo-analysis research --owned-host example.com --dataset <serp-run> --owned-crawl <owned-run> --competitor-crawl <competitor-run>
```

Open `content-plan.json` in the research run. It groups related queries when observed search results share at least two URLs and half of the combined result set in the same provider, date, locale and device sample. The editorial briefs link to the observed competitor pages and provide prompts for review.

Refresh candidates flag measured declines across the two latest comparable, equal-length and non-overlapping Search Console periods. Supply query-by-page data for both periods. For local imports, use matching property and filters and record each period with `--period-start` and `--observed`. Missing, duplicated, incomplete and segmented measurements are excluded where a comparable pair cannot be established.

Supply both saved crawl IDs to compare the best-ranked observed page from each site for the same query and sample. The report includes titles, H1s, word counts and links by run and evidence ID. Coverage depends on the selected search observations and saved pages.

## Connect a Google property

Install the optional dependencies on the computer where you will give consent. On Windows, use the virtual environment's Python. On Linux, an unlocked Secret Service or KWallet must be available in your desktop session.

```sh
python -m pip install -e '.[google]'
```

In Google Cloud, enable the Search Console API for `gsc` or the Google Analytics Admin API and Google Analytics Data API for `ga4`. Configure the OAuth consent screen and create an OAuth client of type **Desktop app**. If the consent screen is in testing mode, add the Google account as a test user. Download the client JSON to a private location outside the repository.

```sh
seo-analysis google connect gsc --client-file path/to/desktop-client.json
seo-analysis google status gsc
seo-analysis google disconnect gsc
```

Sign in and grant the requested read-only permission in the browser on the same computer, then select one of the properties printed in the terminal. Use `--property sc-domain:example.com` or `--property properties/123456789` to provide the exact property ID instead of choosing from the numbered list. The same commands accept `ga4` for Analytics. Add `--project NAME` to keep a connection with an existing project.

The credential manager holds the refresh token and OAuth client secret. SQLite holds the selected property's ID and display name. Moving the workspace to a different path or computer requires reconnecting. For a grant you also want to remove from your Google account, pass `--revoke` to disconnect. Google may revoke other grants for the same account and OAuth project.

### Retrieve Search Console data

```sh
seo-analysis google search-analytics --start 2026-11-01 --end 2026-11-21 --dimensions query page device country
seo-analysis google inspect-url https://example.com/article/
seo-analysis workbook --crawl <audit-run-id> --dataset <search-analytics-run-id>
```

Both Google commands use the selected Search Console property. Add `--project NAME` to use that project's connection. Search Analytics uses Pacific Time dates and defaults to finalized web results grouped by query and page. Choose at least one of those two dimensions. You can also group by date, device or country. `--data-state all` includes provisional data when available.

Each pull saves `normalized.csv` and `dataset.json` in its run directory. Use its run ID with the workbook command directly. The pull retrieves up to 50,000 rows, which you can reduce with `--max-rows`. Reaching the selected limit or losing a later batch produces a partial run. Explicit zero values remain zero. Google may omit rows, including anonymized queries. URL Inspection saves Google's indexed assessment for one URL within the property each time you run it.

### Retrieve GA4 landing-page data

```sh
seo-analysis google landing-pages --start 2026-11-01 --end 2026-11-21 --channel "Organic Search" --stream-id 123456789 --origin https://example.com
seo-analysis workbook --crawl <audit-run-id> --dataset <ga4-run-id> --dataset <search-analytics-run-id>
```

The GA4 command uses the selected property and the property's reporting time zone. Add `--project NAME` for a project connection. By default it reports all web channels and streams. The example filters to Organic Search and one web stream. The dataset keeps sessions and key events in separate columns and records Google's reported row count, quota information and any sampling or privacy threshold notices.

Landing paths retain their query strings. Supply `--origin` only when the selected data belongs to that web origin. This assigns a hostname and scheme for crawl matching. Use `--stream-id` or an appropriately scoped property when the property covers several sites. With no supplied origin, live GA4 paths appear as **landing origin unknown** in the workbook. The workbook checks requested URLs first, then final URLs, then site-declared canonicals. If several crawl records match at the same tier, it reports **ambiguous** and lists the candidate evidence.

### Measure page performance

```sh
seo-analysis google pagespeed https://example.com/ --strategy mobile
seo-analysis lighthouse-report lighthouse.json
seo-analysis google performance-key set
seo-analysis google crux https://example.com/ --form-factor PHONE
seo-analysis google crux https://example.com --scope origin
```

PageSpeed Insights runs a Lighthouse lab test for a public URL. It sends the URL, including its query string, to Google. To connect a key, enable the PageSpeed Insights API and Chrome UX Report API in Google Cloud, install the Google extra and run `google performance-key set` in an interactive terminal. The key is shared by the two performance commands within the selected workspace and stored in the OS credential manager. CrUX requires the key. Add `--use-key` to PageSpeed Insights to use it. `google performance-key delete` removes the saved key locally.

Generate local Lighthouse JSON with Chrome DevTools or the Lighthouse CLI, then pass it to `lighthouse-report`. Both lab tools produce `performance.json` with Lighthouse scores, timings, device data and warnings. CrUX produces a separate field report with p75 values, histogram data when available, collection period and form factor. Use `--scope origin` for an explicit whole-origin sample. A missing URL record appears as `no_data` and exits with code 3. Field INP and lab Total Blocking Time remain distinct measurements.

### Export selected data to Google Sheets

Create a local preview from a normalized dataset run, such as a Search Analytics pull, a GA4 landing-page pull or a file import. Repeat `--column` in the order you want the columns written.

```sh
seo-analysis export-dataset --dataset <dataset-run-id> --title "Search report" --column query --column url --column clicks
```

Review `selected.csv` or `selected.xlsx` in the export run directory. `export.json` lists the title, columns, row count, coverage and confirmation SHA-256. Preparing the export works offline. Select fewer rows with `--max-rows` if the upload limit is reached.

Enable the Google Sheets API in the Google Cloud project for your Desktop OAuth client. Connect Sheets separately using the app-file permission, then publish the reviewed export.

```sh
seo-analysis google connect sheets --client-file path/to/desktop-client.json
seo-analysis google publish-sheets <export-run-id> --confirm <sha256-from-export.json>
```

Use the same `--project NAME` for preparing, connecting and publishing when working in a project. Publishing creates a spreadsheet in the connected Google account and writes the selected values into its **Data** tab. Google sharing permissions are managed separately. Open the URL in `publication.json`, or select that spreadsheet and tab through the Google Sheets connector in Looker Studio. Strings are written as literal cell values. Empty measurements appear as blank cells and numeric zeros stay numeric.

If a cell upload fails, rerun publication with the same export and checksum to write to the recorded spreadsheet. A completed publication returns the existing receipt. If Google fails to return the spreadsheet ID during creation, the run reports an unknown outcome. Check Drive for the preview title before preparing a fresh export.

## Capture browser QA for a local build

```sh
python -m pip install -e '.[browser]'
python -m playwright install chromium
seo-analysis browser-qa ./build --page /docs/ --width 1365 --height 768
seo-analysis browser-qa ./build --page /docs/ --axe-script ./node_modules/axe-core/axe.min.js --baseline approved.png
```

Choose a trusted build directory and an HTML route. Use a trailing slash for a directory index such as `/docs/`. The command runs Chromium with a fresh profile, serves files from the selected build and blocks external resources. Use `--chromium` to select an installed Chromium executable. The run saves `screenshot.png` and `browser-qa.json` with browser version, viewport, resource observations and local navigation timings.

To run accessibility checks, pass the `axe.min.js` file from a trusted axe-core installation. The generated `axe.json` also works with `site-qa --axe`. For visual comparisons, pass an approved PNG at the same viewport size. Changes produce a `changed-pixels.png` mask. Keep browser version and viewport consistent across captures. Browser timings describe this local run. Use the Lighthouse and CrUX commands for their separate performance measurements.

### Generate a local Lighthouse lab report

```sh
seo-analysis lighthouse-run ./build --page / --device desktop --lighthouse-cli ./node_modules/lighthouse/cli/index.js --chromium /path/to/chromium
```

Install Lighthouse with npm and use a compatible Node.js version plus an installed Chrome or Chromium executable. The command serves one trusted build on loopback and runs Lighthouse against a fresh browser profile. External resources are blocked, so the lab measurements describe the files in the selected build. The run saves the generated `lighthouse.json` and normalized `performance.json`. Pass the raw report to `site-qa --lighthouse` to include it in a build QA report.

## Inspect published WordPress metadata

```sh
seo-analysis wordpress inventory https://example.com/blog --resource pages --max-items 50
```

Pass the installation's exact HTTPS base URL, including its subdirectory if present. Public reads follow the site's robots policy. The run saves `wordpress.json` and `wordpress.csv` with selected metadata from published posts or pages. Yoast canonical and index directives appear when the REST API exposes them. Results reflect the selected item limit and any incomplete pages of API results.

Use `--resource media` for attachment metadata, including source URL, alt text, MIME type, dimensions and attached post ID. Attachment files are not downloaded. Use `--resource types` to list supported REST registrations and then pass a custom type's slug, such as `--resource book`, to inventory its published items. Custom routes must be registered under `wp/v2`.

For authorized access, create an Application Password for a dedicated WordPress user with the minimum access the site requires. Install the optional credential support, save the password with the interactive prompt and explicitly select authenticated inventory.

```sh
python -m pip install -e '.[wordpress]'
seo-analysis wordpress connect https://example.com/blog
seo-analysis wordpress inventory https://example.com/blog --resource posts --authenticated
seo-analysis wordpress forget https://example.com/blog
```

Credentials are stored in the OS credential manager and scoped to the installation, workspace and optional `--project NAME`. The connector reads the selected REST route over HTTPS and stops at redirects. `forget` removes the saved copy locally. To revoke the Application Password itself, use WordPress's user profile screen.

## Workspace

Run `system doctor` to locate the configuration, data, run and export directories. Configuration is optional. To customize paths, copy [config.example.toml](config.example.toml) to the reported config path, or select a file with `seo-analysis --config-file "<path>" system doctor`. Relative directory settings resolve beside the configuration file. When all commands have exited, back up the config file and complete data directory, including history.sqlite3 and runs/. Restore them to the locations reported by doctor. Reindexing recovers run records from manifests. The database backup also preserves projects and targets that have never been used. To start a fresh workspace, select a new data directory.

Follow the [roadmap](docs/ROADMAP.md) for the current step and what comes next. See the [architecture](SEO_ANALYSIS_SOFTWARE_ARCHITECTURE.md) for the detailed design, the [implementation state](docs/IMPLEMENTATION_STATE.md) for verification and limits, and the [implementation log](docs/IMPLEMENTATION_LOG.md) for dated changes.
