"""Content and competitor evidence from selected, normalized local datasets."""

from collections import defaultdict
from itertools import combinations
from dataclasses import dataclass
import json
from pathlib import Path
from urllib.parse import urlsplit

from seo_analysis.analysis.fa_text import tokenize
from seo_analysis.core.artifacts import write_json
from seo_analysis.core.urls import url_key
from seo_analysis.reporting.report import write_csv


@dataclass
class ResearchInput:
    datasets: tuple
    owned_host: str


def build_research(ctx, request):
    host = request.owned_host.strip().casefold().rstrip(".")
    if not host or any(c in host for c in "/@: "):
        raise ValueError("Supply an exact owned hostname.")
    host = urlsplit(url_key("https://" + host)).hostname
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
        sources[directory.name] = source
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
    if omitted_common:
        warnings.append(f"Omitted {omitted_common} common result URLs from pair generation.")
    partial = omitted_common or any(s["skipped"] or s["capped"] or s.get("partial") for s in sources.values())
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
        ),
    )
