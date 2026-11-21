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

## Workspace

Run `system doctor` to locate the configuration, data, run and export directories. Configuration is optional. To customize paths, copy [config.example.toml](config.example.toml) to the reported config path, or select a file with `seo-analysis --config-file "<path>" system doctor`. Relative directory settings resolve beside the configuration file. When all commands have exited, back up the config file and complete data directory, including history.sqlite3 and runs/. Restore them to the locations reported by doctor. Reindexing recovers run records from manifests. The database backup also preserves projects and targets that have never been used. To start a fresh workspace, select a new data directory.

See the [architecture](SEO_ANALYSIS_SOFTWARE_ARCHITECTURE.md) for the product roadmap and the [implementation state](docs/IMPLEMENTATION_STATE.md) for verified capabilities and current limits.
