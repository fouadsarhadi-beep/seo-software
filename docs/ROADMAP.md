# SEO Software Roadmap

**Current checkpoint:** Stage F has public feed and Brave Search adapters. Stage G now includes keyword clusters, content planning and saved page comparisons. Stage H now includes read-only WordPress inventory and local Chromium and axe checks. **Next:** Stage I reporting and agent work. Automatic local Lighthouse collection remains open in Stage H. Live Google verification remains open.

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
| H — CMS and site quality | Read-only WordPress inventory for published posts, pages and registered custom types, plus media metadata, static build checks, local Chromium screenshots and axe checks, baseline comparison, access-log summaries, and Lighthouse and axe report imports. | Verify a live WordPress installation and add automatic local Lighthouse collection. |
| I — Agents and reporting | Scoped MCP tools and optional Looker Studio report links. | Expand report integrations and add reusable workflows or scheduling where useful. |
| J — Performance and distribution | Benchmarked Python content matching and a tested Linux wheel. | Measure larger real-site runs and verify Windows distribution. Consider native code only for a measured bottleneck. |

[Detailed implementation sequence](../SEO_ANALYSIS_SOFTWARE_ARCHITECTURE.md#14-implementation-sequence--stable-foundation-and-working-vertical-slices) · [Verification and remaining work](IMPLEMENTATION_STATE.md) · [Dated implementation log](IMPLEMENTATION_LOG.md)
