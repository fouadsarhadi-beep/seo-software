"""Time the complete prepare-and-compare path on a reproducible synthetic corpus."""

from random import Random
from statistics import median
from time import perf_counter

from seo_analysis.analysis.similarity import Settings, compare, prepare


def sample(size=600):
    random = Random(25)
    items = []
    for index in range(size):
        topic = index % 30
        words = [f"topic{topic}term{random.randrange(100)}" for _ in range(90)]
        items.append(
            dict(
                url=f"https://example.org/{index}",
                title=f"topic{topic} guide{index}",
                h1=f"guide{index}",
                text=" ".join(words),
            )
        )
    for index in range(1, size, 23):
        items[index]["text"] = items[index - 1]["text"]
    return items


if __name__ == "__main__":
    items = sample()
    runs = []
    for _ in range(3):
        start = perf_counter()
        matches = compare(prepare(items, Settings()))
        runs.append(perf_counter() - start)
    print(f"{len(items)} pages, {len(matches)} pairs, median {median(runs):.3f} seconds")
