"""Similarity signals between pages. Signals are kept separate and explained; none of them is a verdict.

  near-duplicate   Jaccard of shared 5-word phrases (same wording)
  containment      share of the SHORTER page's phrases that also appear in the other page
                   (catches a short post copied into a long one, which Jaccard understates)
  topic overlap    TF-IDF cosine of words (+ word pairs): same subject even if worded differently
  title / H1       title word overlap (brand words ignored), identical H1
"""
from __future__ import annotations

from bisect import bisect_right
import math
from random import Random
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from seo_analysis.analysis.fa_text import tokenize


@dataclass
class Settings:
    shingle: int = 5
    min_words: int = 80
    boilerplate_df: float = 0.30
    max_df: float = 0.50
    bigrams: bool = True
    thr_dup: float = 0.35
    thr_contain: float = 0.80
    thr_topic: float = 0.60
    thr_title: float = 0.60
    brand_terms: tuple = ()


@dataclass
class Doc:
    url: str
    title: str
    h1: str
    page_type: str
    words: int
    tokens: list
    shingles: set
    vec: dict
    title_tokens: set
    h1_key: str


@dataclass
class PairResult:
    url_a: str
    url_b: str
    title_sim: float
    dup: float
    containment: float
    topic: float
    same_h1: bool
    shared_terms: list = field(default_factory=list)
    shared_phrases: list = field(default_factory=list)
    triggers: list = field(default_factory=list)
    evidence: int = 0
    page_type_a: str = "unknown"
    page_type_b: str = "unknown"
    words_a: int = 0
    words_b: int = 0
    short_page: bool = False


class Corpus:
    def __init__(self, docs, shingle_df, settings):
        self.docs, self.shingle_df, self.settings = docs, shingle_df, settings


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    return inter / (len(a) + len(b) - inter) if inter else 0.0


def prepare(items, settings: Settings, stopwords=frozenset(), variants=None, stem_fn=None) -> Corpus:
    """items: dicts with url, title, h1, text, page_type."""
    n = len(items)
    toks_all = [tokenize(it["text"], variants) for it in items]
    k = settings.shingle
    raw_sh = [{" ".join(t[i:i + k]) for i in range(len(t) - k + 1)} if len(t) >= k else set() for t in toks_all]
    sdf = Counter(s for sh in raw_sh for s in sh)
    limit = max(5, settings.boilerplate_df * n)
    shingles = [{s for s in sh if sdf[s] <= limit} for sh in raw_sh]

    terms_all = []
    for t in toks_all:
        topic = [(stem_fn(w) if stem_fn else w) if w not in stopwords and len(w) > 1 and not w.isdigit() else None for w in t]
        terms = [word for word in topic if word]
        if settings.bigrams:
            terms += [a + " " + b for a, b in zip(topic, topic[1:]) if a and b]
        terms_all.append(Counter(terms))
    tdf = Counter(w for c in terms_all for w in c)
    cut = max(3, settings.max_df * n)
    vecs = []
    for c in terms_all:
        v = {w: (1 + math.log(f)) * (math.log((1 + n) / (1 + tdf[w])) + 1) for w, f in c.items() if tdf[w] <= cut}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        vecs.append({w: x / norm for w, x in v.items()})

    brand = set(tokenize(" ".join(settings.brand_terms)))
    title_tok = [set(tokenize(it["title"])) for it in items]
    ttdf = Counter(w for s in title_tok for w in s)
    auto_brand = {w for w, c in ttdf.items() if n >= 6 and c >= 0.5 * n}
    title_tok = [{w for w in s if w not in stopwords and w not in brand and w not in auto_brand} for s in title_tok]

    docs = []
    for it, toks, sh, vec, tt in zip(items, toks_all, shingles, vecs, title_tok):
        docs.append(Doc(url=it["url"], title=it["title"], h1=it["h1"], page_type=it.get("page_type", "unknown"),
                        words=len(toks), tokens=toks, shingles=sh, vec=vec, title_tokens=tt,
                        h1_key=" ".join(tokenize(it["h1"])) if it["h1"] else ""))
    return Corpus(docs, sdf, settings)


def _explain(corpus: Corpus, a: Doc, b: Doc):
    small, big = (a.vec, b.vec) if len(a.vec) <= len(b.vec) else (b.vec, a.vec)
    scored = sorted(((w * big[t], t) for t, w in small.items() if t in big), reverse=True)[:8]
    terms = [t for _, t in scored]
    inter = a.shingles & b.shingles
    phrases = sorted(inter, key=lambda s: (corpus.shingle_df.get(s, 0), -len(s), s))[:3]
    return terms, [p if len(p) <= 70 else p[:67] + "..." for p in phrases]


