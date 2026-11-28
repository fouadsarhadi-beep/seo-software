# SEO Analysis Software — Unified Architecture & Implementation Specification

**Status:** Single authoritative specification for the first real application and its long-term tool roadmap  
**Working project name:** SEO Analysis Software  
**Date:** 2026-11-21  
**Starting code:** `samatoos-seo-audit.zip`, containing the existing `seo_audit/` Python package and `tests/`; these are functional unreleased tools, not a previously deployed application  
**Verified starting baseline (2026-11-21):** Six CLI commands (`crawl`, `variants`, `analyze`, `review`, `calibrate`, `gsc-pull`); offline suite: **75 passed, 1 skipped** (optional Hazm). This result applies to the supplied archive, not necessarily a later working checkout  
**Package and CLI:** `seo_analysis` / `seo-analysis` on CPython 3.12 or 3.13. Maintained source is in `src/seo_analysis/`.
**Current scope and verification:** See the [roadmap](docs/ROADMAP.md), [implementation state](docs/IMPLEMENTATION_STATE.md) and [manual audit log](docs/MANUAL_AUDIT_LOG.md).


This document consolidates the complete architecture and tool catalogue with the critical review corrections. **It replaces both the earlier architecture draft and its review addendum for implementation purposes.** No separate addendum or predecessor specification is required. If the repository reveals facts that conflict with this document, verify them and record the decision in the living architecture and implementation record.

SEO Analysis Software is a **local-first personal SEO, website analysis, and research workbench**. It is independent of any employer, agency, client, domain, or CMS. Each target is entered explicitly in the CLI, selected from saved targets, or provided through the local UI. The supplied Python audit code is a useful starting implementation, not an old application version to migrate from.

**Development approach:** Establish the coherent module structure and shared contracts from the beginning; implement and verify real end-to-end tools inside that structure. The long-term module catalogue defines extensibility, not a requirement to implement every module before the application is usable. Do not create successive competing architecture specifications. Maintain this document as the architectural source of truth, with concise decisions and implementation state alongside it.

---

# 0. Instructions to the implementing agent

Build the first actual release of a personal local-first workbench that automates SEO, crawling, technical checks, content analysis, analytics, research, CMS inspection and website QA workflows. This is not a multi-tenant SaaS, a public service or a commercial Ahrefs/Semrush replacement.

Use the owner's authorized services and accounts when needed. Data acquisition choices, in order of applicability, include official practical APIs, manual account exports, supported user-authorized browser/REA workflows where permitted, documented public APIs/feeds, and optional paid providers. Ahrefs/Semrush are capability references, not required APIs. Never build authentication, paywall, CAPTCHA, rate-limit or bot-defense bypasses. Treat access terms and data-source policies as applicable constraints.

## 0.1 Implementation rules

1. **Inspect the actual repository before editing.** Read its tree, tests, CLI, dependencies and output formats; verify behavior rather than assuming an earlier conversation or archive is the exact working checkout. The supplied archive contains substantive working functionality: use the concrete baseline inventory in Section 6.1, and verify the source files are present in the coding workspace before proposing changes. If only this document is available, request the archive/repository rather than assuming its code exists.
2. **Treat all predecessor code as unreleased starting material.** Evaluate existing modules and behavior on their merits. The implementing agent may reuse, refactor, reorganize, or entirely replace any component when warranted by the intended application design; preserving an old implementation is never itself a requirement. Preserve useful verified behavior and tests, adapting them to intentional design changes. Do not invent compatibility layers, production migrations, backward-compatibility promises or prior users. Existing CSV exports can be retained when practically useful, not because they are an external compatibility obligation.
3. **Establish one coherent application skeleton.** Define module boundaries, shared data types, configuration, network policy, storage placement and a common tool interface early; validate the abstraction with a real complete workflow. Avoid a speculative plugin marketplace or unused infrastructure.
4. **Use Python for the application initially.** Existing integration-heavy Python tooling is a suitable foundation. Keep Rust available for benchmarked CPU-bound components; C/C++ and C# are not required for this direction.
5. **Make the interface genuinely useful.** CLI first, lightweight local UI later (or early once the core workflow works). UI and CLI use the same application services and evidence model. The number of tools must not translate into a large initial frontend payload.
6. **Keep tools agent-accessible.** Provide typed inputs, structured results, stable IDs and a constrained CLI/JSON interface. MCP/REA are adapters, not alternative implementations of the analysis tools.
7. **Read-only by default.** CMS edits, uploads, publication, remote writes and costly or broad actions require specific permissions and user approval.
8. **Preserve evidence and caveats.** Distinguish observed data, third-party measurements, estimates, heuristics, AI interpretations and missing data. Topic similarity does not demonstrate cannibalization.
9. **Control access and data movement.** The HTTP layer enforces target scope and protections; credentials belong in the operating system's secure store; explicit connector permissions govern external data sharing.
10. **Treat external text as untrusted.** Crawled content, search snippets, forums and imported documents must never gain authority over tool calls, system prompts or file/network access.
11. **Respect crawling and source constraints.** Robots defaults, approved scopes, quotas, delays and no bypass of CAPTCHAs or access controls.
12. **Verify implementations against behavior.** Add regression and offline integration tests for fixes, cross-module behavior and connector boundaries. Report what was actually tested; do not claim an authorized Google or live external test unless performed.
13. **Allow necessary coordinated changes.** A coherent foundation or end-to-end feature may touch multiple modules. Use Git commits at meaningful tested checkpoints; avoid arbitrary limits on task count or file scope.
14. **No default organization or site.** No hardcoded organization URL, default employer site or implicit remembered target. Site-specific operations use explicit, validated runtime targets.
15. **Keep documentation synchronized.** Maintain this architecture, short ADRs for consequential decisions and `docs/IMPLEMENTATION_STATE.md` for finished work, tests, decisions and next actions. Do not proliferate competing plans.

## 0.2 Initial read-only repository assessment

Before changing the repository, report the actual structure, available functionality, commands, offline test results and gaps against the first working milestone in Section 17. Identify proven defects, unverified assumptions and architectural decisions that require resolution. Show the proposed package skeleton, core module boundaries, service/data contracts and a logical implementation sequence, including the first functioning vertical slice and relevant test cases.

The assessment is **not** a migration plan from a deployed old product. Do not assume historical users, application data or backward-compatible commands. Review the proposed architecture critically where the repository or technical constraints justify a change. Wait for the owner's instruction before applying the first changes.

## 0.3 How to use this specification

The full catalogue (Section 6) is a long-term capability map. The engineering sequence (Section 14) defines how to establish the application structure while delivering useful tools. The first milestone's acceptance criteria (Section 17) define the first run the owner can perform independently. New capabilities may be added in coordinated increments without redesigning the application's foundation.

A ready-to-use first agent message is in Section 20. The agent should read this one document and the actual repository; earlier architecture/addendum files are not inputs to implementation unless explicitly provided for historical reference.

---

# 1. Product vision and operating model

## 1.1 What SEO Analysis Software is

SEO Analysis Software is a **general-purpose, local-first SEO analysis and website research application**. It is not tied to a specific company, customer, domain, industry, CMS or employer. The user chooses the website, domain, sitemap, URL list, or local source repository to inspect for each run. It combines focused tools for:

- Website crawling and technical SEO.
- Search visibility and keyword research.
- Competitor research and SERP observation.
- Forum/community research and brand/topic monitoring.
- Content inventory, content gap and content maintenance.
- Analytics and conversion context.
- Website performance, accessibility and visual QA.
- WordPress and generic website/CMS/project inspection.
- Research and workflow automation through an external LLM agent.

It should be useful for both:

1. **CMS-managed sites**, particularly WordPress.
2. **Custom-coded, static, headless, generated, and “vibe-coded” sites**, where there may be no CMS API at all.

The system must not assume that all sites are WordPress sites or that source code is always available. It should support both public-URL inspection and optional local repository/build-output inspection.

## 1.2 Scope boundaries

- Not a public SaaS or commercial multi-tenant product.
- Not an attempt to recreate the proprietary web indexes of Ahrefs or Semrush.
- Not a system that requires all data to come from vendor APIs.
- Not tied to a preconfigured website, company domain, industry, or customer account.
- Not a replacement for Google Search Console, GA4, Lighthouse, Ahrefs, Semrush or Looker Studio.
- Not an automatic website editor or deployment agent in its initial form.

The platform may independently implement useful analysis and workflow functionality inspired by established SEO suites, using data the owner can legitimately access. When a feature depends on a large proprietary backlink, keyword or clickstream database, state that limitation instead of pretending a local crawler can reproduce it.

## 1.3 Operating model

Default deployment:

- Runs locally on the user's computer.
- Uses one local workspace with optional saved projects and site profiles.
- Can run a one-off analysis against a user-entered target without requiring the user to create a saved project first.
- Stores project metadata in SQLite and larger source/output artifacts on disk.
- Calls remote services only when a tool explicitly needs them.
- Keeps credentials in the operating system's credential store, not in project files.
- Exposes a local CLI and later a minimal web UI bound to loopback.
- Can be called by REA or another compatible agent using structured commands and later MCP.

No server, paid cloud database or always-on process is required for the first version.

## 1.4 Core product principles

### Small tools, composed into workflows

A tool should do one thing well. A workflow combines tools to answer a larger question. Example: a competitor research workflow may run SERP discovery, collect competitor URLs, inspect selected pages, compare topics, then save an evidence-backed opportunity list.

### Useful when disconnected

Crawling, parsing, URL checks, schema checks, page similarity, local source inspection, CSV/XLSX imports and many quality checks should work without Google or vendor credentials.

### Evidence is not all the same

Keep these source categories distinguishable:

- First-party website observations.
- Google/Search Console/Analytics measurements.
- Third-party SEO platform data.
- Search engine result observations.
- Public community/forum data.
- User-supplied exports or notes.
- Derived calculations.
- AI-generated interpretation.

Every observation has source, retrieval method, timestamp, scope, locale and limitations where relevant.

### User controls data movement

The system should be capable of sending selected data to Google, an LLM, a search provider or another remote service, but only through an explicit connector/tool permission. Do not let one tool silently pass the entire workspace to another service.

### No fake precision

Do not produce an arbitrary overall SEO score as the central product. Show the issue, evidence, coverage, uncertainty and next action. Vendor metrics such as Ahrefs DR or Semrush Authority Score remain vendor-specific indicators, never Google ranking factors.

---

# 2. Technology architecture: Python first, Rust selectively

## 2.1 Recommended initial stack

| Layer | Initial choice | Reason |
|---|---|---|
| Core tools and orchestration | Python | Existing codebase, broad ecosystem, rapid integration |
| HTTP and parsing | Requests/httpx, BeautifulSoup or lxml | Mature and sufficient for initial crawl volumes |
| Local database | SQLite | Local, simple, transactional, no server |
| Artifact storage | Filesystem, content-addressed where useful | Easy to inspect, copy and back up |
| CLI | Typer or argparse (choose a clean unified CLI) | Typed options and structured output |
| Local HTTP/UI server | FastAPI | Typed routes, OpenAPI, async support and later MCP integration |
| UI templates | Jinja2 + HTML + CSS; HTMX optional | Server-rendered and lightweight |
| UI JavaScript | Small vanilla JS modules | Only for controls that need client interaction |
| Data validation | Pydantic or existing typed models | Shared schemas for CLI/API/MCP |
| Google OAuth | Google-supported OAuth client libraries | Avoid hand-written token protocol |
| Tests | pytest + local mock servers | Extend current offline testing approach |
| Native optimization later | Rust (PyO3/maturin or subprocess) | Use only for measured CPU-bound bottlenecks |

Do not introduce React/Vue/Svelte or a large component framework for a simple private utility UI unless interaction complexity later justifies it. A large number of tools does not require a large JavaScript bundle: render only the active page and its form, and fetch large result tables on demand.

## 2.2 Python versus Rust, C/C++ and C#

### Python: best starting choice for this repository

Python is the correct initial choice because:

- The supplied Python crawler and analysis modules already have tests that can be retained.
- Most crawl time is network waiting, DNS/TLS, remote server response and polite delays—not raw CPU execution.
- Async I/O or a bounded thread pool can support many concurrent requests while respecting per-host limits.
- Google API, OAuth, WordPress, parsing, reporting and Persian NLP libraries are readily available.
- The owner can add and change tools quickly without maintaining language bindings across the whole application.

Use bounded concurrency, caching, streaming and incremental analysis before considering a language rewrite. Python's GIL is relevant to CPU-bound Python threads; it does not make ordinary network I/O crawls automatically slow. CPU-heavy stages can use processes, native libraries or a Rust module.

### Rust: a strong later option, not a reason to rewrite now

Rust is attractive for:

- High-throughput URL processing and deduplication.
- Large-scale shingling, similarity candidate generation and graph operations.
- Fast content hashing and parsing pipelines.
- Memory-efficient processing of large crawl datasets.
- A future self-contained desktop/backend component.

Adopt it only after profiling a realistic SEO Analysis Software workload. Keep the Python contract stable and implement a narrow Rust component behind it. Prefer a JSONL/stdin-stdout subprocess interface initially if it is easier to maintain. Use PyO3/maturin only when a Python extension provides a measurable benefit.

Rust does not make a vanilla JS interface faster by itself, and it does not reduce frontend DOM/layout costs. Backend language and frontend rendering are separate decisions.

