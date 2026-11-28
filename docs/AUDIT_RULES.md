# Audit rules and snapshot checks

Two mechanisms produce findings. **Crawl findings** are written during the audit itself (`src/seo_analysis/app/audit.py`). **Snapshot checks** run afterwards against a saved `snapshot.jsonl` and make no requests to the site (`src/seo_analysis/analysis/checks.py`).

A finding's evidence IDs point into `observations/page-NNNNNN.json`. One finding with two evidence IDs is still **one finding affecting two pages** — counts of occurrences and affected URLs are reported separately.

## Crawl findings (`seo.audit`)

| Rule | Category | Fires when | Coverage limit |
| --- | --- | --- | --- |
| `crawl.<fetch_state>` | `error` for `fetch_error`, `client_error`, `server_error`; otherwise `warning` | A URL did not fetch as HTML: transport failure, 4xx/5xx, robots block, non-HTML, redirect loop or blocked redirect | The status describes one attempt in this run |
| `content.extraction` | `coverage` | Usable text came from a fallback container, was empty, or the response was truncated | Not a site defect; it limits what comparison can see |
| `seo.redirect` | `warning` | The first response was a redirect | The destination is reported, not judged |
| `seo.multiple-h1` | `review` | More than one H1 on the page | Presence, not correctness |
| `seo.noindex` | `warning` | The effective indexability is `noindex` | Reports the directive; exclusion may be intentional |
| `seo.missing-title` | `review` | No `<title>` | — |
| `seo.missing-meta` | `review` | No meta description | — |
| `seo.missing-h1` | `review` | No H1 | — |
| `seo.canonical` | `warning` | The declared canonical raised an issue (missing, conflicting, points elsewhere) | Target status needs the target in the same crawl |
| `content.overlap` | `review` | Two pages passed the similarity thresholds | Requires at least two eligible pages; similarity is not proof of cannibalisation |

## Snapshot checks (`seo.check`)

These read a saved crawl only. Available: `technical`, `sitemap`, `links`, `broken-links`, `canonicals`, `schema`, `hreflang`, `assets`.

| Check | Observations | What it answers |
| --- | --- | --- |
| `technical` | the page's `fetch_state`; `missing-title`, `missing-meta`, `missing-h1` | Did the page fetch, and does it carry core metadata? |
| `sitemap` | `discovery_method`; `linked target absent from observed sitemap inventory` | How the URL was found, and whether declared sitemaps agree |
| `links` | the target's `fetch_state`, or `unobserved` | Where internal links point and whether the target was seen |
| `broken-links` | `observed-http-error` | Only links whose target returned an HTTP error |
| `canonicals` | `missing`, `self`, `self (written differently)`, `variant of itself`, `conflicting canonicals`, `points to another page` | Canonical consistency |
| `schema` | `types observed`, `no typed entity`, `invalid JSON-LD` | Structured data syntax and observed types, not rich-result eligibility |
| `hreflang` | `invalid language tag shape`, `return link observed`, `return link not observed`, `return link unverified` | Alternate-language declaration consistency |
| `assets` | `img`, `script`, `link` with `alt_state`; `mixed content reference` | Asset references and missing alt text |

## The three link cases

They are deliberately distinct, and the UI and exports keep them apart:

1. **Recorded HTTP error** — the target was crawled and answered 4xx/5xx → `broken-links`.
2. **Unobserved destination** — the target exists in markup but was never crawled → `links` observation `unobserved`. Never reported as broken.
3. **Missing markup** — an older snapshot has no link inventory → the check reports partial coverage (`markup unavailable`) rather than a clean result.

## Partial coverage

A snapshot from an older tool version, or one whose response was truncated, can lack `markup` or `extraction`. Affected checks then report partial coverage instead of zero findings, and findings are counted once even when two views show the same observation.