"""Content and competitor evidence from selected, normalized local datasets."""

from collections import defaultdict
from itertools import combinations
from dataclasses import dataclass
import json
from pathlib import Path
from urllib.parse import urlsplit

from seo_analysis.analysis.analyze import load_snapshot
from seo_analysis.analysis.fa_text import tokenize
from seo_analysis.core.artifacts import write_json
from seo_analysis.core.urls import url_key
from seo_analysis.reporting.dataset_export import indexed_artifact
from seo_analysis.reporting.report import write_csv
from seo_analysis.research.content_plan import (
    cluster_queries, editorial_briefs, refresh_candidates, sampled_page_comparisons,
)


@dataclass
class ResearchInput:
    datasets: tuple
    owned_host: str
    owned_crawl: str | None = None
    competitor_crawl: str | None = None


def _observed_pages(workspace, run_id, owned_host, *, owned):
    manifest, path = indexed_artifact(workspace, run_id, "snapshot.jsonl")
    if manifest["status"] not in ("succeeded", "partial"):
        raise ValueError("Use finished crawl runs for page comparisons.")
    pages = load_snapshot(path)
    if not pages:
        raise ValueError("The selected crawl has no page observations.")
    host = urlsplit(url_key(pages[0]["url"])).hostname
    if (host == owned_host) != owned:
        raise ValueError("Select one crawl for the owned hostname and one for a different competitor hostname.")
    indexed = {}
    for page in pages:
        if page["fetch_state"] not in ("ok", "ok_after_redirect") or not page.get("evidence_id"):
            continue
        final_url = page.get("final_url") or page["url"]
        if urlsplit(url_key(final_url)).hostname != host:
            continue
        entry = {"url": page["url"], "final_url": final_url, "title": page["title"], "h1": page["h1"],
                 "words": page["words"], "crawl_evidence": {"run_id": run_id, "id": page["evidence_id"]}}
        indexed[url_key(page["url"])] = entry
        if final_url == page["url"]:
            continue
        indexed.setdefault(url_key(final_url), entry)
    return indexed, {"run_id": run_id, "host": host, "status": manifest["status"]}


