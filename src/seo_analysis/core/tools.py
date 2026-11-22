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

IMPORT = ToolSpec("research.import", "import-data", "Import a selected research or analytics export.")
RESEARCH = ToolSpec("research.opportunities", "research", "Compare sourced queries, competitors, questions and backlinks.")
WORKBOOK = ToolSpec("report.workbook", "workbook", "Export crawl and first-party measurements to Excel.")
SITE_QA = ToolSpec("quality.build", "site-qa", "Inspect a selected static build and browser QA reports.")

SEARCH_ANALYTICS = ToolSpec("google.search-analytics", "google search-analytics",
                            "Fetch Search Analytics for the selected Search Console property.", uses_network=True)
URL_INSPECTION = ToolSpec("google.inspect-url", "google inspect-url",
                          "Read Google's indexed assessment of one URL.", uses_network=True)

BUILTIN_TOOLS = (SEARCH_ANALYTICS, URL_INSPECTION, IMPORT, RESEARCH, WORKBOOK, SITE_QA, CHECK, COMPARE, DOCTOR, CRAWL, AUDIT, ANALYZE, VARIANTS, REVIEW, CALIBRATE)
