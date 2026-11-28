# Tools, routes and prerequisites

Every task reachable from the workbench, the screen that starts it, and what it needs. Routes are relative to the loopback workbench. Operations are the shared functions the CLI uses too.

| Task | Entry screen | Operation | Prerequisite | Example input | Useful output |
| --- | --- | --- | --- | --- | --- |
| Overview | `GET /` | `History.list_runs` | — | — | Selected project, latest audit, recent work |
| Start a one-off audit | `GET /audit/new` → `POST /audit` | `seo.audit` | Public site, or the local-network opt-in | `https://example.org` | Run with findings, CSV, inventory, snapshot |
| Audit a saved project target | `GET /projects?project=` → `POST /audit` | `seo.audit` | Project with a target | Target name | Run recorded against the project |
| Run a saved workflow | `POST /workflows/{id}/run` | `seo.audit` via workflow | Saved workflow | Workflow ID | Run with the stored settings |
| Explore a run | `GET /runs/{rid}` | `ui.audit_read` | Run with `snapshot.jsonl` | — | Overview, Findings, Pages, Exports |
| Snapshot checks | `GET /runs/{rid}?tab=exports` → `POST /runs/{rid}/checks` | `seo.check` | Saved `snapshot.jsonl` | Check name or all | Separate run with observations |
| Compare two runs | `GET /compare` → `POST /compare` | `seo.compare` | Two runs, same origin, crawl manifests | Before/after run IDs | New/persistent/resolved findings, page changes |
| Review a finding | `GET /runs/{rid}?tab=findings&rule=` → `POST /runs/{rid}/review-finding` | `History.save_finding_review` | Run belongs to a project | Status + note | Decision in the review queue |
| Review queue | `GET /review-queue` | `History.finding_reviews` | Project with decisions | — | Decisions with current standing |
| Report, CSV, bundle | `GET /runs/{rid}?tab=exports` | `reporting.export` | Run with `snapshot.jsonl` | Optional page filters | HTML report, page CSV, ZIP bundle |
| Excel report | `GET /runs/{rid}/report` → `POST /runs/{rid}/report` | `report.workbook` | Run plus GSC/GA4 datasets | Dataset IDs or imported files | Workbook, match preview |
| Import a measurement | `POST /runs/{rid}/report/import/{gsc\|ga4}` | `research.import` | A saved audit | CSV/TSV/XLSX file | Dataset run usable in the report |
| Connect Google | `GET /tools/search-traffic` → `POST /tools/search-traffic/connect/{service}` | `GoogleConnection.connect` | Desktop OAuth client JSON | Client file path | Property selection, then stored credential |
| Fetch Search Console | `POST /tools/search-traffic/fetch/gsc` | `google.search-analytics` | Connected property | Date range, dimensions | Dataset with `normalized.csv` and `dataset.json` |
| Fetch GA4 landing pages | `POST /tools/search-traffic/fetch/ga4` | `google.landing-pages` | Connected property | Date range, origin, channel | Dataset with sessions and key events |
| Inspect one URL | `POST /tools/search-traffic/inspect` | `google.inspect-url` | Connected property | One URL | Google's recorded assessment |
| Disconnect Google | `POST /tools/search-traffic/disconnect/{service}` | `GoogleConnection.disconnect` | A stored connection | Optional revoke | Local credential removed for that project |
| Keyword and competitor research | `GET /tools/research` → `POST /tools/research` | `research.opportunities` | At least one saved dataset | Owned hostname + datasets | Keyword map, gaps, clusters, briefs |
| Import a research source | `POST /tools/research/import` | `research.import` | — | CSV/TSV/XLSX | Dataset with source hash and row references |
| Sample a public feed | `POST /tools/research/feed` | `research.feed` | Public feed URL | Feed URL, item limit | Article sample with request log |
| Local build QA | `GET /tools/site-qa` → `POST /tools/site-qa` | `quality.build` | Local HTML build folder | Build path | Static findings, imported lab/a11y reports |
| Browser capture | `POST /tools/browser-qa` | `quality.browser` | Playwright Chromium installed | Build path, route, viewport | Screenshot, timings, optional axe JSON |
| Manage saved data | `GET /history/data` | `storage.removal` | — | Scope choice | Runs or workspace data removed |

## CLI-only for now

These have no screen yet. The CLI remains the supported path, and navigation never advertises them:

`wordpress inventory`, `google pagespeed`, `google crux`, `google performance-key`, `google publish-sheets`, `export-dataset`, `lighthouse-run`, `lighthouse-report`, `calibrate`, `variants`, `analyze`, `mcp`.

## Conventions

- Every POST form carries the workspace CSRF token and is rejected without a matching `Origin` header.
- Run URLs, evidence URLs and file downloads keep working across upgrades; list state lives in GET parameters.
- A task that needs a prerequisite names it on screen rather than failing after submission.