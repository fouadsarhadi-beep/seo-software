# Implementation state

## Goal checklist through Stage C step 2

- [x] Stage A. Installable Python package, workspace configuration, diagnostics and built-in tool catalogue.
- [x] B1. Accept explicit website, sitemap and URL-list inputs. Validate the selected origin and pin each connection to an approved address.
- [x] B2. Discover sitemaps and support an opt-in, bounded link crawl. Apply shared request and time budgets, save observations incrementally and record coverage.
- [x] B3. Produce technical and content findings, evidence references and terminal, JSON and CSV reports. Exercise the installed CLI against offline fixture sites.
- [x] C1. Route audit, crawl, offline analysis, variants, review and calibration through typed requests and a shared tool runner.
- [x] C2. Support ad hoc runs, optional projects and saved targets, transactional SQLite migrations, run history, artifact and evidence indexes and interrupted-run recovery.

## Verification

The suite covers a Persian WordPress-style sitemap, static HTML without a sitemap, redirects, robots, malformed XML, CSV seeds, parameter limits, interrupted acquisition, exact canonical target status and phrase adjacency. Transport tests use simulated DNS answers and an explicit local fixture. A separate console test launches the installed executable outside the checkout, performs an ad hoc audit, replays its snapshot offline and inspects the indexed evidence.

Persistence tests exercise concurrent first-time schema creation, a future schema version, an active writer, interrupted runs, repeatable recovery and rebuilding project-linked history after losing the index. The clean wheel check includes the bundled Persian resources. The source checkout and an isolated installation of the 0.2.0 wheel each passed 101 tests on Linux with Python 3.12.14. The optional Hazm test skipped in both environments. Windows runs are configured in CI and await execution.

## Current scope

Audit findings describe the HTML and HTTP responses received. The request/time budget covers acquisition. Offline report generation and SQLite finalization can continue afterward. Reports preserve missing measurements and label content overlap for human review. Search Console CSV imports remain available. Authenticated services are deferred. Existing Stage A snapshots can be analyzed; a missing source completion status appears as unknown coverage.

The implementation stops at C2. C3 begins additional independent offline checks. C4 covers comparisons across runs and reopening reviews after content changes.

[Architecture](../SEO_ANALYSIS_SOFTWARE_ARCHITECTURE.md) · [Foundation decision](adr/0001-foundation.md)
