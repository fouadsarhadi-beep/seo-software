"""Turn selected research observations into reviewable editorial candidates."""
from collections import defaultdict
from datetime import date

from seo_analysis.core.urls import url_key


def cluster_queries(overlaps):
    """Group queries connected by substantial SERP overlap within one sample context."""
    indexes = defaultdict(lambda: defaultdict(set))
    edges = defaultdict(list)
    for overlap in overlaps:
        if len(overlap["shared_urls"]) < 2 or overlap["jaccard"] < 0.5:
            continue
        context = overlap["context"]
        first, second = overlap["queries"]
        indexes[context][first].add(second)
        indexes[context][second].add(first)
        edges[context].append(overlap)

    clusters = []
    for context, graph in sorted(indexes.items()):
        group_by_query = {}
        for query in sorted(graph):
            if query in group_by_query:
                continue
            cluster = {"context": context, "queries": [], "overlaps": []}
            pending = [query]
            group_by_query[query] = cluster
            while pending:
                current = pending.pop()
                cluster["queries"].append(current)
                for neighbor in graph[current]:
                    if neighbor not in group_by_query:
                        group_by_query[neighbor] = cluster
                        pending.append(neighbor)
            cluster["queries"].sort()
            clusters.append(cluster)
        for overlap in edges[context]:
            group_by_query[overlap["queries"][0]]["overlaps"].append(overlap)
    return clusters


def editorial_briefs(candidates, clusters, sources):
    related = defaultdict(list)
    for cluster in clusters:
        for query in cluster["queries"]:
            related[query].append(cluster)
    briefs = []
    for candidate in candidates:
        query = candidate["query"]
        references = candidate["reference_pages"]
        contexts = set()
        for reference in references:
            source = sources[reference["evidence"]["run_id"]]
            contexts.add((source["provider"], source["observed"], source["locale"], source["device"]))
        briefs.append({
            "query": query,
            "reference_pages": references,
            "related_queries": [
                {"context": cluster["context"], "queries": [q for q in cluster["queries"] if q != query]}
                for cluster in related[query] if cluster["context"] in contexts
            ],
            "review": [
                "Review the sampled pages to identify the task searchers appear to be trying to complete.",
                "Check the owned site for an existing page before proposing a new one.",
                "Outline a way to answer the primary query using original examples or evidence.",
            ],
        })
    return briefs


def _gsc_period(source):
    # Daily or segmented rows need a deliberate roll-up before they can be compared.
    if source["kind"] != "gsc" or source.get("data_state") not in (None, "final"):
        return None
    if source.get("partial") or source.get("capped") or source.get("skipped"):
        return None
    if set(source.get("dimensions") or ("query", "page")) != {"query", "page"}:
        return None
    try:
        start = date.fromisoformat(source["period_start"])
        end = date.fromisoformat(source["observed"])
    except (ValueError, KeyError, TypeError):
        return None
    return (start, end) if start <= end else None


def _period_label(period):
    return [boundary.isoformat() for boundary in period]


def refresh_candidates(keywords, host, sources):
    candidates = []
    for keyword in keywords:
        histories = defaultdict(lambda: defaultdict(list))
        for observation in keyword["observations"]:
            if observation["domain"] != host:
                continue
            source = sources[observation["evidence"]["run_id"]]
            period = _gsc_period(source)
            if period is None:
                continue
            context = (source["provider"], source.get("property", ""), source.get("search_type", ""),
                       source.get("locale", ""), source.get("device", ""), source.get("retrieval", ""))
            histories[(url_key(observation["url"]), context)][period].append(observation)
        for (url, context), periods in histories.items():
            ordered = sorted(periods, key=lambda period: (period[1], period[0]), reverse=True)
            if len(ordered) < 2:
                continue
            latest, previous = ordered[:2]
            if (previous[1] >= latest[0] or latest[1] - latest[0] != previous[1] - previous[0]
                    or len(periods[latest]) != 1 or len(periods[previous]) != 1):
                continue
            older, newer = periods[previous][0], periods[latest][0]
            changes = {}
            for metric in ("clicks", "impressions"):
                before, after = older.get(metric), newer.get(metric)
                if before is not None and after is not None and after < before:
                    changes[metric] = {"before": before, "after": after, "change": after - before}
            if changes:
                candidates.append({
                    "query": keyword["query"], "url": url, "context": context,
                    "previous_period": _period_label(previous), "latest_period": _period_label(latest),
                    "declines": changes, "evidence": [older["evidence"], newer["evidence"]],
                })
    return sorted(candidates, key=lambda row: (
        row["declines"].get("clicks", {}).get("change", 0),
        row["declines"].get("impressions", {}).get("change", 0), row["url"], row["query"],
    ))


def sampled_page_comparisons(keywords, sources, owned_pages, competitor_pages):
    comparisons = []
    for keyword in keywords:
        groups = defaultdict(lambda: ([], []))
        for observation in keyword["observations"]:
            if observation["kind"] != "serp" or not observation["rank"] or observation["rank"] < 1:
                continue
            key = url_key(observation["url"])
            ref = observation["evidence"]
            source = sources[ref["run_id"]]
            context = (source["provider"], source["observed"], source["locale"], source["device"])
            for index, pages in enumerate((owned_pages, competitor_pages)):
                if key in pages:
                    groups[context][index].append((observation["rank"], key, ref, pages[key]))
        for context, (owned, competitor) in sorted(groups.items()):
            if not owned or not competitor:
                continue
            first = min(owned, key=lambda item: (item[0], item[1]))
            second = min(competitor, key=lambda item: (item[0], item[1]))
            comparisons.append({
                "query": keyword["query"], "context": context,
                "owned": {"rank": first[0], "serp_evidence": first[2], **first[3]},
                "competitor": {"rank": second[0], "serp_evidence": second[2], **second[3]},
            })
    return comparisons
