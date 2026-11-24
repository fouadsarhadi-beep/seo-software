# SEO Software Roadmap

The local audit, evidence, project and history workflows are in use. The Windows test on Samatoos observed 100 URLs and confirmed Persian article extraction. PR #4 added run archiving and clearer results and downloads. Technical checks, comparisons, local reporting, research and build QA already have CLI entry points. The next milestone brings the most useful of those workflows into the browser workbench.

## Next milestone — Audit, compare and review in the workbench

| Order | From the original plan | Change | Ready when |
| --- | --- | --- | --- |
| 1 | C3, D2–D4 — Technical checks and results | **Implemented and fixture-tested.** Run checks on a saved audit, search and filter results, and open the original evidence. | The workbench and CLI produce matching check reports without making HTTP requests. Unobserved destinations show as unknown, and checks affected by missing markup report partial coverage. Retest on the saved Samatoos run in the Windows workspace. |
| 2 | C4, D2 — Snapshot comparisons | **Implemented.** Select two same-site runs from History and compare observed pages, findings and coverage. | See the manual audit log. |
| 3 | C4, G2 — Content review | **Implemented.** Open page pairs side by side, see their match signals, and save decisions that carry across audits. | See the manual audit log. |
| 4 | D, E2–E5 — Local reporting | **Implemented.** Import or reuse Search Console and GA4 exports, preview how their rows match a saved audit, and download the Excel workbook from the browser. | See the local reporting checkpoint in the manual audit log. |
| 5 | D, F1, G1–G4 — Research from imported data | Add a small **Tools** entry starting with keyword and competitor research. Reuse the importers and existing reports for SERP overlap, competitor gaps, sampled rank changes and content briefs. Start with user-owned exports. | A user can import comparable samples, read a sourced opportunity and trace it back to the source row. The UI shows provider, capture date, locale, device when available and sample coverage. |

Collect pending Windows checks by checkpoint in the [manual audit log](MANUAL_AUDIT_LOG.md). Keep source URLs, page identity, evidence IDs and existing archive state readable across upgrades.

## Follow-on work after the local milestone

| Order | From the original plan | Deliverable and dependency |
| --- | --- | --- |
| 6 | E1–E5, I3 — Live Google and reporting | Start with one authorized Search Console property. Compare a date range against a manual export and verify one URL Inspection result. Then verify GA4 joins, PageSpeed and CrUX with the required access, and an approved Sheets publication that can feed Looker Studio. Each connector can be verified independently when access is available. |
| 7 | F2–F4, G1, G3–G5 — Broader research sources | Benchmark Brave for sample quality, locale coverage and storage terms, verify a live public feed, and assess user-export workflows for SERP and backlink providers. Add sources when they improve a concrete research workflow. Ads Keyword Planner and Trends depend on access and useful data for the target market. |
| 8 | H, I, J — Site QA and operational expansion | Bring local build QA into the workbench when the Tools flow is established, and verify read-only WordPress against an authorized installation. Add saved workflows and scheduling once repeat runs and permissions are reliable. Consider hosted reporting, an installer or native optimization when there is a demonstrated need. |

## Foundation and audit workbench

| Stage | Status | What it covers |
| --- | --- | --- |
| A | Implemented | Installable Python package, workspace configuration, CLI diagnostics and shared network policy. |
| B | Implemented | Bounded website audits from a URL, sitemap or URL list, with saved observations, coverage and evidence-linked findings. |
| C | Implemented | Shared tool runner, SQLite history, projects and targets, offline technical checks and snapshot comparisons. |
| D | Implemented | Local browser workbench for starting and cancelling audits, reviewing evidence and downloading reports. |

## Stage E — Owned-site Google data and reporting

| Step | Status | Deliverable |
| --- | --- | --- |
| E1 | Implemented | Read-only Google consent, property selection and OS-backed credential storage. |
| E2 | Implemented | Search Console Search Analytics exports and single-URL Inspection. |
| E3 | Implemented | GA4 landing-page sessions and key events, with explicit URL matching in the workbook. |
| E4 | Implemented | PageSpeed Insights and local Lighthouse lab reports, plus CrUX field metrics. |
| E5 | Implemented | Preview selected columns in CSV and Excel, then publish an approved selection to a spreadsheet for Looker Studio. |

E1–E5 have automated coverage. Live verification still needs authorized Google properties, a performance API key and a Sheets connection. The keyless PageSpeed check returned HTTP 429.

## After Stage E

| Stage | Work already available | Remaining work |
| --- | --- | --- |
| F — Research sources | Local imports, bounded public RSS and Atom retrieval, and Brave Search samples with source and row references. | Verify a live feed from the deployment environment, benchmark Brave with an eligible key and assess authorized browser exports. |
| G — Keyword and competitor analysis | Keyword maps, SERP clusters, editorial briefs, Search Console refresh candidates, saved page comparisons, sampled rank history and backlink grouping. | Extend discovery beyond selected datasets as sources become available. |
| H — CMS and site quality | Read-only WordPress inventory, static build checks, local Chromium screenshots, axe checks, visual comparisons, access-log summaries and Lighthouse lab reports. | Verify a live WordPress installation. |
| I — Agents and reporting | Scoped MCP analysis, snapshot comparisons, editorial decision reads, and links to selected Looker Studio and Sheets reports. | Consider hosted connectors and scheduling where useful. |
| J — Performance and distribution | Profiled the 300-page audit fixture, replayed saved real pages, reduced extraction overhead and built the 0.4.0 wheel. Windows and Ubuntu CI verify clean wheel installation. | Measure a larger live owner site. Consider native code or a standalone executable if justified. |

[Detailed implementation sequence](../SEO_ANALYSIS_SOFTWARE_ARCHITECTURE.md#14-implementation-sequence--stable-foundation-and-working-vertical-slices) · [Verification and remaining work](IMPLEMENTATION_STATE.md) · [Dated implementation log](IMPLEMENTATION_LOG.md)
