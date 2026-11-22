# SEO Software Roadmap

**Current checkpoint:** Stage E4 is implemented. **Next: Stage E5**, selected exports and Google Sheets publication for Looker Studio.

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
| E5 | **Next** | Publish selected normalized data to Google Sheets for Looker Studio. Local CSV and Excel exports already work. |

E1–E4 have automated coverage. Live verification still needs authorized Google properties and a performance API key. The keyless PageSpeed check returned HTTP 429.

## After Stage E

| Stage | Work already available | Remaining work |
| --- | --- | --- |
| F — Research sources | Import CSV, TSV, XLSX, RSS and Atom with source and row references. | Benchmark a permitted search provider, add controlled live sources and assess authorized browser exports. |
| G — Keyword and competitor analysis | Keyword maps, observed SERP overlap, sampled rankings and competitor gaps, and imported backlinks. | Expand clustering, editorial briefs, refresh prioritization and selected competitor page comparisons. |
| H — CMS and site quality | Static build checks, screenshot comparisons, access-log summaries, and Lighthouse and axe report imports. | Add read-only WordPress access and automated browser measurements. |
| I — Agents and reporting | Scoped MCP tools and optional Looker Studio report links. | Expand report integrations and add reusable workflows or scheduling where useful. |
| J — Performance and distribution | Benchmarked Python content matching and a tested Linux wheel. | Measure larger real-site runs and verify Windows distribution. Consider native code only for a measured bottleneck. |

[Detailed implementation sequence](../SEO_ANALYSIS_SOFTWARE_ARCHITECTURE.md#14-implementation-sequence--stable-foundation-and-working-vertical-slices) · [Verification and remaining work](IMPLEMENTATION_STATE.md) · [Dated implementation log](IMPLEMENTATION_LOG.md)