def build_research(ctx, request):
    host = request.owned_host.strip().casefold().rstrip(".")
    if not host or any(c in host for c in "/@: "):
        raise ValueError("Supply an exact owned hostname.")
    host = urlsplit(url_key("https://" + host)).hostname
    if bool(request.owned_crawl) != bool(request.competitor_crawl):
        raise ValueError("Supply both --owned-crawl and --competitor-crawl for page comparisons.")
    comparisons, crawl_sources = [], []
    terms = defaultdict(list)
    domains = defaultdict(set)
    questions, backlinks = [], []
    sources = {}
    serp = defaultdict(lambda: defaultdict(set))
    ranks = defaultdict(lambda: defaultdict(list))
    for path in request.datasets:
        directory = Path(path)
        data = json.loads((directory / "dataset.json").read_text(encoding="utf-8"))
        source = data["source"]
        sources[directory.name] = source | {"sample_rows": len(data["rows"])}
        for row in data["rows"]:
            ref = {"run_id": directory.name, "row": row["row"]}
            query = " ".join(tokenize(row.get("query", "")))
            url = row.get("url", "")
            domain = urlsplit(url_key(url)).hostname if urlsplit(url).hostname else ""
            if source["kind"] == "community":
                questions.append(dict(title=row["title"], url=url, evidence=ref))
            elif source["kind"] == "backlinks":
                backlinks.append(dict(source=row["source_url"], target=url, evidence=ref))
            elif query:
                terms[query].append(
                    dict(
                        evidence=ref,
                        domain=domain,
                        url=url,
                        kind=source["kind"],
                        rank=row.get("rank"),
                        volume=row.get("volume"),
                        impressions=row.get("impressions"),
                        clicks=row.get("clicks"),
                    )
                )
                if source["kind"] == "serp" and url and domain:
                    context = (source["provider"], source["observed"], source["locale"], source["device"])
                    domains[domain].add(query)
                    serp[context][query].add(url_key(url))
                    rank = row.get("rank")
                    if rank is not None and rank >= 1:
                        series = (source["provider"], source["locale"], source["device"], query, domain)
                        ranks[series][source["observed"]].append((rank, url, ref))
    keywords = []
    for query, records in sorted(terms.items()):
        observed = sorted({item["domain"] for item in records if item["domain"]})
        state = (
            "owned page observed"
            if host in observed
            else "only other domains observed"
            if observed
            else "no page attribution"
        )
        keywords.append(dict(query=query, state=state, domains=observed, observations=records))
    # Use an inverted index. Compare only queries sharing at least one result in the same capture context.
    overlaps = []
    omitted_common = 0
    for context, queries in serp.items():
        inverted = defaultdict(set)
        for query, urls in queries.items():
            for url in urls:
                inverted[url].add(query)
        candidates = set()
        for group in inverted.values():
            if len(group) > 100:
                omitted_common += 1
                continue
            candidates.update(combinations(sorted(group), 2))
            if len(candidates) > 100000:
                raise ValueError("Narrow the selected SERP exports to compare fewer query pairs.")
        for a, b in sorted(candidates):
            shared = queries[a] & queries[b]
            overlaps.append(
                dict(
                    queries=[a, b],
                    context=context,
                    shared_urls=sorted(shared),
                    jaccard=len(shared) / len(queries[a] | queries[b]),
                )
            )
    competitors = [
        {
            "host": d,
            "observed_queries": len(q),
            "shared_with_owned": len(q & domains.get(host, set())),
            "only_in_competitor_sample": sorted(q - domains.get(host, set())),
        }
        for d, q in sorted(domains.items())
        if d != host
    ]
    rank_history = []
    for (provider, locale, device, query, domain), captures in sorted(ranks.items()):
        previous = None
        samples = []
        for observed, items in sorted(captures.items()):
            best = min(rank for rank, _, _ in items)
            samples.append(
                dict(
                    date=observed,
                    best_observed_rank=best,
                    positions_gained=previous - best if previous is not None else None,
                    evidence=[ref for rank, _, ref in items if rank == best],
                )
            )
            previous = best
        rank_history.append(
            dict(provider=provider, locale=locale, device=device, query=query, host=domain, samples=samples)
        )

    briefs = []
    for keyword in keywords:
        if keyword["state"] != "only other domains observed":
            continue
        reference_pages = [r for r in keyword["observations"] if r["kind"] == "serp"]
        if reference_pages:
            briefs.append(
                dict(
                    query=keyword["query"],
                    action="Review sampled results for an owned-page opportunity",
                    reference_pages=reference_pages,
                )
            )
    clusters = cluster_queries(overlaps)
    content_briefs = editorial_briefs(briefs, clusters, sources)
    refresh = refresh_candidates(keywords, host, sources)
    if request.owned_crawl:
        owned_pages, own_source = _observed_pages(ctx.workspace, request.owned_crawl, host, owned=True)
        competitor_pages, competitor_source = _observed_pages(ctx.workspace, request.competitor_crawl, host, owned=False)
        crawl_sources = [own_source, competitor_source]
        comparisons = sampled_page_comparisons(keywords, sources, owned_pages, competitor_pages)
    write_json(ctx.directory / "content-plan.json", {
        "schema_version": 1,
        "sources": sources,
        "keyword_clusters": clusters,
        "content_briefs": content_briefs,
        "refresh_candidates": refresh,
        "crawl_sources": crawl_sources,
        "page_comparisons": comparisons,
        "method": {
            "clusters": "Queries are linked within one sample when they share at least two URLs and half of the combined result set.",
            "briefs": "Editorial prompts for queries with only competitor pages in the selected observations.",
            "refresh": "Declines between the two latest equal-length, non-overlapping Search Console periods. Each query and page must have one row per period.",
        },
    })
    referring_domains = defaultdict(list)
    for row in backlinks:
        domain = urlsplit(url_key(row["source"])).hostname
        if domain:
            referring_domains[domain].append(row["evidence"])
    write_json(
        ctx.directory / "research.json",
        dict(
            schema_version=1,
            owned_host=host,
            sources=sources,
            keywords=keywords,
            competitors=competitors,
            serp_overlap=overlaps,
            questions=questions,
            backlinks=backlinks,
            referring_domains=referring_domains,
            rank_history=rank_history,
            brief_candidates=briefs,
        ),
    )
    write_csv(
        ctx.directory / "keyword-map.csv",
        ["Query", "Observation", "Observed hosts", "Evidence rows"],
        ([r["query"], r["state"], ", ".join(r["domains"]), len(r["observations"])] for r in keywords),
    )
    warnings = ["Results describe the selected export samples."]
    if crawl_sources and not comparisons:
        warnings.append("No shared query tied both selected crawls to pages in the same SERP sample.")
    incomplete_crawl = any(source["status"] != "succeeded" for source in crawl_sources)
    if incomplete_crawl:
        warnings.append("At least one selected crawl has partial coverage.")
    if omitted_common:
        warnings.append(f"Omitted {omitted_common} common result URLs from pair generation.")
    partial = omitted_common or incomplete_crawl or any(s["skipped"] or s["capped"] or s.get("partial") for s in sources.values())
    return dict(
        status="partial" if partial else "succeeded",
        warnings=warnings,
        counts=dict(
            keywords=len(keywords),
            competitors=len(competitors),
            overlaps=len(overlaps),
            questions=len(questions),
            backlinks=len(backlinks),
            rank_series=len(rank_history),
            briefs=len(briefs),
            clusters=len(clusters),
            page_comparisons=len(comparisons),
            refresh_candidates=len(refresh),
        ),
    )