### C/C++: not recommended as the primary application language

C and C++ can be extremely fast, but they offer little advantage for this current mix of HTTP APIs, parsing, OAuth, data integration and personal workflows. They add build, memory-safety and interoperability overhead. Native C/C++ libraries may be useful through existing Python packages, but do not write the application in C/C++.

### C#: technically capable, but not the best migration target now

Modern .NET is performant and has strong HTTP, concurrency, desktop and database support. It becomes a reasonable primary option if the product is deliberately redesigned as a Windows-first desktop application and the owner wants a unified .NET UI/backend. Today, that would require replacing the existing Python modules and rebuilding their integrations without solving a demonstrated performance problem.

**Decision:** Python application now; lightweight HTML UI; benchmark; Rust for isolated hotspots later. Keep C# as a future replatform option only if the product direction changes.

## 2.3 Avoid confusing UI scale with tool count

The app may eventually have dozens of tools without loading dozens of widgets at startup.

Use:

- Server-rendered navigation and pages.
- Tool registry metadata to populate a tool directory.
- A form generated only for the selected tool.
- Paginated server-side tables.
- On-demand detail panels.
- Lazy-loaded charts only on report views that need them.
- A small shared CSS system.
- No persistent background polling unless the user opens a running-job screen.

The limiting factors will be poorly designed queries, huge DOM trees, loading every dataset at once, or unnecessary chart libraries—not the raw number of tool definitions.

---

# 3. High-level architecture

Use a **local-first modular monolith**. Run one application process at first. Keep module boundaries strong, but do not split into microservices.

```text
┌──────────────────────────────────────────────────────────────┐
│ Interfaces                                                     │
│ CLI | Local HTML UI | REA/agent CLI contract | MCP (later)    │
└─────────────────────────────┬────────────────────────────────┘
                              │
┌─────────────────────────────▼────────────────────────────────┐
│ Application services                                           │
│ Tool runner | Workflow runner | Project service | Job service  │
└─────────────────────────────┬────────────────────────────────┘
                              │
┌─────────────────────────────▼────────────────────────────────┐
│ Shared domain                                                   │
│ Project | Site | Page | Snapshot | Evidence | Finding | Run    │
│ ToolSpec | Connector | DataPolicy | Decision | Artifact         │
└─────────────────────────────┬────────────────────────────────┘
                              │
┌─────────────────────────────▼────────────────────────────────┐
│ Tool modules                                                    │
│ Crawl | Technical SEO | Content | Keywords | SERP | Community  │
│ Competitors | GSC | GA4 | Looker | CMS | Accessibility | QA    │
└─────────────────────────────┬────────────────────────────────┘
                              │
┌─────────────────────────────▼────────────────────────────────┐
│ Adapters and infrastructure                                     │
│ HTTP | Google APIs | REA/Browser bridge | Import/export        │
│ SERP/search providers | Forum APIs | CMS | SQLite | Artifacts  │
│ Secret store | Cache | Rate limiter | Egress policy             │
└──────────────────────────────────────────────────────────────┘
```

### Layer rules

- The UI and CLI call the same application services.
- MCP is an adapter over the same tool registry and runner.
- Tools do not import UI/CLI modules.
- Provider-specific response formats do not leak into domain models without a source/provider field.
- Workflows orchestrate tools; they do not copy tool logic.
- Tool outputs are persisted consistently with provenance and coverage.
- Connectors are data acquisition mechanisms; a tool is the user-facing operation that applies useful logic to the data.
- No tool may bypass the shared DataPolicy or secret access layer.

## 3.1 Repository structure

The current foundation uses these boundaries. Keep the root architecture document authoritative. Add directories for later capabilities when a working feature needs them.

```text
SEO_ANALYSIS_SOFTWARE_ARCHITECTURE.md
README.md
pyproject.toml
uv.lock
config.example.toml
docs/
  adr/                   # consequential implementation decisions
  IMPLEMENTATION_STATE.md
src/seo_analysis/
  cli.py                 # user input, command dispatch and presentation
  app/                   # interface-independent application services
  core/                  # tool metadata, configuration, paths and network scope
  web/                   # HTTP transport, discovery, robots and page extraction
  analysis/              # technical checks, content similarity and editorial review
  reporting/             # tabular exports and run manifests
  storage/               # SQLite migrations, history indexing and recovery
  connectors/            # provider formats and acquisition code
tests/                   # offline unit and end-to-end fixtures
```

Stage B stores page observations atomically. Stage C indexes run manifests, artifacts and page evidence in SQLite, with optional saved projects and targets. The local UI, research sources, CMS tools and agent adapters will call these same services. Each source retains its own authority, coverage and permissions.

**Do not put mutable application data inside the Git checkout by default.** On Windows use an appropriate per-user application-data directory (e.g. `%LOCALAPPDATA%\SEOAnalysisSoftware`, resolved with `platformdirs`); use equivalent per-user paths on other operating systems. Store SQLite databases, run artifacts, caches and logs there. User export paths are configurable and distinct from internal application state. Do not place active WAL-mode SQLite databases in synchronized/network folders. Secrets live in the OS credential store, not the database or repository.

## 3.2 Install and operational conventions

- Choose and document a supported Python version range in `pyproject.toml` after checking repository/library compatibility; use reproducible dependency locking for the developer environment.
- Document Windows CMD/PowerShell setup with `venv`, editable installation and `seo-analysis --help` / offline fixture smoke tests. Support paths containing spaces and Persian characters.
- Add a minimal `seo-analysis system doctor` operation showing Python/runtime paths, safe config diagnostics and dependency health; never display credentials.
- Provide basic backup/export, app-data inspection, and state reset/recovery instructions. Introduce SQLite schema migrations before altering persisted schemas.
- Defer packaging as a Windows executable until the installed Python application works end to end.

---

# 4. Core domain and data model

The database should represent work and evidence—not just a cache of provider responses.

## 4.1 Hierarchy

```text
Workspace
  ├── Ad hoc runs
  │    └── Target snapshot (URL / sitemap / URL list / local source)
  │         ├── Tool runs
  │         ├── Evidence and findings
  │         ├── Crawl snapshots
  │         └── Reports / exports
  │
  └── Saved Projects (optional)
       ├── Saved site targets
       │    ├── Production / staging / development profiles
       │    ├── Allowed hosts and network scope
       │    ├── Sitemap and crawl configuration
       │    └── Page-type rules
       ├── Competitors
       ├── Source connections
       ├── Tool runs and history
       ├── Evidence and findings
       ├── Human review decisions
       ├── Workflows
       └── Reports / exports
```

A site-specific run always has a target snapshot, but its `project_id` is nullable. This supports immediate one-off analysis while preserving optional saved workspaces for recurring audits and research.

## 4.2 Main entities

### Analysis target (required for site-specific tools)

An analysis target is the website or source selected for one tool run. It is created from user input and does not have to be saved as a permanent project.

- User-provided starting URL, domain, sitemap URL, URL-list file, or local source directory, depending on the tool.
- Normalized origin and exact user-supplied input retained separately.
- Allowed hostnames and redirect scope.
- Target type: public website, explicitly authorized private/staging website, or local repository/build output.
- Sitemap discovery result and sitemap sources, if relevant.
- robots.txt policy and crawl configuration, if relevant.
- Optional locale, country, language and device context.
- Optional authentication connection reference; never store raw credentials in the target record.
- Creation time and the run that first used the target.

For a one-off run, persist the target snapshot with the run for reproducibility, but do not require creation of a named Project. A user may explicitly save the target for reuse.

### Project

A Project is an optional saved workspace that groups one or more analysis targets and their historical work. It is a convenience for continuity, not a tenant, customer, company or agency account.

- Stable ID and human name.
- Zero or more saved analysis targets; no default website is required.
- Main locale, country and language(s), when useful.
- Project type: CMS, static, custom-coded, headless, unknown, or mixed.
- Production/staging/development environments, when applicable.
- Competitor list.
- Page classification rules.
- Data connections and per-project access policy.
- Created/updated timestamps.

### Saved site target

A saved site target is a reusable profile derived from an Analysis target. It is optional. Keep hostname/origin separate from external property identifiers:

- Origin and allowed hostnames.
- Environment label.
- Sitemap sources.
- robots.txt policy.
- Local repository/build directory, if provided.
- GSC property identifier.
- GA4 property ID.
- CMS connection reference.

## 4.3 Target modes and data authority

A user-supplied URL identifies a **target**, not an entitlement to private data. The run must distinguish:

| Mode | Allowed initial capabilities | Authorization boundary |
|---|---|---|
| **Public website** | Public crawl, public metadata/technical/content checks, permitted public research | Crawl scope, robots and network policy |
| **Owned / connected website** | Public checks plus authorized GSC, GA4, CMS and other account data | Explicit selected OAuth/property/CMS connection; URL alone proves no ownership |
| **Explicitly approved local / staging site** | Local private-network site and optional local source/build inspections | Narrow per-run or saved host/subnet/path allowlist, not broad private-network access |

Always keep each property's source identity and permission distinct. A public competitor target never implicitly grants private Google/CMS access.

## 4.4 Runtime website/source input (initial UX requirement)

The application has no built-in primary website. A target is chosen for each run unless the user explicitly selects a saved target.

### Accepted inputs

- Website URL, e.g. `https://example.com/`.
- Domain/origin where the CLI can safely normalize it to an HTTP(S) URL; ask for scheme when ambiguous rather than guessing silently.
- Sitemap URL, e.g. `https://example.com/sitemap_index.xml`.
- Text/CSV file containing seed URLs.
- Local repository or build-output directory for source-level and static-site checks, only after the user explicitly selects the path.

### CLI behavior

- Interactive commands prompt for missing required target inputs.
- Non-interactive commands require explicit flags/arguments and return machine-readable validation errors when missing.
- A tool's schema declares whether it needs a website target, a local directory, a keyword/query, an account property, an imported file, or no external target.
- Never reuse the last URL silently. A recent-target picker may be offered interactively, but the user must select it.
- Show the normalized target and allowed host scope before broad crawls or private-network access.

### Future UI behavior

The first screen should let the user paste a URL or sitemap and start an audit. Advanced options (crawl depth, page limit, user agent, content selectors, locale, authentication connection, allowed additional hosts) remain secondary. A saved-project selector is optional, not a prerequisite.

### Discovery requirements

- Treat explicit URL, sitemap URL, seed URL file and local source directory as distinct target kinds; validate each.
- For a website URL, consult `robots.txt` sitemap declarations, then configured known sitemap locations. Record exactly how URLs were discovered.
- If no sitemap is usable, offer a **bounded internal-link crawl** with disclosed limits and an explicit decision; do not fail mysteriously or expand to unrelated hosts.
- Never implicitly reuse a previous site for a non-interactive run. For missing required input, provide an actionable usage error. Support a human CLI prompt when interactive.
- Avoid infinite URL discovery through calendars, facets, tracking/query variants and repeating pagination. Canonicalize comparison keys carefully without collapsing semantically distinct URLs.

### Scope and safety

- Public website input is subject to robots policy, rate limits, redirects and SSRF protections.
- Private/staging/local targets require explicit per-run or saved-target authorization.
- A redirect to a new host is not automatically permission to crawl that host.
- A URL supplied to analyze a site does not authorize scanning its surrounding IP range, unrelated subdomains or internal network.
- Local source-directory input must be selected explicitly and constrained to approved filesystem paths.

### Page identity and snapshot

Store the **requested URL**, **final URL**, **first and final HTTP status**, **normalized matching key**, **declared HTML/HTTP canonical**, **Google-selected canonical** (where inspected), **GSC-reported page URL**, **GA4 landing page path/query**, response metadata, content hash and snapshot/run ID as separate source identities. Never overwrite the exact observed/source URL with a normalized key.

Cross-source mapping needs explicit match type and confidence, plus unmatched/ambiguous row reporting. GSC page metrics are generally canonical-oriented; GA4 landing paths may not contain domain identity and use different attribution and metric definitions. **Do not equate GSC clicks with GA4 sessions, add them together as a uniform metric, or turn missing provider rows into zero.**

### Query / keyword / SERP observation

A keyword is not a SERP observation. A SERP is not a GSC ranking metric. Store them separately.

A SERP observation should include:

- Query text and normalized query key.
- Search engine and provider.
- Country, location code/name, language, device and OS where available.
- Captured timestamp and result depth.
- Result type and feature types (organic, ads, local pack, AI Overview, PAA, news, images, video, etc.).
- Result rank, URL, domain, title, snippet and structured fields returned by provider.
- Raw artifact reference, provider task ID, cost/units and coverage.

### Community observation

Store source platform, community/subreddit/category, post/thread ID, title, body/excerpt, author pseudonym/ID if permitted and needed, timestamp, score/reaction counts if available, permalink, retrieval method, source policy notes and raw artifact reference. Avoid collecting unnecessary personal information.

### Evidence

Every observation must record:

- Source type and source name.
- Retrieval mode: official API, user export, REA/browser session, public crawl, SERP provider, manual entry, calculated or AI-derived.
- Observed time and period when applicable.
- Entity identifiers and dimensions.
- Raw source artifact or source URL when retained.
- Completeness/coverage and known limitations.
- Data classification and allowed downstream uses.

### Finding

