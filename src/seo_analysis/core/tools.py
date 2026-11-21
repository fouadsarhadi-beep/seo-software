"""Discovery metadata shared by the CLI and future local interfaces."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ToolSpec:
    id: str
    command: str
    summary: str
    uses_network: bool = False


DOCTOR = ToolSpec("system.doctor", "system doctor", "Inspect runtime, dependencies and workspace paths.")
AUDIT = ToolSpec("seo.audit", "audit", "Crawl one site and report evidence-backed findings.", uses_network=True)
CRAWL = ToolSpec("web.crawl", "crawl", "Read a sitemap and inventory its pages.", uses_network=True)
ANALYZE = ToolSpec("seo.analyze-snapshot", "analyze", "Evaluate canonicals and content overlap in a saved crawl.")
VARIANTS = ToolSpec("content.spelling-variants", "variants", "Review Persian spelling variants.")
REVIEW = ToolSpec("content.review-pairs", "review", "Record editorial decisions on flagged pairs.")
CALIBRATE = ToolSpec("content.calibrate", "calibrate", "Evaluate thresholds on reviewed pairs.")

CHECK = ToolSpec("seo.check", "check", "Inspect observed links, metadata, markup and assets in a crawl.")
COMPARE = ToolSpec("seo.compare", "compare", "Compare two snapshots for the same origin.")

BUILTIN_TOOLS = (CHECK, COMPARE, DOCTOR, CRAWL, AUDIT, ANALYZE, VARIANTS, REVIEW, CALIBRATE)
