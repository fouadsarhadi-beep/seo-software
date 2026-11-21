# SEO Analysis Software

A local-first workbench for SEO analysis and website research. The foundation includes sitemap crawling, offline content and canonical analysis, Persian spelling variants, editorial review and threshold calibration.

## Install on Windows

From the checkout, in CMD or PowerShell with Python 3.12 installed:

```bat
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -e .
.venv\Scripts\seo-analysis --help
.venv\Scripts\seo-analysis system doctor
```

For a reproducible development environment with uv, run `uv sync --locked` then `uv run --locked pytest`. On macOS and Linux the executable in a pip-created environment is `.venv/bin/seo-analysis`.

## Local workflow

```sh
seo-analysis tools list --json
seo-analysis system doctor --json
seo-analysis crawl --sitemap https://example.org/sitemap.xml --limit 20
```

Use the crawl directory printed by the command in each following step. A unique directory is allocated per crawl by default. Use `--out-dir` to select a destination explicitly.

```sh
seo-analysis variants --in-dir "<crawl directory>"
seo-analysis analyze --in-dir "<crawl directory>"
seo-analysis review --in-dir "<crawl directory>"
seo-analysis calibrate --in-dir "<crawl directory>"
```

Analysis reads the saved snapshot and runs locally. The optional variants step records approved Persian spellings. The inventory, canonical reports, similarity candidates and human decisions remain inspectable as CSV, JSON or JSONL. The analysis command accepts existing Search Console CSV exports.

## Workspace

Run `system doctor` to locate the configuration, data, run and export directories. Configuration is optional. To customize paths, copy [config.example.toml](config.example.toml) to the reported config path, or select a file with `seo-analysis --config-file "<path>" system doctor`. Relative directory settings resolve beside the configuration file. Back up the config file and run directories after a run finishes. Restore them to the locations reported by doctor. To start a fresh workspace, select a new data directory.

See the [architecture](SEO_ANALYSIS_SOFTWARE_ARCHITECTURE.md) for the product roadmap and the [implementation state](docs/IMPLEMENTATION_STATE.md) for verified capabilities and current limits.