Stable ID/fingerprint, rule code/version, affected entities, severity, status, evidence IDs, confidence definition, first/last seen, recommendation and review history.

### Tool run

Unique run ID, tool and version, parameters (secrets redacted), optional `project_id`, immutable target snapshot/reference when relevant, start/end times, status, sources called, data egress, cost/usage, coverage, warnings, artifacts and logs.

### User decision

Keep historical decisions immutable. Link them to the relevant content hashes/snapshot. If content or supporting data changes significantly, re-open a review rather than silently suppressing the candidate forever.

---

# 5. Universal tool architecture

## 5.1 ToolSpec

A tool definition should provide enough information for CLI help, UI form generation, agent discovery, permissions and cost confirmation. **Implement the smallest workable contract around the first real crawl/audit tools; the full example below is an extensible target shape, not a checklist of fields to implement before any feature works.**

Example:

```python
ToolSpec(
    id="seo.internal-links",
    version="1.0.0",
    title="Internal link audit",
    description="Build and inspect the internal page-link graph.",
    category="SEO / Site structure",
    input_schema={...},
    output_schema={...},
    permissions=["project.read", "network.site_read"],
    data_inputs=["crawl.snapshot"],
    external_destinations=[],
    default_read_only=True,
    estimated_cost=None,
    supports_cli=True,
    supports_ui=True,
    supports_agent=True,
)
```

Tool metadata must also declare:

- Whether network access is needed.
- Allowed destination hosts/providers.
- Whether it accesses local files and which approved directories.
- Whether credentials are needed and which named connection.
- Data classifications accepted and emitted.
- Whether the operation is expensive or potentially mutating.
- Expected run duration/scale where possible.
- Required predecessor artifacts (if any).

Use JSON Schema or a typed model that can be exported to JSON Schema. Avoid defining separate input validation for CLI, UI and MCP.

## 5.2 Standard result envelope

Every run should produce a predictable result:

```json
{
  "schema_version": "1.0",
  "run_id": "...",
  "tool_id": "seo.internal-links",
  "tool_version": "1.0.0",
  "status": "succeeded",
  "started_at": "...",
  "finished_at": "...",
  "summary": {},
  "findings": [],
  "evidence": [],
  "artifacts": [],
  "sources": [],
  "effective_permissions": [],
  "usage": {},
  "data_egress": [],
  "coverage": {},
  "warnings": []
}
```

Statuses: `queued`, `running`, `succeeded`, `partial`, `failed`, `cancelled`.

Missing data is not zero. Partial coverage must be visible. A tool must not claim it completed a task when a provider returned incomplete results or a connector failed. Use atomic artifact writes and resumable run records where practical. In `--json` mode, print **only valid machine-readable JSON to stdout**; send progress and diagnostics to stderr. Never dump bulk page data or secrets into agent/terminal output: expose references to saved artifacts.

## 5.3 Tool categories and identifiers

Use stable namespaces such as:

- `web.*`
- `seo.*`
- `research.*`
- `analytics.*`
- `content.*`
- `cms.*`
- `quality.*`
- `report.*`
- `system.*`

Tool IDs should describe the capability, not the provider, where possible. Provider-specific variants can be separate connector IDs under the same tool.

## 5.4 CLI / agent interface

The initial experience must not require a pre-created project or a hardcoded website. Every site-specific tool must accept a target supplied at runtime. Support both interactive prompts for a person using CMD/Terminal and explicit flags for scripts/agents.

Recommended commands (adjust names to the actual CLI framework, but preserve these capabilities):

```bash
# Easiest one-off audit: URL supplied directly
seo-analysis audit https://example.com

# Interactive mode: prompt for a URL or sitemap when omitted
seo-analysis audit

# Explicit crawl scope and structured output
seo-analysis crawl --url https://example.com --limit 100 --json

# Sitemap supplied directly when the user already knows it
seo-analysis crawl --sitemap https://example.com/sitemap_index.xml --json

# Use a URL list instead of sitemap discovery
seo-analysis crawl --urls-file ./urls.txt --json

# Inspect and reuse optional saved projects/targets
seo-analysis project list
seo-analysis project create "Example Website"
seo-analysis site add --project example-website --url https://example.com
seo-analysis run seo.technical-audit --project example-website --json

# A one-off tool run can use --url without --project
seo-analysis run seo.technical-audit --url https://another-example.org --json

# Research tools that need a website can accept --url; query-only tools need no site target
seo-analysis run research.serp-search --query "example keyword" --country US --json
seo-analysis report export --run latest --format xlsx
```

Target-input behavior:

1. If a required target is supplied as a positional URL or `--url`, validate and use it.
2. If no target is supplied and the command is interactive, prompt once for a website URL, domain, sitemap URL or URL-list path as appropriate.
3. If no target is supplied in non-interactive mode, return a clear validation error and usage example; never silently select a previous or default website.
4. When the input is a website URL/domain, offer/discover `robots.txt` and sitemap locations. Do not assume `/sitemap.xml` is the only sitemap path. Report the discovered source and allow an explicit `--sitemap` override.
5. When the input is a sitemap URL, treat it as the discovery seed and derive the allowed site origin(s) carefully. Do not silently expand to unrelated hosts.
6. A one-off target is associated with the run and can be saved as a reusable target/project only when requested.
7. GSC/GA4 tools may accept a website URL for convenience, but the actual data scope is the selected Search Console property or GA4 property. Require explicit connection/property selection; do not infer access solely from the domain.
8. Tools that don't need a website (keyword clustering from imported data, CSV validation, report formatting, query-only SERP search, etc.) must not demand one.

Requirements:

- `--help`, stable flags, predictable exit codes.
- `--json`/JSONL machine output; human output separate.
- `--non-interactive` and explicit scope parameters for agent usage.
- `--dry-run` for workflows with multiple source calls or potential writes.
- Explicit confirmation for expensive, broad, external or mutating operations.
- Credentials never printed.
- Large datasets written as artifact files, not dumped into terminal context. An authorized agent can discover tools, execute a bounded run, and retrieve evidence/artifact references through this contract without obtaining credentials or a universal shell capability.

---

# 6. Tool catalogue: what to build

This catalogue uses Ahrefs and Semrush as a **feature-discovery reference**, not as an instruction to reproduce their proprietary datasets or use their APIs. Each capability is assigned an effort level and data dependency. Add tools when they provide real standalone value.

## 6.1 Existing Python audit foundation — concrete integration baseline

**Actual starting artifact:** `samatoos-seo-audit.zip` contains the `samatoos-seo-audit/` directory with `seo_audit/` (a Python package), `tests/`, `README.md`, `requirements.txt`, and `config.example.json`. These are **implemented, working tools**, not merely sample code or earlier architecture drafts. The archive has no `src/seo_analysis/` package or shared application/UI framework yet. Treat these modules as available starting material, not mandatory building blocks: the architecture may incorporate, restructure, or replace them after inspection.

The starting package runs through `python -m seo_audit <command>`. Its six working commands are:

| Existing command | Implemented workflow | Where it belongs in the new application |
|---|---|---|
| `crawl` | Sitemap-led HTTP audit with redirects, robots handling, extraction, Persian-compatible CSV inventory, snapshot and crawl manifest | `web.crawl` and initial SEO audit workflow |
| `variants` | Suggests joined/split Persian spelling variants for **human approval**; stores accepted mappings | Persian-language content-analysis settings/review utility |
| `analyze` | Offline similarity, canonical diagnostics, issue summary; optional GSC CSV inputs; emits pairs and manifests | `content` similarity and `seo.technical-audit`/canonical tools |
| `review` | Interactive, resumable decisions on flagged pairs with supporting evidence | Review queue, independent of CLI/UI presentation |
| `calibrate` | Compares scoring thresholds against saved human decisions; its sampled-data limitations must be disclosed | Similarity calibration / evaluation tool |
| `gsc-pull` | Optional read-only GSC Search Analytics `query × page` acquisition using OAuth; API path is mocked in the existing tests, **not verified with a live property** | Google GSC connector and query-map source |

**Source-to-responsibility inventory.** These filenames describe the baseline archive. Section 3.1 and the implementation state track the current checkout:

| Existing file(s) | Functionality to reuse or deliberately refactor |
|---|---|
| `cli.py`, `__main__.py` | Current argument parser, interactive prompts and six command entry points; redesign as the unified CLI without losing useful commands |
| `crawl.py`, `sitemap.py`, `fetch.py`, `robots.py` | Crawl orchestration, XML sitemap discovery, bounded HTTP fetching, redirect/robots behavior |
| `extract.py`, `classify.py`, `indexability.py`, `canon.py`, `urls.py` | HTML extraction, page-type classification, indexing/canonical checks and URI comparison |
| `fa_text.py`, `stopwords_fa.txt`, `variants.py` | Persian text normalization, stopword data, optional Hazm and human-approved spelling variants |
| `similarity.py`, `analyze.py` | TF-IDF/bigram topical matching, shingles, containment, title/H1 overlap, pair explanations and analysis pipeline |
| `gsc.py` | Optional GSC CSV parsing and authenticated Search Analytics acquisition |
| `review.py` | Persistent editorial decisions and threshold calibration |
| `report.py` | CSV formula guarding, CSV writing and manifest writing; other workflow modules also emit JSON/JSONL evidence |
| `config.example.json`, `requirements.txt`, `README.md` | Existing configuration shape, installation dependencies and documented workflows; replace or extend intentionally |
| `tests/test_*.py`, `tests/conftest.py` | Existing offline regression fixtures, CLI end-to-end tests and optional dependency tests; adapt to the new interfaces while retaining their validated behaviors |

The existing workflow produces, among other files, `inventory.csv`, `snapshot.jsonl`, `similar_pairs.csv`, `canonical_report.csv`, `issues.txt`, `pairs.json`, `decisions.jsonl`, `decisions.csv`, `calibration.txt`, `crawl_manifest.json` and `analysis_manifest.json`. The first working application need not preserve the exact old filenames or positional CSV format, because there are no released compatibility obligations; **the underlying capabilities, review decisions and inspectable evidence must not disappear unnoticed**. If an existing feature is deferred, document its status and retain a clear route to reintroduce it through the shared tool interface.

**Limitations at assessment time.** The implementation state records which items have been addressed:

- `seo_audit/cli.py` has `DEFAULT_SITEMAP = "https://samatoos.ir/sitemap_index.xml"`; `crawl` can silently use it when no target is supplied. Remove this behavior and require explicit input (or an interactive prompt). The GSC prompt and sample/test fixtures also contain site-specific examples; make product-facing examples generic without requiring fixtures to lose all realistic test data.
- `seo_audit/crawl.py` uses a Samatoos-branded HTTP user-agent token; use an application-appropriate identifier instead. Project identity, configuration and normal runtime defaults must not depend on a particular company or website.
- The old commands cover sitemap-led audits; a generic website input, sitemap discovery, bounded link crawl fallback, common tool runner, optional project persistence and UI are **new requirements**, not already implemented features.
- Apply verified audit findings where applicable: stopword-induced false bigrams, exact canonical-target redirect validation, reserved-character-safe URI normalization, GSC canonical-aware joins/missing-data distinctions, calibration sample bias, content-change-aware review decisions and incomplete-extraction markers.
- The suite was **75 passed, 1 skipped** when rerun against this uploaded archive; passing those tests does not establish live GSC connectivity, public crawl safety against all network edge cases or future product readiness. Keep and extend the regression tests rather than replacing them with superficial placeholders.

**Integration rule:** For each existing module, decide whether to reuse, move, wrap temporarily, split, refactor, or replace it based on the resulting application's boundaries. The old implementation does not constrain the new design. Don't build parallel replacement logic while leaving a functioning implementation disconnected. Don't preserve the old package layout solely for historical compatibility, and don't silently delete useful tested behavior. The goal is one cohesive application with a functional inherited core, not a blank scaffold that starts over.

## 6.2 Website crawling and technical SEO tools

### A. `web.crawl` — P0

- Crawl from sitemap, internal links, provided URL lists, or combinations.
- Scope by host/path/page type and depth.
- Store complete response and redirect history.
- Extract title, description, headings, robots, canonical, hreflang, links, images, schema, language and main content.
- Record page types and extraction confidence.
- Conditional requests, content hashing and incremental snapshots.
- Respect crawl policy, request budgets and domain concurrency.
- Centralize URL/host/scheme validation in the **lowest HTTP fetch layer**, including the first request, redirects and any future adapter calls. Check actual connected destination addresses against the public/private policy; a separate DNS check before a normal unrestricted connect is not enough to prevent rebinding.
- Define user-visible configurable defaults for max pages, depth, total requests, duration, per-host concurrency/rate, retry attempts, sitemap recursion/size and max response bytes. Reject or stop at unsafe URL-parameter traps.
- Support `Ctrl+C` cancellation, well-defined partial results and statuses (`succeeded`, `partial`, `cancelled`, `failed`, `no_pages_found` where relevant). Persist any valid evidence before reporting an incomplete run.

### B. `seo.technical-audit` — P1

- HTTP errors and soft-404 candidates.
- Redirect chains/loops and internal links to redirects.
- Indexability and robots directives.
- Canonical target validity and conflicts.
- Sitemap/robots/canonical consistency.
- Missing/duplicate titles and descriptions.
- H1 and heading structure observations.
- hreflang validation.
- Pagination and parameterized URL review.
- HTTPS and mixed content.
- Internal/external broken links.
- Language and encoding issues.

