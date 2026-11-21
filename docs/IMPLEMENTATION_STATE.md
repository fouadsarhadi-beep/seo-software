# Implementation state

## Stage A · Installable foundation

The Git checkout contains the maintained Python source and offline fixtures. The original ZIP and its six-command baseline are recorded at commit `2001b7c`. The current CLI installs as `seo-analysis`. Run `tools list --json` for the implemented tool IDs and their CLI names, and `system doctor --json` for local installation details.

| Area | Current behavior |
|---|---|
| Acquisition | Sitemap-led crawl with explicit target input. The fetcher checks the selected HTTP origin on its first request and redirects. Page exclusions can be configured. |
| Analysis | Offline replay of saved snapshots, canonical diagnostics, content similarity, Persian spelling variants, editorial decisions and threshold calibration. |
| Storage | Each default crawl gets a separate workspace directory. TOML can override the data and export paths. The operator can select a crawl output directory explicitly. |
| Integrations | GSC CSV imports and the acquisition function with its mock tests are retained. Interactive OAuth and the live command are deferred to the Google connector stage with OS-backed credentials. |
| Verification | On Linux with CPython 3.12.14, 84 tests passed and one optional Hazm test skipped. A built wheel installed in a clean environment outside the checkout, with spaces and Persian characters in its path. CLI help, doctor JSON and the packaged Persian stopword data passed. The Windows and Linux CI workflow includes the suite and isolated wheel installation. Windows execution is pending. |

## Next increment · Bounded website input and durable runs

1. Extend the transport with destination-address enforcement for public websites and explicit approval for a local fixture or staging origin. Share request/time budgets across discovery, retries and redirects.
2. Accept a website URL or URL list alongside the explicit sitemap. Discover sitemaps using robots declarations and configured conventional paths. Offer a budgeted internal-link crawl when there is no usable sitemap.
3. Persist each observation during the crawl. Finalize a per-run manifest with status, coverage, timing and evidence references, including cancelled and partial runs.
4. Compose the installed `audit` command from acquisition and offline analysis. Verify report correctness for reserved URL characters, redirecting canonical targets, incomplete extraction and phrase adjacency. Add the fixture cases in Section 17.
5. Once both acquisition and offline replay work end to end, validate the runner contract and add optional SQLite history. Link review decisions to content snapshots and preserve missing GSC values during enrichment.

Until Stage B, the sitemap command uses ordinary system DNS and the existing per-request controls. The page limit applies after sitemap discovery. Interrupting a crawl before snapshot writing can lose its observations. Run against selected, trusted sitemap inputs during this foundation stage.

The [architecture](../SEO_ANALYSIS_SOFTWARE_ARCHITECTURE.md) maintains the full tool roadmap. The [foundation decision](adr/0001-foundation.md) records the initial runtime and storage choices.

## Active checklist through Stage C step 2

- [x] B1. Pin each connection to an approved destination and apply shared crawl budgets.
- [x] B2. Accept URL, sitemap and seed lists, discover pages, checkpoint evidence and report coverage.
- [x] B3. Verify the installed audit and correct the verified reporting defects.
- [ ] C1. Run the audit and offline operations through shared tool contracts.
- [ ] C2. Add optional projects and saved targets, schema migrations and recoverable SQLite run, artifact and evidence indexes.