def candidate_rows(corpus):
    """With positive thresholds a result must share a feature in at least one signal."""
    docs, settings = corpus.docs, corpus.settings
    if len(docs) < 32 or min(settings.thr_dup, settings.thr_contain, settings.thr_topic, settings.thr_title) <= 0:
        for i in range(len(docs)):
            yield range(i + 1, len(docs))
        return

    def features(doc):
        return (doc.shingles, doc.vec.keys(), doc.title_tokens, (doc.h1_key,) if doc.h1_key else ())

    postings = [defaultdict(list) for _ in range(4)]
    for index, doc in enumerate(docs):
        for table, keys in zip(postings, features(doc)):
            for key in keys:
                table[key].append(index)
    for index, doc in enumerate(docs):
        candidates = set()
        for table, keys in zip(postings, features(doc)):
            for key in keys:
                candidates.update(table[key])
        yield sorted(other for other in candidates if other > index)


def score_pair(corpus: Corpus, a: Doc, b: Doc, *, include_unflagged=False) -> PairResult | None:
    s = corpus.settings
    inter = len(a.shingles & b.shingles)
    smallest = min(len(a.shingles), len(b.shingles))
    dup = inter / (len(a.shingles) + len(b.shingles) - inter) if inter else 0.0
    contain = inter / smallest if inter and smallest else 0.0
    va, vb = (a.vec, b.vec) if len(a.vec) <= len(b.vec) else (b.vec, a.vec)
    topic = sum(w * vb.get(t, 0.0) for t, w in va.items())
    tsim = _jaccard(a.title_tokens, b.title_tokens)
    same_h1 = bool(a.h1_key) and a.h1_key == b.h1_key
    trig = []
    if dup >= s.thr_dup:
        trig.append("near-duplicate")
    if contain >= s.thr_contain:
        trig.append("containment")
    if topic >= s.thr_topic:
        trig.append("topic overlap")
    if tsim >= s.thr_title:
        trig.append("title")
    if same_h1:
        trig.append("same H1")
    if not trig and not include_unflagged:
        return None
    fam = (1 if ("near-duplicate" in trig or "containment" in trig) else 0) \
        + (1 if "topic overlap" in trig else 0) + (1 if ("title" in trig or "same H1" in trig) else 0)
    terms, phrases = _explain(corpus, a, b)
    return PairResult(a.url, b.url, round(tsim, 3), round(dup, 3), round(contain, 3), round(topic, 3),
                          same_h1, terms, phrases, trig, fam, a.page_type, b.page_type,
                          a.words, b.words, min(a.words, b.words) < s.min_words)


def compare(corpus: Corpus, progress=None) -> list[PairResult]:
    docs = corpus.docs
    out = []
    n = len(docs)
    for i, candidates in enumerate(candidate_rows(corpus)):
        if progress and i % 50 == 0:
            progress(i, n)
        for j in candidates:
            result = score_pair(corpus, docs[i], docs[j])
            if result is not None:
                out.append(result)
    out.sort(key=lambda p: (-p.evidence, -p.dup, -p.containment, -p.topic))
    return out



def calibration_sample(corpus: Corpus, flagged: list[PairResult], per_stratum: int, seed: int):
    """Sample uniformly within each stratum, including pairs discarded by the candidate index."""
    docs = corpus.docs
    n = len(docs)
    starts = [i * (2 * n - i - 1) // 2 for i in range(n)]
    total = n * (n - 1) // 2
    positions = {doc.url: i for i, doc in enumerate(docs)}
    excluded = sorted(starts[positions[pair.url_a]] + positions[pair.url_b] - positions[pair.url_a] - 1
                      for pair in flagged)
    population = {"flagged": len(flagged), "unflagged": total - len(flagged)}
    rng = Random(seed)
    sample = [("flagged", p) for p in rng.sample(flagged, min(per_stratum, len(flagged)))]

    # The k-th unflagged pair is k plus the flagged pairs preceding it.
    offset = 0
    for k in sorted(rng.sample(range(population["unflagged"]), min(per_stratum, population["unflagged"]))):
        while offset < len(excluded) and excluded[offset] <= k + offset:
            offset += 1
        rank = k + offset
        i = bisect_right(starts, rank) - 1
        j = i + 1 + rank - starts[i]
        result = score_pair(corpus, docs[i], docs[j], include_unflagged=True)
        if result is not None:
            sample.append(("unflagged", result))
    rng.shuffle(sample)
    return population, sample