Do not classify every missing description or multiple H1s as a ranking error.

### C. `seo.sitemap-reconcile` — P1

Compare sitemap, discovered links, indexability, HTTP state, canonical target, lastmod and content hash. Report URL classes: in sitemap only, discovered only, redirected, non-200, noindex, canonicalized elsewhere, duplicate variant and uninspected.

### D. `seo.schema-audit` — P1

Parse JSON-LD/Microdata/RDFa where feasible, validate syntax and common graph relationships, identify duplicate/conflicting entities and compare selected properties with visible content. Separate Schema.org validity from Google rich-result eligibility.

### E. `seo.internal-links` — P1

Build a directed link graph. Report click depth, inbound/outbound counts, orphan candidates, broken/redirected targets, anchor text, generic anchors, canonical variants and link distribution. Show crawl coverage to avoid claiming a URL is orphaned when it was outside the crawl scope.

### F. `seo.log-file-analysis` — P3

Import web-server access logs (Apache, Nginx, LiteSpeed/OpenLiteSpeed and common formats). Parse bot user agents, status codes, response time, URL patterns, crawl frequency and bot access to important/low-value URL groups. This should be an import-only analysis tool initially. Provide configurable bot identification and confidence because user-agent strings can be spoofed.

### G. `seo.indexation-monitor` — P3

Track URL state across crawl snapshots and selected GSC URL Inspection samples. Do not imply that local crawl status equals Google's index status.

## 6.3 Keyword and content research tools

### A. `content.query-map` — P1/P2

Map GSC queries to pages, devices, countries and periods. Show impressions, clicks, CTR and average position with the Search Console caveats preserved.

### B. `content.keyword-discovery` — P2

Generate candidate keywords from:

- GSC query history.
- Google Ads Keyword Planner API if account access and project configuration allow it.
- SERP related searches/autocomplete observations from a provider or user-supplied source.
- Competitor pages and headings.
- Public forums/community questions.
- Uploaded keyword lists from existing tools.
- Site content and internal search logs if supplied.

Keep raw candidate discovery separate from search volume/difficulty metrics. A phrase discovered in a forum is not evidence of monthly search volume.

### C. `content.keyword-metrics` — P2

Attach metrics only when sourced: search volume, trend, CPC, paid competition, keyword difficulty, SERP features, clicks potential and intent labels. Record metric provider, database, country, language, date and units. Do not merge estimates from different providers as if equivalent.

Google Ads Keyword Planner's `KeywordPlanIdeaService` can generate keyword ideas from keyword, URL and site seeds and return historical metrics. API access is subject to project access levels, permissible use and request limits; this should be an optional Google connector, not assumed to work without setup. Reference: https://developers.google.com/google-ads/api/docs/keyword-planning/generate-keyword-ideas and https://developers.google.com/google-ads/api/docs/api-policy/access-levels

### D. `content.keyword-cluster` — P2

Cluster keywords using lexical similarity, SERP URL overlap and optionally multilingual embeddings. Keep methods and confidence visible. Do not infer identical intent from word similarity alone.

### E. `content.content-gap` — P2

Compare a site's indexed/performance query coverage with selected competitor pages and SERPs. Differentiate:

- GSC-proven queries for the owned site.
- Competitor queries estimated by a third-party dataset.
- Queries inferred from competitor page text.
- Search-result observations.

### F. `content.content-refresh` — P2

Find pages with historical traffic/impression declines, stale facts, changed SERPs, outdated screenshots/product versions or pages whose content no longer satisfies the query. Recommendations must show the time series and evidence.

### G. `content.brief-builder` — P2/P3

Build evidence-backed briefs containing intent, queries, SERP patterns, questions, competitor headings, internal links and source URLs. LLM can help organize and draft; it must not fabricate volume or competitor metrics.

### H. `content.internal-link-suggestions` — P2

Suggest source/destination pages and anchor concepts from crawl content and topic/query evidence. Suggestions only; no automatic CMS changes.

## 6.4 Google first-party and Google ecosystem tools

### A. Google Search Console — P1

Use read-only OAuth scopes where possible.

Tools:

- `analytics.gsc-performance`
- `analytics.gsc-query-page`
- `analytics.gsc-query-trends`
- `analytics.gsc-page-performance`
- `seo.gsc-url-inspection`
- `seo.gsc-sitemap-status`
- `seo.gsc-property-list`

Dimensions where supported: query, page, date, device, country, search type/search appearance. Preserve response aggregation, date range, filters and dataState. Search Analytics is bounded and can omit rows; anonymized queries are unavailable; absent rows are not necessarily zero. API docs: https://developers.google.com/webmaster-tools/v1/searchanalytics/query and https://developers.google.com/webmaster-tools/limits

URL Inspection returns Google's indexed-version assessment; it is not a live test of an arbitrary page. Use it selectively and respect quotas. Docs: https://developers.google.com/webmaster-tools/v1/urlInspection.index/inspect

### B. Google Analytics 4 — P1

Tools:

- `analytics.ga4-organic-landing-pages`
- `analytics.ga4-landing-page-conversions`
- `analytics.ga4-channel-comparison`
- `analytics.ga4-content-performance`
- `analytics.ga4-event-health`

Use the GA4 Data API for reports and, if needed, Admin API for authorized property discovery. Check dimension/metric compatibility and quotas. Preserve attribution/property settings and distinguish sessions, engaged sessions, key events and revenue from GSC clicks. Docs: https://developers.google.com/analytics/devguides/reporting/data/v1 and https://developers.google.com/analytics/devguides/reporting/data/v1/quotas

### C. Google Ads Keyword Planner — P2

Implement only if the owner can obtain suitable API access and has a real use for its keyword metrics. It requires a configured Google Ads API project and access level/permissible use. It is not a frictionless public keyword-volume endpoint. Docs: https://developers.google.com/google-ads/api/docs/keyword-planning/overview

### D. Google Trends — P3 / access-dependent

Google announced a Trends API alpha in July 2025. It provides a rolling five-year range, regular interval aggregation and regional/subregional interest data, but access is limited to accepted alpha testers. Therefore:

- Create an adapter interface, but do not make it a dependency.
- Enable it only when the owner has approved access.
- Otherwise accept manual CSV exports or other explicitly identified trend sources.
- Do not rely on reverse-engineered unofficial endpoints as a stable core integration.

Docs: https://developers.google.com/search/apis/trends and announcement https://developers.google.com/search/blog/2025/07/trends-api

### E. PageSpeed Insights, Lighthouse and CrUX — P1

Separate lab diagnostics from field data:

- Lighthouse lab audit (PageSpeed Insights API or local Lighthouse CLI/browser runner).
- CrUX current field data.
- CrUX History API where historical data is needed.
- Optional site-owned RUM only if deliberately installed.

Capture LCP, INP, CLS and other available metrics with device/granularity/period/sample context. Google's PSI docs state that CrUX field data is planned to be removed from PSI responses; use the dedicated CrUX API for durable field-data integration. Docs: https://developers.google.com/speed/docs/insights/v5/get-started and https://developer.chrome.com/docs/crux/api

### F. YouTube Data and Analytics — P3

If the owner manages YouTube content, keep it as a distinct content channel. Use YouTube Data API for public channel/video metadata and YouTube Analytics/Reporting APIs for authorized channel performance. Do not mix video views with website organic sessions. Connect videos to website landing pages only through explicit links/UTM or content mapping.

Docs: https://developers.google.com/youtube/v3 and https://developers.google.com/youtube/analytics

### G. Google Business Profile — P3 / eligibility-dependent

Potential local SEO tools include profile metadata, locations, reviews and performance metrics where the account and API eligibility allow them. Keep Google Business Profile access as a later optional connector; do not assume every individual account or profile is eligible for every API.

### H. Google Search result access — important limitation

Do not build a new tool around Google's Custom Search JSON API. Current Google documentation says it is closed to new customers and existing customers must transition by January 1, 2027. The retired Bing Search APIs are also not a current option (retired August 11, 2025). For general web search and Google SERP observations, use:

- A selected SERP/search data provider.
- User-initiated browser/REA capture where permitted.
- Other currently supported search APIs.
- Search Console for the owner's own search performance.

References: https://developers.google.com/custom-search/v1/overview and https://learn.microsoft.com/en-us/lifecycle/announcements/bing-search-api-retirement

## 6.5 Looker Studio integration — include as a real integration, but understand its role

Assume the user means **Looker Studio (formerly Google Data Studio)**. It should be supported as a reporting destination and asset-management integration, not treated as a source of Google search/analytics data. If the user instead means **Google AI Studio**, that is a separate Gemini model prototyping/development product; it belongs under a future LLM-provider configuration, not the reporting integration described in this section.

There are four practical integration patterns:

#### Mode 1 — Google Sheets export/sync (first implementation)

1. SEO Analysis Software generates normalized report tables.
2. User exports or synchronizes selected tables to Google Sheets.
3. Looker Studio uses its native Google Sheets connector.
4. Reports can be opened or embedded back into the local SEO Analysis Software UI using the user's approved report URL.

This is the simplest and safest first path for a local-only personal tool. Do not upload sensitive project data automatically; each sync should be explicitly enabled and limited to selected tables/fields.

#### Mode 2 — BigQuery reporting warehouse (later, optional)

For larger/historical datasets, SEO Analysis Software can export selected normalized tables to BigQuery. Looker Studio can use the native BigQuery connector. This introduces cloud project configuration, billing, storage, query cost, identity and retention responsibilities. It is not required for the first release.

#### Mode 3 — Looker Studio Community Connector (later, useful)

A Community Connector is built with Google Apps Script and can read from an internet-accessible data source. SEO Analysis Software could expose a narrow, authenticated, read-only reporting endpoint and a private Community Connector could request selected project datasets.

Important limitation: Apps Script runs in Google's cloud. It cannot call a user's `127.0.0.1`/localhost SEO Analysis Software server. A live connector therefore needs one of:

- A deliberately exposed HTTPS endpoint behind strong authentication and a narrow read-only token.
- A controlled relay/tunnel that the owner explicitly enables for the reporting session.
- A cloud-hosted read-only replica/export of selected tables.

Do not expose the whole local database or admin API to make this work. Use a read-only report endpoint with per-project scope, field allowlists, expiration, revocation and rate limits. If the system remains local-only, prefer Mode 1.

Community Connector docs: https://developers.google.com/data-studio/connector and reference https://developers.google.com/data-studio/connector/reference

#### Mode 4 — Looker Studio API and Linking API

The Data Studio/Looker Studio API can search/manage assets and permissions, but it is available only to users in an organization with Google Workspace or Cloud Identity. It does not expose deeper report internals such as all filters, sections and dimensions. It is not a generic report data extraction API.

The Linking API can open a report-creation flow with preconfigured data source parameters, including Community Connectors. It can be used to create a one-click setup flow from a SEO Analysis Software report template, but it does not replace data storage or ingestion.

Docs:

- Asset/permissions API: https://developers.google.com/data-studio/integrate/api
- API reference: https://developers.google.com/data-studio/integrate/api/reference
- Linking API: https://developers.google.com/data-studio/integrate/linking-api
- Embedding: https://docs.cloud.google.com/data-studio/embed-a-report

#### Looker Studio tool IDs

- `looker.assets.list` — list/search available reports, subject to Workspace/Cloud Identity eligibility.
- `looker.assets.permissions` — inspect permissions, if authorized.
- `looker.report.open` — open a stored report URL.
- `looker.export.prepare` — prepare a report-ready Sheets/CSV dataset.
- `looker.connector.config` — generate configuration/links for a future Community Connector.

Do not claim that SEO Analysis Software can programmatically inspect or rebuild every part of a Looker report using the asset API.

## 6.6 SERP, search and web research tools

This is a major part of the product, because the owner wants research sources that may not be directly crawlable by a generic agentic crawler.

Build a **Research Source Hub** with multiple acquisition modes. Do not treat every result as a page that SEO Analysis Software must crawl directly.

### A. `research.web-search` — P2

Search a query across configured search sources. Normalize result title, URL, snippet, domain, rank, result type, source provider, locale, language, captured time and raw reference.

Potential adapters:

- REA's existing search/browser capability, if available.
- A supported third-party web-search API (select after comparing coverage, price and output fields).
- Search provider APIs such as Brave Search or other maintained services.
- Search provider exports.

Do not hard-code a provider as the only route.

### B. `research.google-serp` — P2

Collect Google SERP observations by query, location, country, language, device and depth. Preserve result blocks and SERP features rather than storing only ten blue links.

Potential providers include DataForSEO and SerpApi. DataForSEO documents Google Organic, AI Mode, Maps, Local Finder, News, Images, Autocomplete and other endpoints. SerpApi documents structured Google organic/local/news/knowledge graph and related result types. Compare current pricing and result coverage before selecting a primary provider.

References:

- DataForSEO Google SERP API: https://docs.dataforseo.com/v3/serp-google-overview/
- DataForSEO pricing: https://dataforseo.com/pricing/google-serp
- SerpApi Google Search API: https://serpapi.com/search-api

Provider choice must be configurable. Record query cost, location accuracy, result depth and missing SERP feature coverage. Never present a provider's result as an exact universal Google result; SERPs vary by location, language, device, time and personalization.

