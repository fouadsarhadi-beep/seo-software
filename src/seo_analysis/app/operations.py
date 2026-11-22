"""Typed inputs and implementations for the local tool registry."""
from dataclasses import dataclass, field, replace
import json
from pathlib import Path

from filelock import FileLock

from seo_analysis.analysis.checks import CompareInput, SnapshotInput, check_snapshot, compare_snapshots
from seo_analysis.analysis import analyze, fa_text, review, similarity, variants
from seo_analysis.research.sources import BraveSearchInput, FeedInput, brave_search, read_feed
from seo_analysis.research.imports import ExportInput, import_export
from seo_analysis.research.intelligence import ResearchInput, build_research
from seo_analysis.reporting.workbook import WorkbookInput, build_workbook
from seo_analysis.analysis.local_lighthouse import LocalLighthouseInput, local_lighthouse
from seo_analysis.analysis.browserqa import BrowserQAInput, browser_qa
from seo_analysis.analysis.siteqa import SiteQAInput, inspect_build

from seo_analysis.connectors.wordpress import InventoryInput, inventory
from seo_analysis.app.audit import run_audit
from seo_analysis.connectors.performance import CruxInput, LighthouseInput, PageSpeedInput, crux, lighthouse, pagespeed
from seo_analysis.connectors.sheets import SheetsPublishInput, publish_sheets
from seo_analysis.reporting.dataset_export import DatasetExportInput, prepare_dataset
from seo_analysis.connectors.ga4 import LandingPagesInput, landing_pages
from seo_analysis.connectors.search_console import InspectionInput, SearchAnalyticsInput, inspect_url, search_analytics
from seo_analysis.core import tools
from seo_analysis.core.artifacts import write_json, write_text
from seo_analysis.reporting.report import write_csv
from seo_analysis.web.crawl import CrawlConfig, run_crawl


@dataclass
class AnalysisInput:
    in_dir: str
    settings: similarity.Settings = field(default_factory=similarity.Settings)
    gsc_pages: str | None = None
    gsc_queries: str | None = None
    stopwords: str | None = None
    variants: str | None = None
    normalizer: str = "basic"
    stem: bool = False
    include_noindex: bool = False


@dataclass
class VariantInput:
    in_dir: str
    variants: str | None = None
    min_count: int = 2


@dataclass
class ReviewInput:
    in_dir: str
    decisions: str | None = None
    min_evidence: int = 1
    limit: int = 0


@dataclass
class CalibrationInput:
    in_dir: str
    decisions: str | None = None


def crawl(ctx, cfg):
    return run_crawl(replace(cfg, out_dir=str(ctx.directory)), input_fn=ctx.prompt, log=ctx.log, cancel=ctx.cancel)


def audit(ctx, cfg):
    return run_audit(replace(cfg, out_dir=str(ctx.directory)), prompt=ctx.prompt, log=ctx.log, cancel=ctx.cancel)


def analyze_snapshot(ctx, request):
    result = analyze.run_analyze(
        request.in_dir, ctx.directory, request.gsc_pages, request.gsc_queries, request.settings,
        request.stopwords, request.variants, request.normalizer, request.stem, request.include_noindex, log=ctx.log,
    )
    manifest = Path(request.in_dir) / "crawl_manifest.json"
    if manifest.is_file():
        source = json.loads(manifest.read_text(encoding="utf-8"))
        result["counts"]["source_coverage"] = source["counts"]
        source_status = source["config"].get("status", "unknown")
        result["counts"]["source_status"] = source_status
        if source_status != "succeeded":
            result["status"] = "partial"
            result["warnings"].append(f"Source crawl status: {source_status}")
    else:
        result["status"] = "partial"
        result["warnings"].append("Source coverage unavailable.")
    return result


def spelling_variants(ctx, request):
    records = analyze.load_snapshot(Path(request.in_dir) / "snapshot.jsonl")
    tokens = [fa_text.tokenize(r["text"]) for r in records if r["fetch_state"].startswith("ok")]
    candidates = variants.find_candidates(tokens, min_split=request.min_count)
    path = Path(request.variants or Path(request.in_dir) / "persian_variants.json")
    with FileLock(str(path) + ".lock", timeout=0):
        if candidates:
            variants.review(candidates, path, ctx.ask, ctx.log)
        approved = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        write_json(ctx.directory / "persian_variants.json", approved)
    return {"counts": {"candidates": len(candidates), "approved": len(approved)}}


def review_pairs(ctx, request):
    source = Path(request.in_dir)
    pairs = json.loads((source / "pairs.json").read_text(encoding="utf-8"))
    path = Path(request.decisions or source / "decisions.jsonl")
    with FileLock(str(path) + ".lock", timeout=0):
        new = review.review_loop(pairs, path, request.min_evidence, request.limit, ctx.ask, ctx.log)
        decisions = review.load_decisions(path)
        if path.exists():
            write_text(ctx.directory / "decisions.jsonl", path.read_text(encoding="utf-8"))
    write_csv(ctx.directory / "decisions.csv", ["URL A", "URL B", "Decision", "Note", "Decided at (UTC)"],
              ([x["url_a"], x["url_b"], x["decision"], x["note"], x["ts"]] for x in decisions.values()))
    return {"counts": {"new_decisions": new, "decisions": len(decisions)}}


def calibrate(ctx, request):
    source = Path(request.in_dir)
    path = Path(request.decisions or source / "decisions.jsonl")
    pairs = json.loads((source / "pairs.json").read_text(encoding="utf-8"))
    with FileLock(str(path) + ".lock", timeout=0):
        text = review.calibrate(pairs, path, ctx.log)
    write_text(ctx.directory / "calibration.txt", text)
    return {"counts": {"candidate_pairs": len(pairs)}}


OPERATIONS = {
    tools.LOCAL_LIGHTHOUSE: (LocalLighthouseInput, local_lighthouse),
    tools.BROWSER_QA: (BrowserQAInput, browser_qa),
    tools.WORDPRESS: (InventoryInput, inventory),
    tools.PUBLIC_FEED: (FeedInput, read_feed),
    tools.BRAVE_SEARCH: (BraveSearchInput, brave_search),
    tools.DATASET_EXPORT: (DatasetExportInput, prepare_dataset),
    tools.SHEETS_PUBLISH: (SheetsPublishInput, publish_sheets),
    tools.PAGESPEED: (PageSpeedInput, pagespeed),
    tools.CRUX: (CruxInput, crux),
    tools.LIGHTHOUSE: (LighthouseInput, lighthouse),
    tools.GA4_LANDING_PAGES: (LandingPagesInput, landing_pages),
    tools.SEARCH_ANALYTICS: (SearchAnalyticsInput, search_analytics),
    tools.URL_INSPECTION: (InspectionInput, inspect_url),
    tools.IMPORT: (ExportInput, import_export),
    tools.RESEARCH: (ResearchInput, build_research),
    tools.WORKBOOK: (WorkbookInput, build_workbook),
    tools.SITE_QA: (SiteQAInput, inspect_build),
    tools.CHECK: (SnapshotInput, check_snapshot),
    tools.COMPARE: (CompareInput, compare_snapshots),
    tools.AUDIT: (CrawlConfig, audit),
    tools.CRAWL: (CrawlConfig, crawl),
    tools.ANALYZE: (AnalysisInput, analyze_snapshot),
    tools.VARIANTS: (VariantInput, spelling_variants),
    tools.REVIEW: (ReviewInput, review_pairs),
    tools.CALIBRATE: (CalibrationInput, calibrate),
}
