# SEO Analysis Software

A local-first workbench for SEO analysis and website research. Run a bounded website audit, inspect its evidence and replay content analysis offline. Projects and saved targets are optional.

## Install on Windows

From the checkout, in CMD or PowerShell with Python 3.12 installed:

```bat
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -e .
.venv\Scripts\seo-analysis --help
.venv\Scripts\seo-analysis system doctor
```

For a reproducible development environment with uv, run `uv sync --locked` then `uv run --locked pytest`. On macOS and Linux the executable in a pip-created environment is `.venv/bin/seo-analysis`.

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

Start the workbench and open `http://127.0.0.1:8765` in your browser. Enter the website, choose crawl options and run the audit. Findings link to the observed page and the results view offers downloadable files. Use Cancel audit to stop acquisition. Completed observations stay available in the cancelled run. Cancellation interrupts pacing and retry waits. An active network read may take until its timeout to return.

```sh
seo-analysis serve
```

Use run IDs printed by the CLI or listed under History. The following commands read existing snapshots offline.

```sh
seo-analysis check --run <crawl-id> --check broken-links --json
seo-analysis check --run <crawl-id> --check hreflang
seo-analysis compare --before <older-crawl-id> --after <newer-crawl-id>
```

Omit `--check` to run all eight checks. A broken-link result requires an observed HTTP error at the target. A link to an uncrawled page has unknown status. Older snapshots can lack the new markup inventory. To continue editorial review across crawls, pass the same `--decisions path/to/decisions.jsonl` to successive review and calibration commands. Changed page content reopens its pair for review.

## Research and reports from local exports

Import an export with its source and observation date. Use `--period-start` for an aggregated measurement and `--locale` and `--device` for search results. Each import prints a dataset run ID. CSV, TSV and the active worksheet in XLSX are supported. Community imports also accept local RSS or Atom feeds. Map custom column headers with `--columns`, a JSON object from normalized field names to original headers.

```sh
seo-analysis import-data rankings.csv --kind serp --provider "Account export" --observed 2026-11-21 --locale fa-IR --device desktop
seo-analysis research --dataset <rankings-id> --owned-host example.org
seo-analysis import-data pages.csv --kind gsc --provider "Search Console" --period-start 2026-11-01 --observed 2026-11-21
seo-analysis import-data landing-pages.csv --kind ga4 --provider "GA4" --period-start 2026-11-01 --observed 2026-11-21
seo-analysis workbook --crawl <crawl-id> --dataset <gsc-id> --dataset <ga4-id>
```

Supply repeated `--dataset` arguments to compare dated SERP samples or include keyword, community and backlink exports. The research output includes a keyword map, competitor gaps, overlapping results, sampled rank history, brief candidates and source-row references. The Excel workbook keeps Search Console and GA4 on separate sheets with row-level match status. Query-only Search Console exports retain their clicks and impressions without page attribution. GA4 paths use the crawl origin, so select an export filtered to that host when the property covers several hosts. An optional `--report-url` records an existing Looker Studio report link in the report metadata.

## Local site QA and agent access

```sh
seo-analysis site-qa ./build
seo-analysis site-qa ./build --lighthouse lighthouse.json --axe axe.json --access-log access.log --baseline approved.png --screenshot current.png
seo-analysis tools run seo.check --run <crawl-id> --check canonicals
seo-analysis mcp --allow-run <crawl-id>
```

Each QA input is optional. The PNG comparison requires an explicitly chosen baseline and identical dimensions. The log summary counts paths and HTTP statuses and discards client addresses and query strings. For an MCP client, configure the installed `seo-analysis` executable with arguments `mcp --allow-run <crawl-id>`. Repeat the flag to select additional runs. The stdio server exposes selected summaries, page evidence, paginated findings and offline checks. It exits when the client disconnects.

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

## Connect a Google property

Install the optional dependencies on the computer where you will give consent. On Windows, use the virtual environment's Python. On Linux, an unlocked Secret Service or KWallet must be available in your desktop session.

```sh
python -m pip install -e '.[google]'
```

In Google Cloud, enable the Search Console API for `gsc` or the Google Analytics Admin API for `ga4`. Configure the OAuth consent screen and create an OAuth client of type **Desktop app**. If the consent screen is in testing mode, add the Google account as a test user. Download the client JSON to a private location outside the repository.

```sh
seo-analysis google connect gsc --client-file path/to/desktop-client.json
seo-analysis google status gsc
seo-analysis google disconnect gsc
```

Sign in and grant the requested read-only permission in the browser on the same computer, then select one of the properties printed in the terminal. Use `--property sc-domain:example.com` or `--property properties/123456789` to provide the exact property ID instead of choosing from the numbered list. The same commands accept `ga4` for Analytics. Add `--project NAME` to keep a connection with an existing project.

The credential manager holds the refresh token and OAuth client secret. SQLite holds the selected property's ID and display name. Moving the workspace to a different path or computer requires reconnecting. For a grant you also want to remove from your Google account, pass `--revoke` to disconnect. Google may revoke other grants for the same account and OAuth project.

This milestone covers authorization and property selection. Use the file import workflow above to analyze or report on Google data.

## Workspace

Run `system doctor` to locate the configuration, data, run and export directories. Configuration is optional. To customize paths, copy [config.example.toml](config.example.toml) to the reported config path, or select a file with `seo-analysis --config-file "<path>" system doctor`. Relative directory settings resolve beside the configuration file. When all commands have exited, back up the config file and complete data directory, including history.sqlite3 and runs/. Restore them to the locations reported by doctor. Reindexing recovers run records from manifests. The database backup also preserves projects and targets that have never been used. To start a fresh workspace, select a new data directory.

See the [architecture](SEO_ANALYSIS_SOFTWARE_ARCHITECTURE.md) for the product roadmap and the [implementation state](docs/IMPLEMENTATION_STATE.md) for verified capabilities and current limits. See the [implementation log](docs/IMPLEMENTATION_LOG.md) for dated changes by stage and step.