### C. `research.serp-tracker` — P2/P3

Track selected keyword sets on a schedule. Store a time series of ranking observations and SERP features. Keep a deliberate crawl/search budget and make the location/device context part of the tracked keyword key.

### D. `research.serp-overlap` — P2

Compare top-ranking domains/URLs across keyword sets to identify shared competitive sets, potential keyword clusters and competitor overlap. Distinguish observed URL overlap from an inferred intent cluster.

### E. `research.autocomplete` and `research.related-queries` — P2/P3

Collect autocomplete, related searches and question suggestions only through documented/allowed sources or a selected search provider. Keep source and locale visible; these are suggestions, not measured search volumes.

### F. `research.site-query` — P2

Run targeted domain searches (for example, `site:domain.tld phrase`) through a supported search source. Treat returned results as provider observations, not a complete index inventory. Compare with sitemap and GSC data.

### G. `research.source-fetch` — P2

Fetch a selected page/thread only where the source allows access and SEO Analysis Software has permission. Use source-specific APIs/feeds first. Respect robots/policies for ordinary web crawl. If content is available only through a user's authenticated session, use the dedicated browser/REA flow with user authorization; do not export cookies into SEO Analysis Software.

### H. Source acquisition options for restricted or agent-inaccessible pages

When a generic crawler or agent cannot directly visit a source, SEO Analysis Software should support, in this order:

1. A public/official platform API or RSS/JSON feed.
2. A search provider that legitimately supplies indexed result metadata.
3. A user-provided export or saved page.
4. A user-authorized REA/browser workflow using an existing session, subject to service rules.
5. Manual URL/notes capture.

Do not bypass a CAPTCHA, login requirement, paywall, bot challenge, blocked endpoint or access policy. An agent being blocked does not create permission to evade the block. The architecture should make it easy to use an alternate authorized data path.

## 6.7 Forum and community intelligence tools

### A. `research.community-search` — P2

Search relevant discussions for real questions, pain points, product comparisons, recurring terminology, objections and unmet needs.

Potential sources:

- Reddit API where access and application permissions are available.
- Stack Exchange API.
- Discourse forums with documented API access.
- Public forum RSS/Atom feeds.
- Public forum search pages through a supported search provider.
- User-provided exports/bookmarks.

Useful source documentation:

- Reddit developer API: https://developers.reddit.com/docs/capabilities/server/reddit-api
- Stack Exchange API: https://api.stackexchange.com/docs
- Discourse API: https://docs.discourse.org/

### B. `research.community-topic-map` — P2/P3

Cluster discussion subjects and extract recurring question patterns. Preserve thread/post URLs, dates and source labels. Avoid collecting unnecessary personal profiles or inferring sensitive personal attributes.

### C. `research.question-mining` — P2

Extract distinct questions and classify them into informational, comparison, troubleshooting, transactional or support intents. The LLM may classify and summarize, but each question should retain its source reference and a link to the original context.

### D. `research.brand-mentions` — P3

Monitor public indexed mentions of brands/products/competitors using search sources and supported community APIs. This is not a complete firehose or guaranteed exhaustive monitoring service.

### E. `research.ai-visibility-observations` — P4

A future manual or API-backed tool to record brand/product citations in AI answers. Store the exact prompt, model/provider, date, market, answer and citation URLs. Do not compare different models as if they share a common ranking scale. Do not automate accounts or bypass provider controls.

## 6.8 Competitor and market research: feature map inspired by Ahrefs/Semrush

Use these products to understand what SEO practitioners need. Recreate the **workflow and analysis capabilities** where possible, not proprietary database coverage.

### Reference capability inventory

This inventory is based on the vendors' public product/feature pages. Product packaging and availability change, so use it as a capability checklist rather than a promise that every feature is included in every subscription.

**Ahrefs capability families:**

- Site Explorer: domain/URL overview, organic pages and keywords, competing domains, backlink profile, referring domains, anchors, outgoing links and link opportunities.
- Keywords Explorer: keyword ideas, search volume and other keyword metrics, difficulty estimates, SERP overview, related terms and keyword clustering.
- Site Audit: technical/on-page crawl, broken links, metadata and other site-health checks.
- Rank Tracker: ranking observations across tracked keywords, locations and devices, plus SERP feature/visibility tracking.
- Content Explorer: discover pages/content by topic, links, mentions and engagement/search-related filters.
- Brand Radar: brand and competitor appearances/citations across selected AI answer/search environments.
- Additional adjacent capabilities shown in the current product catalogue include Web Analytics, Bot Analytics, SEO Toolbar and AI content assistance.

**Semrush capability families:**

- Keyword Overview and Keyword Magic Tool: keyword ideas, metrics, related terms and intent/keyword grouping.
- Keyword Strategy Builder: keyword organization into topic/content plans.
- Domain Overview, Organic Research and Top Pages: domain-level competitor and organic visibility estimates.
- Keyword Gap and Backlink Gap: compare domains for missing keyword/link opportunities.
- Position Tracking: scheduled positions, locations/devices, competitors and SERP feature changes.
- Site Audit and Log File Analyzer: technical crawling and server-log inspection.
- Backlink Analytics, Backlink Audit and Link Building: backlink profile analysis and prospect workflows.
- On Page SEO Checker, SEO Writing Assistant, topic/content research and content auditing: page-level content recommendations and content workflows.
- Traffic Analytics and Market Explorer: estimated competitor traffic/audience/market research, based on external datasets and models.
- Sensor, AI Visibility, Prompt Research and brand/sentiment tools: SERP volatility and emerging AI answer visibility/brand research.
- Additional local, advertising, social and reporting toolkits exist but are lower priority for this website/SEO workbench.

The independent SEO Analysis Software implementation should prioritize capabilities that can be reproduced with the owner's own crawl, GSC/GA4, open/search-source data and imported exports. Large web indexes, backlink graphs, clickstream models and vendor-specific AI citation databases remain external-data-dependent.

### A. Domain overview — P2

`competitor.domain-overview`

Combine available evidence:

- Domain and subdomain inventory.
- Top pages discovered by SERP observations.
- GSC data for owned properties only.
- Competitor organic keyword estimates from a user export/provider, if supplied.
- Backlink/referring-domain metrics only where sourced.
- Page types, topic coverage and content publication patterns.
- Tech stack signals from public HTML/headers where reliable.

Show the source per metric; don't synthesize estimated traffic as actual traffic.

### B. Competitor discovery — P2

`competitor.discover`

Use:

- SERP overlap across known keyword sets.
- Similar ranking URLs/domains.
- Search result competitors for target topics.
- User-specified competitors.
- Public industry directories/forums when relevant.

Output candidate competitors with evidence and confidence, not an unexplained list.

### C. Organic research and top pages — P2/P3

`competitor.organic-pages`, `competitor.organic-keywords`

Can be partially estimated from SERP snapshots, competitor page crawl and imported vendor exports. Reliable domain-wide organic keywords and traffic estimates generally require a large search dataset/provider; mark these features as provider-dependent.

### D. Keyword gap — P2/P3

`competitor.keyword-gap`

Compare the owner's GSC queries/keyword map against competitor keyword exports and observed SERPs. Clearly label the dataset used for each competitor. Provide gaps, overlaps, shared SERPs and pages, not fabricated volume.

### E. Content gap / Content Explorer equivalent — P3

`competitor.content-discovery`

Find relevant high-performing public content by topic, query, link references or search visibility using SERP/search providers and public sources. A full web-wide content database is expensive and cannot be reproduced with a local crawl alone.

### F. Backlink research — P3/P4

Tools:

- `competitor.backlink-profile`
- `competitor.referring-domains`
- `competitor.backlink-gap`
- `competitor.link-intersect`
- `competitor.lost-new-links`
- `competitor.broken-backlinks`

A local crawler can find links from pages it visits, but it cannot discover the complete internet-wide backlink graph. For meaningful domain-wide backlink data, use exports from an account the owner has, a supported provider interface or a dedicated dataset. Store referring URL, target URL, anchor, link attributes, first/last seen, provider and confidence.

### G. Rank tracking and SERP feature tracking — P2/P3

`competitor.rank-tracker`, `competitor.serp-features`

Can be implemented on top of a SERP provider or controlled browser observations. Record locale/location/device, engine, query and capture time. Do not use GSC average position as if it were a daily rank tracker.

### H. Site audit — P1

A strong local Site Audit equivalent is feasible and should build on the existing Python crawler, technical checks, internal-link graph, schema validation, Lighthouse and accessibility tools. This is one of the highest-value capabilities that does not require a paid SEO database.

### I. Content optimization and writing assistance — P2/P3

`content.page-optimizer`, `content.brief-builder`, `content.update-plan`

Use query evidence, current SERPs, page text, headings, related pages, internal links and selected competitor samples. Keep recommendations evidence-backed. LLM suggestions are drafts, not facts.

### J. AI search / brand radar — P4

`research.ai-visibility-observations`, `research.prompt-discovery`, `research.citation-monitor`

Potential capabilities include prompt set tracking, brand mentions, citations, competitor comparisons, sentiment and topic gaps. This is emerging and provider/model dependent. Keep raw prompts and responses with full provenance, and do not imply a standardized market-wide AI visibility metric.

### K. Market / traffic estimates — P4 / provider-dependent

Semrush-like traffic analytics and market estimates depend on large panels, clickstream, modeling and/or search datasets. This cannot be honestly reconstructed from the owner's site crawl. Support imports/providers later, but label values as estimates and do not prioritize this as a local algorithm project.

## 6.9 Website and web-design QA tools for WordPress and custom-coded sites

The platform should support public URL inspection and optional local source/build inspection.

### A. Generic site profile — P1

Detect observable site characteristics:

- Static vs rendered behavior indicators.
- Common frameworks/CMS fingerprints (best-effort, not definitive).
- Sitemap, robots, canonical, language and response headers.
- Publicly visible route patterns and assets.
- Site structure and page types.

### B. WordPress connector — P2

Read-only REST API connection for:

- Posts/pages/custom post types.
- Status, slug, dates, author, parent, categories/tags.
- Media attachments and alt text.
- SEO plugin fields only where officially exposed or safely mapped.
- Menus/settings only if exposed and explicitly authorized.

Use a dedicated least-privilege user and HTTPS Application Password. Do not assume every plugin's metadata is available from core REST endpoints.

### C. Static/custom-code project inspection — P1/P2

Allow user to select a local repository or build directory. Read-only tools can inspect:

- HTML templates and generated HTML.
- Meta tags, headings, canonical/hreflang, JSON-LD.
- Internal links and asset paths.
- Sitemap and robots files in repo/build output.
- Redirect configuration where known (for example nginx/Apache/hosting config files selected by user).
- Framework/build configuration (Astro, Next.js, Nuxt, Vite, static generator, custom app) without assuming a framework.
- Route manifest/output URL coverage.
- Broken local asset references.
- Build artifact size and static performance hints.

Never recursively scan the whole computer. Require explicit project directory selection and enforce filesystem allowlists.

### D. `quality.accessibility-audit` — P2

Use a browser engine and axe-core for automated checks, with a clear note that automated tools cannot certify full WCAG conformance. Add manual-review checklist output for keyboard, focus, semantics and contrast cases.

### E. `quality.visual-regression` — P3

Playwright screenshots for fixed viewports, screenshot diffing and approved baselines. Normalize or mask dynamic regions (dates, rotating content, ads, animations) to reduce false positives. Require explicit browser rendering because it is more resource intensive.

### F. `quality.asset-audit` — P2

Check broken assets, large image files, image dimensions, modern formats, alt text presence, font loading and CSS/JS asset weights. Distinguish source-level unused code analysis from observed network load; they are different.

### G. `quality.performance-audit` — P1/P2

Combine local Lighthouse lab tests, CrUX field data and optional RUM. Do not blend the measures. Track waterfall/transfer size, LCP/INP/CLS diagnostics, unused CSS/JS where supported and render-blocking resource signals.

### H. `quality.security-baseline` — P2

Read-only hygiene checks: HTTPS, TLS expiry, HSTS/security headers, mixed content and obvious accidental public artifacts. Not a penetration test. Active security testing must be separately scoped and explicitly approved.

---

# 7. Source acquisition and connector model

SEO Analysis Software must support multiple ways of collecting data. An external API is only one of them.

## 7.1 Acquisition modes

| Mode | Good for | Design |
|---|---|---|
| Official API | GSC, GA4, Ads, community APIs, CMS | Typed connector, OAuth/API key, quota handling |
| User export/import | Ahrefs/Semrush UI exports, spreadsheets, reports | File import, schema detection, provenance |
| REA/browser bridge | User-directed authenticated workflows | External agent owns browser session; SEO Analysis Software receives approved structured results/artifacts |
| SERP/search provider | Google SERPs, general search, location-specific observations | Provider adapter, cost and context tracking |
| Public crawl/API/feed | Public websites, Discourse, RSS, open APIs | Respect access policy and rate limits |
| Manual evidence | URLs, notes, copied excerpts | Preserve author/date/source URL and mark manual |

## 7.2 REA and authenticated browser workflow

Do not assume what REA can do; inspect its actual skill/tools and integrate only through a supported interface.

Preferred first contract:

1. SEO Analysis Software creates a research/export request with a stable `request_id`, schema and allowed fields.
2. REA performs the user-authorized browser/API task using its own session and credentials.
3. REA returns a structured JSON/CSV artifact plus source URLs, timestamps, retrieval method and any warnings.
4. SEO Analysis Software validates the result, records provenance and imports it into the project.
5. The owner can inspect and approve before it is used in analysis.

Do not copy browser cookies, local-storage tokens or passwords into SEO Analysis Software. REA should remain the credential/session boundary. Browser automation should not bypass CAPTCHAs, paywalls, bot challenges or service access controls. If a service disallows automation, use its export or a permitted method.

A later MCP server can expose the same import and workflow operations. SEO Analysis Software should not need to know which agent performed the research.

## 7.3 Ahrefs/Semrush account use without making vendor APIs foundational

Build a generic `account_export` importer rather than dedicated API clients as an initial requirement.

Support:

- CSV/XLSX exports from keyword reports.
- Organic competitor reports.
- Top pages/top keywords.
- Backlink and referring domain exports.
- Rank-tracking exports.
- Site Audit issue exports.
- Content research exports.
- Brand/AI visibility exports where available.

Import flow:

1. User selects file and project.
2. Parser identifies provider/export type, or asks the user to choose.
3. Preview columns and sample rows.
4. Map columns into normalized fields.
5. Preserve original file and parsed raw rows.
6. Record account/provider, export date, database/country, filters and any known limits.
7. Warn when a metric is estimated, sampled, truncated or provider-specific.

For account UI automation, use REA only where permitted and user-authorized. Prefer direct export workflows over brittle scraping of dashboards. Do not write passwords or automate subscription/account changes.

## 7.4 Search/SERP provider selection

Do not choose a single SERP/search provider permanently. Add an adapter interface and compare candidates with a small benchmark set before implementation.

Potential providers to evaluate include DataForSEO and SerpApi for Google SERP structure; for general web search, evaluate currently maintained services such as Brave Search API or other suitable search APIs. Consider coverage, locale precision, result feature types, latency, price, terms, history and export options. Provider feature sets and prices change; re-check at implementation time.

The retired Bing Search APIs must not be included in a new design. Google's Custom Search JSON API is closed to new customers and existing users are directed to transition by 2027-01-01. Don't use either as a foundation.

## 7.5 Community APIs and forum sources

Use official APIs where possible. Build one small adapter per forum platform as needed, rather than a universal scraper.

- Reddit: use the current approved developer API path if access is available.
- Stack Exchange: use its API, caching and backoff behavior.
- Discourse: use documented endpoints/API and instance rules.
- Other forums: prefer RSS/Atom, JSON endpoints, public search, export or user-authorized REA capture.

Store the source URL and post/thread identifier. Do not assume that a search index result grants permission to fetch the full page or that all forum content may be retained indefinitely.

## 7.6 External research provider interface

A provider connector should declare:

- Provider and product name.
- Retrieval method (API, user export, REA, public page).
- Capabilities and supported regions/languages.
- Required credentials and scopes.
- Quota/cost model.
- Rate limits and concurrency.
- Data fields returned.
- Retention/use restrictions known to the owner.
- Whether raw responses may be stored or sent to LLMs.

Connector code may normalize data, but it must not silently remove source-specific distinctions.

---

# 8. Data storage, history and provenance

## 8.1 Local-first storage

Application state and artifacts live in the user-specific application-data directory, not inside the repository. Use `platformdirs` to resolve safe, platform-appropriate locations. On Windows a conventional target is `%LOCALAPPDATA%\SEOAnalysisSoftware`; the exact path is displayed by `system doctor`. Avoid network/synced active SQLite databases, especially in WAL mode. User-selected exports remain separate from app state. Keep schema migrations and backup/recovery instructions as part of storage lifecycle.

Start with SQLite for:

- Projects, sites and connection references.
- Tool specs and run metadata.
- Page identities and snapshot summaries.
- Evidence, findings and decisions.
- Keyword/SERP/community observations.
- Import manifests and connector usage.

Use filesystem artifact storage for:

- HTML snapshots where allowed/needed.
- Raw API JSON where retention permits.
- CSV/XLSX/PDF exports.
- Screenshots and visual diffs.
- Log files and larger datasets.

Do not store secrets in SQLite or artifacts. Keep a secret reference/connection ID only.

## 8.2 Data lineage

Cross-source joins must carry raw identity, normalized candidate key, transformation, match confidence and unmatched/ambiguous reasons. Preserve GSC, GA4, HTTP fetch and Google URL Inspection identifiers independently. A connector reports absent, sampled, truncated, permission-denied and zero-valued results distinctly.

A normalized row must retain source/provider, retrieval mode, timestamp, date range, locale, database, device, query scope, filters, unit, raw artifact reference and coverage where applicable.

Examples:

- GSC metric: property × query × page × date × device × country × search type.
- GA4 metric: property × landing page × date range × channel × device × dimension/metric definitions.
- SERP observation: query × engine/provider × location × language × device × capture time × result depth.
- Backlink observation: source URL × target URL × provider × first/last seen.
- Community observation: platform × community × post ID × captured time.
- Local page snapshot: exact URL × crawl run × fetch time × response state.

## 8.3 History and diffs

Compare runs to identify:

- New, removed, changed, redirected and re-canonicalized pages.
- Changed metadata/schema/content hashes.
- New/resolved technical findings.
- Keyword/query visibility changes.
- SERP competitor movement.
- New/lost backlink observations (only according to source coverage).
- Community mention/question trends.
- Visual layout changes and regression diffs.

Always qualify history by source and completeness. A missing provider row may be caused by data limits, not a true zero or disappearance.

---

# 9. Security and data-flow design

Security is a core requirement, especially because tools may combine website data, private Google metrics, account exports and external LLM/agent connections.

## 9.1 Local boundary by default

- Bind the local UI/API to `127.0.0.1` by default.
- Do not listen on LAN/public interfaces unless the user explicitly enables it.
- Do not create tunnels automatically.
- Do not include a remote admin port by default.
- Validate Host and Origin headers and use CSRF protection for state-changing UI requests.
- Use a per-install local session/secret for the UI if appropriate; localhost is not a universal security boundary against malicious local websites.

## 9.2 Data classification

Start with simple classifications:

| Class | Examples | Default handling |
|---|---|---|
| Public web data | Public page text, public SERP result, public schema | May be processed locally; external use still source/policy-aware |
| Project data | Internal URL lists, crawl snapshots, unpublished content | Local only unless a specific connector is approved |
| Account data | GSC/GA4 metrics, vendor exports, private CMS metadata | Restricted; never send to an LLM by default |
| Sensitive data | User identifiers, private form submissions, credentials, tokens | Exclude/minimize; never send to remote LLMs |
| Secrets | OAuth refresh tokens, API keys, WordPress passwords | Secret store only; never in logs, model context or artifacts |

Each tool must declare the data classes it reads, emits and sends externally.

## 9.3 Egress policy / data transfer permission

Create a shared `DataPolicy` / `EgressPolicy` service.

Before an external connector or remote LLM receives data, it must know:

- Destination/provider.
- Purpose of transfer.
- Project and data types involved.
- Fields or excerpts being sent.
- Whether content is public, project-private or account data.
- Whether the connector is allowed to retain or cache it.
- Whether the user has enabled this use.

Provide controls such as:

- `allow_public_page_text_to_llm`.
- `allow_selected_project_metadata_to_llm`.
- `allow_gsc_metrics_to_llm`.
- `allow_ga4_metrics_to_llm`.
- `allow_upload_to_google_sheets`.
- `allow_looker_studio_sync`.
- `allow_browser_research_via_rea`.

These are illustrative settings, not a giant permission matrix to implement immediately. Start with a small permission model that is clear and deny-by-default for private/account data.

A run summary must show `data_egress` entries such as provider, purpose, selected fields, approximate size and approval state. Never send an entire database or workspace by default.

## 9.4 Secrets and OAuth

- Use the OS credential manager/keyring for API keys and refresh tokens.
- Use OAuth authorization code flow with PKCE/loopback for installed/local apps when supported.
- Request read-only and minimum viable Google scopes.
- Store connection metadata separately from credentials.
- Provide disconnect/revoke and local credential deletion. Before the first live Google connection, replace the starting code’s plaintext JSON refresh-token storage with the agreed secure store; connection metadata alone belongs in SQLite.
- Redact tokens, authorization headers, cookies and passwords from logs and exception messages.
- Do not ask the owner to paste account passwords into prompts or config files.
- WordPress uses a dedicated user and an Application Password over HTTPS, not the administrator password.
- REA/browser credentials remain in the REA/browser environment; do not import session cookies.

## 9.5 SSRF and network scope protection

Because users can enter URLs, crawler tools must defend against server-side request forgery:

- Reject localhost, loopback, link-local, multicast and cloud metadata IPs by default for ordinary public-site scans.
- Resolve DNS and validate the **actual connected destination IP**, enforcing policy at the transport boundary. Do not rely on DNS prevalidation followed by an unchecked request; test DNS-rebinding behavior.
- Revalidate every redirect destination; don't allow redirect chains to jump into private networks.
- Protect against DNS rebinding and alternate IP representations.
- Enforce allowed host/path scope.
- Set connect/read timeouts, response-size limits and content-type restrictions.
- Do not fetch arbitrary `file://`, `ftp://`, gopher or other unsupported schemes.

However, the owner also needs to inspect local development/staging websites. Provide an explicit **Local/Private Target Mode** that requires the user to select/approve the target host or subnet for a specific project. Do not make private network access a global default. Keep separate policies for public crawling and explicitly authorized local QA. The shared fetcher must apply policy even when called directly by a new tool, not only when called via a sitemap collector. Restrict ports/schemes and redirect hops; protect against alternate IP forms and metadata endpoints. Tests should cover a private address, a hostname resolving privately, a rebinding simulation, a redirect to private address, a disallowed scheme/port and an explicitly allowlisted local fixture.

## 9.6 Prompt injection and agent security

Crawled HTML, snippets, forums, documents, code comments and imported exports are untrusted input. They may contain instructions such as “ignore previous instructions” or requests to reveal secrets.

Rules:

- Treat retrieved content strictly as data/evidence.
- Never allow page text to change tool permissions or egress policy.
- Keep system instructions and retrieved source content in separate contexts.
- Only call tools exposed by the approved ToolRegistry.
- Use explicit scopes for every agent request.
- Never expose raw secrets, credentials or local filesystem paths to an external model.
- Require confirmation for writes, expensive runs, broad crawling, browser actions and private-data uploads.
- Keep a machine-readable action log with source, tool, arguments summary and approval record.

## 9.7 Backup, deletion and retention

- Provide export/backup of SQLite plus artifacts.
- Provide project deletion and provider-data purge where feasible.
- Configure retention for raw HTML, screenshots, logs and imported account files.
- Do not retain third-party source data beyond what is needed or permitted.
- Backups may contain private analytics and crawl data; protect them accordingly.

---

# 10. Workflows

Workflows should be plain, inspectable compositions of existing tools.

## 10.1 Baseline site audit

```text
web.crawl
  -> seo.sitemap-reconcile
  -> seo.technical-audit
  -> seo.internal-links
  -> seo.schema-audit
  -> quality.security-baseline
  -> quality.performance-audit (optional/browser/API)
  -> report.site-audit
```

## 10.2 Search visibility diagnosis

```text
analytics.gsc-performance
  -> content.query-map
  -> seo.gsc-url-inspection (selected URLs)
  -> analytics.ga4-organic-landing-pages (optional)
  -> research.google-serp (selected queries)
  -> report.visibility-investigation
```

## 10.3 Cannibalization review

```text
web.crawl
  -> content.similarity-analysis
  -> analytics.gsc-query-page
  -> content.query-overlap
  -> seo.internal-links
  -> human.review
```

## 10.4 Competitor discovery and gap

```text
research.google-serp / research.web-search
  -> competitor.discover
  -> competitor.page-sample
  -> web.crawl (selected public pages within scope)
  -> content.topic-map
  -> competitor.keyword-gap (if provider exports available)
  -> report.competitor-opportunities
```

## 10.5 Forum/community research

```text
research.community-search
  -> research.question-mining
  -> research.community-topic-map
  -> research.web-search (cross-check)
  -> content.keyword-cluster
  -> report.audience-questions
```

## 10.6 Website launch/redesign QA

```text
web.crawl (staging)
  -> seo.technical-audit
  -> seo.schema-audit
  -> quality.accessibility-audit
  -> quality.performance-audit
  -> quality.visual-regression
  -> compare with production snapshot
  -> report.release-checklist
```

## 10.7 Looker Studio reporting workflow

Initial:

```text
GSC / GA4 / crawl / other tools
  -> normalized report tables
  -> user-approved export/sync to Google Sheets
  -> Looker Studio native Sheets connector
  -> optional report embed/open inside SEO Analysis Software
```

Later:

```text
SEO Analysis Software read-only reporting API (HTTPS, scoped token)
  -> Apps Script Community Connector
  -> Looker Studio report template via Linking API
```

---

# 11. UI architecture and usability

## 11.1 Timing

Do not spend the first milestone building an elaborate dashboard. Build several real tools and a working local project model first. Then add a minimal UI so everyday operations no longer require memorizing CLI flags.

The UI must remain simple and utility-focused.

## 11.2 Recommended implementation

- FastAPI for local routes/API.
- Jinja2/server-rendered HTML pages.
- Plain CSS with a small token system.
- HTMX only where partial-page updates materially help.
- Vanilla JS for copy, tabs, filter toggles, small charts or progress polling.
- Native HTML forms, tables and links.
- Optional lightweight chart rendering only when a report needs it.

Do not create a single-page application just to display tool forms and result tables. Do not load all tool modules or result datasets into the browser at startup.

## 11.3 Core screens

1. **Quick analysis:** a prominent URL/domain/sitemap input and an immediate way to start a one-off audit without creating a project.
2. **Projects / saved targets:** list and reuse optional named projects and site profiles.
3. **Tools:** searchable tool catalogue, short descriptions and “Run” action.
4. **Run form:** generated from the tool schema, with target, scope, source and cost notes.
5. **Run status:** queued/running/partial/completed, progress and cancellation when safe.
6. **Results:** summary, findings, evidence, warnings, coverage and export links.
7. **Review queue:** similar page pairs, competitor opportunities, content updates and human decisions.
8. **Connections:** Google, WordPress, REA/import sources, search/SERP provider settings and permission overview.
9. **History:** previous runs, comparisons and changed findings.

## 11.4 UX rules

- A tool should be usable in one screen with sensible defaults.
- Show required fields only; advanced settings can be collapsed.
- Always show the exact user-supplied target or selected saved target being inspected. If no saved project is used, label the run as ad hoc rather than inventing a project.
- Before expensive external calls, show provider, estimated cost/units and request count where known.
- Show exactly which external sources will receive data.
- Put output tables first; avoid decorative dashboards that obscure findings.
- Use search, filters, sorting and pagination on large results.
- Provide JSON/CSV/XLSX/Markdown export where appropriate.
- Show source citations and coverage near each finding.
- No “SEO score” gamification or opaque red/yellow/green metrics without definitions.

## 11.5 Performance rules

The frontend remains fast by:

- Server-side pagination and filtering.
- Lazy-loading detail views.
- No large initial API payloads.
- No chart library on pages that do not need one.
- Virtual scrolling only if real table size warrants it.
- Avoiding unnecessary reactive framework and bundle size.

The number of registered tools is not a UI performance problem if tool metadata is small and result data is fetched on demand.

---

# 12. Agent, REA and MCP integration

## 12.1 Initial REA integration: structured CLI/JSON

Inspect what the actual REA skill supports. Start with the lowest-friction supported interface:

- CLI invocation with JSON arguments and JSON results, or
- a local HTTP endpoint with explicit authorization, or
- file-based request/result exchange for bulk research exports.

Do not assume REA provides a specific browser, file or MCP operation until verified.

The agent should be able to:

- List tools and their schemas.
- Describe a tool's purpose, data sources and permissions.
- Run a tool with validated inputs.
- Retrieve run status/results and artifact paths.
- Query evidence/findings.
- Submit explicit human review decisions.
- Compose preapproved workflows.

Do not let REA receive credentials or arbitrary filesystem access simply because it can call SEO Analysis Software.

## 12.2 MCP adapter — later, but design contracts for it now

Build MCP as a thin adapter over the same ToolRegistry/ToolRunner. Expose:

- `list_tools` / tool descriptions.
- `run_tool` with JSON Schema inputs.
- `get_run` / `get_result`.
- `list_findings` / `get_evidence`.
- `export_artifact` with safe project-scoped paths.
- `submit_review_decision` with explicit parameters.

Use project-scoped permissions. Read actions and write/review actions should be separate. High-cost or sensitive external actions should require explicit approval. Do not expose arbitrary shell execution, arbitrary SQL, unrestricted filesystem reads or general URL fetch as an MCP tool.

## 12.3 Evidence-constrained LLM analysis

An optional LLM may:

- Summarize findings.
- Cluster questions/topics.
- Suggest keyword groups.
- Draft a content brief.
- Explain why pages overlap.
- Rank opportunities by an explicit scoring formula.

It must not:

- Invent search volume, traffic, positions, backlink data or crawl results.
- Treat snippets as complete page evidence.
- State inferred intent as fact.
- infer missing API data as zero.
- Execute site changes or send private data without policy permission.

Every AI interpretation must reference the evidence IDs/source URLs used and be labelled as interpretation.

---

# 13. Testing and reliability

## 13.1 Test layers

- Unit tests: URL handling, parsing, normalization, similarity calculations, scoring and shared contracts.
- Offline integration tests: local HTTP fixtures, SQLite, artifact storage, CLI input validation, safe fake OAuth/API responses and cancellations.
- Connector contract tests: schemas, pagination, quotas, authentication failure, retries, incomplete data and missingness.
- End-to-end/golden fixtures: WordPress-like HTML/sitemaps; a plain static site; JavaScript-rendered content missing from initial HTML; Persian slugs/RTL; redirect and canonical variants; robots/no-sitemap behavior; parameterized link traps. Snapshot the expected inventory/findings/run manifest, not just intermediate parsing functions.
- Security tests: first-hop and redirected SSRF (including DNS rebinding and private addresses), filesystem path scope, credential redaction, untrusted web-text prompt injection, UI host/origin/CSRF boundaries when implemented.
- Performance tests: representative sites/data volumes when optimizing—not synthetic microbenchmarks alone.

## 13.2 External providers and live testing

Offline fixtures or mocks are the automated test baseline. Provide separate **opt-in** live smoke tests for owned sites and connected accounts. Make explicit the account/property, scopes, external destinations and request limits before live calls. Never require private API keys in CI, and never report mock tests as successful production authentication.

## 13.3 Crawl and run lifecycle tests

Test grace under limits: cancellation (`Ctrl+C`), maximum pages/depth/time, loops, parameter traps, truncated HTML, connection interruption, partial result reporting, atomic artifacts and recovery from interrupted runs. A partial report must never resemble a complete audit. Preserve useful existing tests while refactoring; update expectations only when the behavior change is intentional and documented. There is no requirement for historical CLI/CSV compatibility with an unreleased product.

---

# 14. Implementation sequence — stable foundation and working vertical slices

This is **one evolving application**, not a series of separate software products requiring migrations and architecture resets. Establish the shared framework and directory structure early. Develop actual capabilities inside it in coherent, verifiable increments. Stage labels below express dependencies and sequencing, not separate installable products or mandatory release versions. Tasks may cross related modules when doing so delivers a complete feature; don't impose arbitrary file counts or task limits.

## Stage A — Repository assessment, skeleton and installability

1. Inspect the real working checkout and reconcile each of the six existing CLI workflows and source modules with the concrete baseline in Section 6.1. Verify the archive/repository is available to the agent; inventory dependencies, outputs, test fixtures and current strengths/defects.
2. Verify available offline tests (starting archive previously reported 75 passed, 1 skipped; reproduce rather than assume).
3. Choose supported Python/runtime range, `pyproject.toml`, locked dependencies and documented Windows installation path.
4. Establish the target package tree, clear module boundaries, shared config/error/network-policy interfaces and concise architecture/ADR/implementation-state records.
5. Configure app-data storage (not repo-root runtime state) and meaningful Git checkpoint. Provide `seo-analysis --help` and a simple `system doctor` path diagnostic.
6. Do not write historical-migration code or compatibility wrappers unless there is a real external consumer.

**Working checkpoint:** Fresh Windows environment can install and invoke the CLI; existing useful tests still run; agents have one clear skeleton to extend.

## Stage B — First useful complete audit

1. Remove the old hardcoded website and defaults. Support explicit URL, sitemap, URL-list input and interactive prompting; fail clearly in noninteractive mode when missing.
2. Validate target mode and exact network scope. Implement secure HTTP fetch for every hop and approved local/staging exceptions.
3. Add sitemap discovery through robots.txt and known configured paths; when none exists, offer an explicitly bounded internal-link crawl.
4. Count discovery, retries and redirects toward the same request and time budgets. Enforce page/depth/response-size/rate/parameter limits. Persist completed observations during the crawl and atomically finalize its manifest with coverage, cancellation or failure status.
5. Integrate existing `crawl`, `analyze` and reporting functionality into the unified user-run audit, reusing the actual crawler, extractor, canonical/indexability and similarity modules where useful. Fix verified defects with targeted tests. Account explicitly for the already-working `variants`, `review`, `calibrate` and `gsc-pull` workflows even when their full unified interfaces are scheduled after the initial audit.
6. Produce readable terminal findings plus versioned JSON and CSV artifacts, coverage/source metadata and error/warning/review categorization. Every finding links to its evidence; no similarity score is a cannibalization verdict.
7. Validate all input types against offline golden fixtures (WordPress-like, static, Persian, no-sitemap, redirects, robots, parameter traps and security scenarios).

**Working checkpoint:** All first-use criteria in Section 17 pass without Google, subscriptions, an LLM connection, a UI or a saved project.

## Stage C — Shared tools, persistence and additional offline checks

1. Validate the smallest `ToolSpec`/ToolResult/ToolRunner contract using the already working audit and one other real operation; avoid speculative metadata. Bring the inherited analysis/review/calibration/variant tools under this contract instead of creating duplicate implementations.
2. Index the durable Stage B run artifacts in SQLite. Add optional saved targets/projects, schema migrations and historical queries. Recover interrupted indexing from the run manifest.
3. Add technical SEO, sitemap reconciliation, internal links, broken links, canonical diagnostics, schema extraction/validation, hreflang and simple asset checks as independently useful tools.
4. Add historical comparisons, review decisions and content-change awareness, preserving source completeness and snapshot identity.
5. Support structured CLI output and safe agent invocation over the **same** service interface. No separate agent-side implementation.

**Working checkpoint:** Tools can run independently or in a composed workflow, with optional project history and consistent evidence/permissions, without an external provider.

## Stage D — Minimal local UI when core workflows warrant it

1. Build a loopback-only FastAPI + server-rendered HTML interface; keep JavaScript optional and small.
2. Support a target URL form, selected tool options, run/progress/cancel, findings/evidence, report exports and optional saved projects.
3. Reuse the CLI's application services and contracts; add no separate UI-specific analysis pipeline.
4. Enforce host/origin/CSRF and data-egress boundaries; load only the active tool view and paginate large data.

**Working checkpoint:** The same audit works through CLI and UI, and the UI stays useful without Google connections.

## Stage E — Owned-site Google data and reporting

The local foundation and first usable audit require no connected service. Keep CSV imports and offline connector fixtures usable independently. Enable live services individually once a concrete workflow needs them.

1. Implement an OS-backed credential store, OAuth property selection and least-privilege scopes before live Google integrations.
2. GSC Search Analytics (query/page/date/device/country) with API limits, missingness and query attribution; use URL Inspection selectively under quota.
3. GA4 landing pages and conversions as distinct measurements; define and test ambiguous URL joins between crawled pages, GSC canonicals and GA4 paths.
4. Add PageSpeed Insights/local Lighthouse and CrUX source-appropriate lab/field metrics.
5. Export selected normalized data to CSV/XLSX/Google Sheets, with Sheets as the first practical Looker Studio input route.

**Working checkpoint:** An authorized owned-site connection can produce source-aware reports without leaking credentials, with unmatched rows and coverage clearly reported.

## Stage F — Search, SERP and community research

1. Add importers for user-owned account exports and public-source data with provenance and field mapping.
2. Define a small `ResearchSource` adapter and normalized result contract; benchmark an actual SERP/search provider before depending on it.
3. Add a controlled public/community source (Reddit, Stack Exchange, Discourse or supported RSS) according to real availability.
4. Add REA/browser request-and-result exchange **after inspecting its real supported capabilities**. Do not assume it can navigate, download or authenticate to a specific service.
5. Preserve source restrictions, date/locale/device and sampling limitations in every observation.

**Working checkpoint:** A selected permitted research source or import produces useful, inspectable observations for later keyword/competitor workflows.

## Stage G — Keyword, competitor and content intelligence

1. Keyword discovery from GSC, page language, SERP observations, forum questions and approved imports.
2. Keyword normalization/clustering, query-to-page mapping, SERP overlap, content briefs and refresh candidates.
3. Competitor discovery, selected page comparison, keyword/content gap and rank tracking from appropriately sourced observations.
4. Backlink and referring-domain analysis from user exports or selected providers; do not simulate a web-scale index or invent traffic volume.
5. Optional Ads Keyword Planner/Trends where actual access and constraints permit.

**Working checkpoint:** At least one keyword and competitor workflow produces source-backed opportunities, with provider-dependent estimates labelled.

## Stage H — CMS and website design quality

1. WordPress read-only REST connector with dedicated credentials (optional for public analysis).
2. Generic local source/build-output inspection for static, generated, headless or custom-coded websites, constrained to user-selected paths.
3. Lighthouse, axe-core accessibility, asset analysis, screenshots and opt-in visual regression with human-approved baselines.
4. Web-server log import and more advanced technical diagnostics when needed.

**Working checkpoint:** Shared contracts support WordPress and non-WordPress websites; user can still run generic web checks without CMS access.

## Stage I — Agent/MCP and Looker Studio expansion

1. Continue to provide structured CLI calls throughout development; build an MCP adapter as soon as its contract is stable and a real workflow benefits from it, rather than making it dependent on every other feature.
2. Restricted agent access to tool discovery, bounded runs, findings/evidence and decisions; no universal shell/file/secret exposure.
3. Looker Studio report links/templates and optional Community Connector or BigQuery export where useful. Apps Script in Google's cloud cannot call localhost; secure HTTPS/hosted selected data is necessary for a live connector.
4. Add optional scheduling and reusable workflows only when runs, storage and permissions behave reliably.

**Working checkpoint:** Agents and reporting tools can orchestrate or consume approved selected outputs without circumventing local permissions.

## Stage J — Performance work and distribution

1. Profile network wait, CPU, memory, SQLite and frontend work using representative real workflows.
2. Optimize Python, I/O, caching, parsing, graph/sparse-vector computations, SQL and UI pagination before language migration.
3. Prototype Rust for a measured CPU hotspot and compare end-to-end gains with integration/maintenance costs. Use a stable narrow Python/JSONL interface.
4. Package the local workbench as a single Windows executable. Reuse the same loopback web app, workspace and SQLite migrations. Verify the bundled workbench outside the checkout and offer a writable copy when workspace permissions block startup.

**Working checkpoint:** Any native component or packaging change has a measured or user-visible benefit.

---

# 15. Feature feasibility matrix

This matrix prevents the agent from attempting to reproduce datasets that require major independent infrastructure.

| Capability | Local implementation feasibility | External data need | Priority |
|---|---|---|---|
| Site crawl / technical audit | High | None for basic version | P0/P1 |
| Site structure / internal links | High | None | P1 |
| Schema audit | High | None for parsing; Google docs for eligibility rules | P1 |
| WordPress metadata/context | High | WordPress REST auth | P2 |
| Custom-coded/build output audit | High | Local repo/build access | P1/P2 |
| Accessibility and visual QA | High/medium | Browser engine | P2 |
| GSC query/page analysis | High | Google OAuth/property access | P1 |
| GA4 organic/conversion analysis | High | Google OAuth/property access | P1 |
| Keyword ideas from site/forum/SERP | Medium/high | Search and community sources | P2 |
| Search volume/CPC/keyword difficulty | Medium | Google Ads or vendor datasets | P2/P3 |
| SERP snapshots | High with provider | SERP data provider or permitted browser capture | P2 |
| Rank tracking | Medium | Repeated SERP observations | P2/P3 |
| Competitor discovery | Medium/high | SERPs and selected competitor pages | P2 |
| Competitor content gap | Medium | SERPs and competitor samples | P2 |
| Competitor domain-wide organic keywords | Low without dataset | Large vendor database or imported exports | P3 |
| Complete backlink profile | Low without dataset | Web-scale backlink index/provider export | P3/P4 |
| Traffic/clickstream estimates | Very low locally | Large panel/clickstream model | P4 |
| Forum question mining | High where API/feed/search results exist | Community APIs/search providers/REA | P2 |
| Looker Studio integration | High via Sheets; medium via connector | Google account/Apps Script; HTTPS for live connector | P2/P3 |
| AI visibility tracking | Medium for controlled prompt experiments | Model APIs/provider datasets | P4 |
| Full web-wide content discovery index | Very low locally | Search index/provider | P4 |

---

# 16. Operational priorities and boundaries

The first priority is an installed, user-run website audit inside the shared modular skeleton—not completing every tool in Section 6. Subsequent priorities are optional history and independent offline tools, a usable local UI, authorized first-party Google data, research source adapters, content/competitor analysis, CMS/source inspection, agent adapters and reporting integrations. Their exact order may change when real dependencies, feature usefulness or implementation experience justify it; preserve the underlying application contracts and document decisions in the authoritative specification.

Use a **single application and development history**, with Git commits and a living implementation-state file. Do not construct successive V1/V2/V3 replacement products or spend work migrating fictional prior versions. New modules must be usable through the shared application services instead of implementing separate logic in CLI, UI or MCP.

---

# 17. First independently usable milestone — acceptance criteria

The first usable milestone must do real work without requiring a saved project, Google account, paid API, LLM, MCP server, Looker Studio connection or graphical UI. The framework and module skeleton can exist already; tools beyond the audit are not release prerequisites.

1. A new user can install the app on Windows, run `seo-analysis --help`, and locate config/data/export directories using `seo-analysis system doctor` (or equivalent).
2. `seo-analysis audit https://example.org --max-pages 100 --max-depth 2` runs against an explicitly supplied permitted website URL, and `seo-analysis audit --sitemap https://example.org/sitemap.xml` supports a direct sitemap. URL-list input is also supported.
3. `seo-analysis audit` prompts for a target in interactive CMD/terminal use. In noninteractive mode without a target it reports a clear usage error, with no hidden default domain.
4. Website targets discover sitemap references from robots.txt and configured common locations. If none is available, the user can opt into a bounded link crawl with clear limits; the tool never explores unrestricted parameter spaces.
5. Request scope, robots policy, response-size limits, request/page/depth/time budget, permitted hosts and output path are inspectable. The HTTP layer applies public/private policy to first requests and redirects; local/staging access requires explicit approval.
6. The audit extracts HTTP/redirect details, titles, descriptions, headings, robots/canonical declarations, relevant technical observations, and content/overlap candidates where meaningful. Link checks and deeper schema capabilities can expand afterward.
7. The run produces a readable summary plus **versioned JSON and CSV artifacts**, with raw URL identity, source/provenance, timing, coverage and error/warning/review classification. Findings identify supporting evidence and uncertain or incomplete observations. Similarity is not labelled proof of search cannibalization.
8. `Ctrl+C`, request limits, an unreachable site, malformed sitemap, zero discoveries or a blocked scope yield meaningful status/diagnostics. Interrupted runs preserve available partial evidence and do not appear complete.
9. Offline end-to-end tests cover WordPress-like, static, Persian, no-sitemap, redirects, canonical/robots variants, unsafe URLs, DNS rebinding simulations and parameter traps; no live external account is required for the automated suite.
10. The application has one shared place for tool contracts, configuration, network permissions and report storage, and a documented initial implementation record; subsequent modules can extend the skeleton without replacing the architecture.

For any audit, a user can tell **what was checked, what was not, which source was consulted, what was sent outside the machine, which results were incomplete, and what requires human review.**

---

# 18. Reference documentation and research checked 2026-11-21

Re-check documentation, terms, access, quotas and pricing before implementing each connector.

## Google Search Console

- API reference: https://developers.google.com/webmaster-tools/v1/api_reference_index
- Search Analytics query: https://developers.google.com/webmaster-tools/v1/searchanalytics/query
- Usage limits: https://developers.google.com/webmaster-tools/limits
- URL Inspection API: https://developers.google.com/webmaster-tools/v1/urlInspection.index/inspect
- Bulk Data Export: https://support.google.com/webmasters/answer/12919198

## Google Analytics

- GA4 Data API: https://developers.google.com/analytics/devguides/reporting/data/v1
- API quickstart: https://developers.google.com/analytics/devguides/reporting/data/v1/quickstart
- API quotas: https://developers.google.com/analytics/devguides/reporting/data/v1/quotas

## Google Ads / Trends

- Keyword Planner API: https://developers.google.com/google-ads/api/docs/keyword-planning/overview
- Generate keyword ideas: https://developers.google.com/google-ads/api/docs/keyword-planning/generate-keyword-ideas
- Google Ads API access levels: https://developers.google.com/google-ads/api/docs/api-policy/access-levels
- Google Trends API alpha: https://developers.google.com/search/apis/trends

## Looker Studio

- Data Studio/Looker Studio API: https://developers.google.com/data-studio/integrate/api
- API reference: https://developers.google.com/data-studio/integrate/api/reference
- Community Connectors: https://developers.google.com/data-studio/connector
- Community Connector reference: https://developers.google.com/data-studio/connector/reference
- Linking API: https://developers.google.com/data-studio/integrate/linking-api
- Embed report: https://docs.cloud.google.com/data-studio/embed-a-report

## Google Search / SERP

- Custom Search JSON API current status: https://developers.google.com/custom-search/v1/overview
- Bing Search API retirement notice: https://learn.microsoft.com/en-us/lifecycle/announcements/bing-search-api-retirement
- DataForSEO SERP overview: https://docs.dataforseo.com/v3/serp-google-overview/
- DataForSEO Google SERP pricing: https://dataforseo.com/pricing/google-serp
- SerpApi Google Search API: https://serpapi.com/search-api

## Community sources

- Reddit developer API: https://developers.reddit.com/docs/capabilities/server/reddit-api
- Stack Exchange API: https://api.stackexchange.com/docs
- Stack Exchange throttles: https://api.stackexchange.com/docs/throttle
- Discourse API: https://docs.discourse.org/

## Performance / quality

- PageSpeed Insights API: https://developers.google.com/speed/docs/insights/v5/get-started
- CrUX API: https://developer.chrome.com/docs/crux/api
- CrUX History API: https://developer.chrome.com/docs/crux/history-api
- axe-core: https://github.com/dequelabs/axe-core
- Playwright: https://playwright.dev/docs/intro

## WordPress / OAuth

- WordPress REST API: https://developer.wordpress.org/rest-api/
- REST API authentication: https://developer.wordpress.org/rest-api/using-the-rest-api/authentication/
- Application Passwords: https://developer.wordpress.org/advanced-administration/security/application-passwords/
- Google OAuth installed apps: https://developers.google.com/identity/protocols/oauth2/native-app
- Google OAuth best practices: https://developers.google.com/identity/protocols/oauth2/resources/best-practices

## Python / Rust performance

- Python asyncio and threading: https://docs.python.org/3/library/asyncio-threading.html
- Rust/Python interoperability (PyO3): https://pyo3.rs/
- maturin: https://www.maturin.rs/

## Product capability reference (not implementation dependency)

- Ahrefs feature overview: https://ahrefs.com/all/
- Ahrefs FAQ/tools: https://ahrefs.com/faq/
- Semrush feature overview: https://www.semrush.com/features/
- Semrush SEO toolkit: https://www.semrush.com/seo/26721035/

---

# 19. Final directive to the implementing agent

Build **one local-first personal SEO and website-analysis workbench**. Use the supplied Python audit repository as unreleased starting code. Establish the coherent module boundaries, data semantics, safe network access, storage, reporting and agent-facing interfaces, then implement complete tools inside that structure. The initial website audit must run with a user-specified target and no external account.

Keep Python as the initial core and a lightweight HTML interface when appropriate. Rust is an option for measured hotspots, not an obligation. No previous project or employer is baked into the software's domain, defaults, paths or CLI.

Maintain the rich tool roadmap in Section 6: Google APIs, Looker Studio reporting (Sheets first), SERP/keyword and community research, competitor and backlink workflows, WordPress and custom-code inspections, website quality, REA/MCP. Source constraints and unavailable proprietary datasets must remain explicit; do not fabricate vendor-scale metrics or assume an unsupported API can supply them.

Keep network scope and data sharing explicit, secrets isolated, public and owned-site permissions separate, agent input untrusted, findings evidence-based and coverage visible. Build a durable application framework, not a set of throwaway stand-alone scripts or competing specification versions. Update the living architecture and implementation-state record as design decisions are validated.

---

# 20. Implementation kickoff prompt

The following prompt is designed to accompany **this consolidated specification and the actual source archive/repository** (`samatoos-seo-audit.zip` or its extracted checkout). The architecture document alone does not contain the source code. It is a reusable first message for any implementing agent; its assessment phase is intentionally read-only.

> We are beginning development of the **first actual release** of **SEO Analysis Software**. Read `SEO_ANALYSIS_SOFTWARE_ARCHITECTURE.md` completely and inspect the repository as it exists now.
>
> This document describes the complete intended architecture and future capabilities. The existing `seo_audit/` package in `samatoos-seo-audit.zip` is a **functional, tested starting codebase**, not an older deployed application: it already has `crawl`, `variants`, `analyze`, `review`, `calibrate`, `gsc-pull` and an offline test suite. There are no previous production users, installed application versions, customer migrations or legacy output contracts to preserve. Study these actual modules and their tests as starting material, not architectural constraints. Reuse useful behavior, but freely refactor, reorganize, or replace existing implementations when appropriate for the intended application. Do not preserve code solely because it already exists. If the archive is not present in the workspace, report that blocker instead of treating the application as an empty repository.
>
> **For your first response, do not modify any files.** Report the actual repository structure, relevant modules, dependencies, commands and tests, **map the six existing workflows into the proposed tool architecture**, identify concrete discrepancies with the architecture, and distinguish verified defects from potential enhancements. Examine the proposed modular skeleton and shared boundaries critically, then propose a coherent application structure and implementation sequence that establishes the foundation and delivers the complete first usable audit described in Section 17.
>
> Include the CLI behavior, target-selection and discovery flow, safe network/crawl controls, persistent data/artifact placement, common result format, and acceptance tests that matter for the first working experience. Describe any decisions that the repository evidence cannot resolve. You may recommend amendments to this specification if the implementation facts justify them; do not create a competing architecture document.
>
> Once the plan is approved, implement the agreed foundation and working capabilities through coordinated changes where needed. Use meaningful Git checkpoints and execute the appropriate tests. Keep `docs/IMPLEMENTATION_STATE.md` current with what is implemented, what was verified, any limitations and the next step. The application should remain extendable for the roadmap tools without requiring a new architectural rewrite for each feature.
>
> End the initial assessment by presenting the recommended first implementation task and the acceptance criteria it must meet. Wait for approval before editing.

---
