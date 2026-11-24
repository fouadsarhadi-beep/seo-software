"""Command-line interface for the local SEO workbench."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import sys
import sqlite3
from urllib.parse import urlsplit
from pathlib import Path

from seo_analysis import __version__
from seo_analysis.analysis import similarity
from seo_analysis.analysis.checks import CHECKS, CompareInput, SnapshotInput
from seo_analysis.app.operations import AnalysisInput, CalibrationInput, ReviewInput, VariantInput
from seo_analysis.app.runner import ToolRunner
from seo_analysis.core.artifacts import publish_files
from seo_analysis.web import crawl
from seo_analysis.app.system import doctor
from seo_analysis.core import tools
from seo_analysis.core.network import HttpOrigin
from seo_analysis.core.workspace import Workspace
from seo_analysis.storage.history import History



def ask(question, default="", input_fn=input):
    suffix = f" [{default}]" if default else ""
    ans = input_fn(f"{question}{suffix}: ").strip()
    return ans or default


def _interactive(args) -> bool:
    return sys.stdin.isatty() and not getattr(args, "yes", False) and not getattr(args, "json", False)


def execute(args, spec, request, prompt=None, export=None, export_names=None):
    workspace = args.workspace
    json_mode = getattr(args, "json", False)
    log = lambda message: print(message, file=sys.stderr)
    result = ToolRunner(workspace).run(spec, request, log=log, prompt=None if json_mode else prompt,
                                       project=getattr(args, "project", None),
                                       saved_target=getattr(args, "target", None))
    directory = Path(result.out_dir)
    if export and result.status in {"succeeded", "partial"}:
        names = result.artifacts if export_names is None else export_names
        destination = publish_files(directory, export, names, include_observations=spec.uses_network)
        log(f"Export directory: {destination}")
    if json_mode:
        summary = asdict(result)
        summary["warning_count"] = len(result.warnings)
        summary["warnings"] = result.warnings[:20]
        print(json.dumps(summary, ensure_ascii=False))
    else:
        print(f"{result.tool_id} {result.status} | {result.run_id}")
        print(f"Run directory: {directory}")
        print("Coverage:", json.dumps(result.counts, ensure_ascii=False))
        for warning in result.warnings[:20]:
            print(warning)
        if len(result.warnings) > 20:
            print("See run.json for all warnings.")
    return {"succeeded": 0, "partial": 3, "cancelled": 130}.get(result.status, 2)


def cmd_crawl(args, input_fn=input):
    inter = _interactive(args)
    sitemap_url = args.sitemap or (ask("Sitemap URL", input_fn=input_fn) if inter else "")
    if not sitemap_url:
        raise ValueError("Supply a target with crawl --sitemap <URL>.")
    HttpOrigin.from_url(sitemap_url)
    robots = args.robots
    if robots is None:
        robots = "respect"
        if inter and ask("Respect robots.txt? (recommended)", "Y", input_fn).lower().startswith("n"):
            robots = "ignore"
    page_types = []
    if inter and not args.config:
        pat = ask("Optional: a URL pattern (regex) that marks blog posts, e.g. /blog/  (Enter to skip)", "", input_fn)
        if pat:
            page_types = [{"name": "blog", "url_regex": pat}]
    selector = args.content_selector
    if inter and not selector:
        selector = ask("Optional: CSS selector of the article text (Enter = automatic)", "", input_fn)
    if inter and ask(f"Crawl {sitemap_url} now (one request at a time, {args.delay}s apart)?", "Y", input_fn).lower().startswith("n"):
        print("Cancelled.")
        return 1
    cfg = crawl.CrawlConfig(sitemap=sitemap_url, out_dir="", delay=args.delay, retries=args.retries,
                            limit=args.limit, allow_local=args.allow_local, max_redirects=args.max_redirects,
                            robots=robots, content_selector=selector or "", exclude_selectors=args.exclude_selector or [],
                            skip_sitemap=args.skip_sitemap, config_file=args.config or "",
                            variants_file=args.variants or "", page_types=page_types,
                            user_agent=args.user_agent or crawl.CrawlConfig.__dataclass_fields__["user_agent"].default,
                            csv_guard=not args.no_csv_guard)
    return execute(args, tools.CRAWL, cfg, input_fn if inter else None, args.out_dir)


def cmd_variants(args, input_fn=input):
    return execute(args, tools.VARIANTS, VariantInput(args.in_dir, args.variants, args.min_count), input_fn)


def cmd_analyze(args, input_fn=input):
    inter = _interactive(args)
    pages, qp = args.gsc_pages, args.gsc_queries
    if inter and not pages:
        pages = ask("Optional: path to a Search Console 'Pages' export CSV (Enter to skip)", "", input_fn) or None
    if inter and not qp:
        qp = ask("Optional: path to a query-by-page CSV export (Enter to skip)", "", input_fn) or None
    s = similarity.Settings(shingle=args.shingle, min_words=args.min_words, thr_dup=args.min_dup,
                            thr_contain=args.min_contain, thr_topic=args.min_topic, thr_title=args.min_title,
                            bigrams=not args.no_bigrams, brand_terms=tuple(args.brand or []))
    request = AnalysisInput(args.in_dir, s, pages, qp, args.stopwords, args.variants, args.normalizer,
                            args.stem, args.include_noindex)
    export = args.out_dir
    if export is None and not (Path(args.in_dir) / "run.json").exists():
        export = args.in_dir
    return execute(args, tools.ANALYZE, request, export=export)


def cmd_review(args, input_fn=input):
    request = ReviewInput(args.in_dir, args.decisions, args.min_evidence, args.limit)
    return execute(args, tools.REVIEW, request, input_fn, args.in_dir, ["decisions.csv"])


def cmd_calibrate(args, input_fn=input):
    return execute(args, tools.CALIBRATE, CalibrationInput(args.in_dir, args.decisions),
                   export=args.in_dir, export_names=["calibration.txt"])


def cmd_doctor(args):
    facts = doctor(args.workspace)
    if args.json:
        print(json.dumps(facts, ensure_ascii=False))
    else:
        print(f"SEO Analysis {facts['app_version']} on Python {facts['python']}")
        for key in ("interpreter", "config_file", "data_dir", "runs_dir", "history_db", "export_dir"):
            print(f"{key}: {facts[key]}")
        print("Configuration:", "loaded" if facts["config_loaded"] else "defaults")
        print("Dependencies:", ", ".join(f"{k} {v}" for k, v in facts["dependencies"].items()))
    return 0


def cmd_list_tools(args):
    if args.json:
        print(json.dumps([asdict(tool) for tool in tools.BUILTIN_TOOLS]))
    else:
        for tool in tools.BUILTIN_TOOLS:
            print(f"{tool.id:26} {tool.command:16} {tool.summary}")
    return 0


def cmd_audit(args, input_fn=input):
    from seo_analysis.web.discovery import read_seeds

    interactive = _interactive(args) and not args.json
    selected = [item for item in (args.url, args.sitemap, args.urls_file) if item]
    if args.target:
        if selected:
            raise ValueError("Choose a saved target or an explicit target.")
        saved = History(args.workspace).selection(args.project, args.target)
        if saved["kind"] == "website":
            args.url = saved["url"]
        else:
            args.sitemap = saved["url"]
    if not selected and not args.target and interactive:
        value = ask("Website URL, sitemap URL, or path to a URL list", input_fn=input_fn)
        if value.startswith(("https://", "http://")) and urlsplit(value).path.lower().endswith((".xml", ".xml.gz")):
            args.sitemap = value
        elif value and not value.startswith(("https://", "http://")) and Path(value).is_file():
            args.urls_file = value
        else:
            args.url = value
    if sum(bool(item) for item in (args.url, args.sitemap, args.urls_file)) != 1:
        raise ValueError("Select one website URL, --sitemap URL, or --urls-file PATH.")
    seeds = read_seeds(args.urls_file) if args.urls_file else []
    first = seeds[0] if seeds else args.url or args.sitemap
    raw_input = args.urls_file or first
    if args.url and "://" not in first:
        hostname = first.split("/", 1)[0]
        if "." not in hostname or any(c in hostname for c in ":@"):
            raise ValueError("Provide the complete HTTP(S) website URL.")
        first = "https://" + first
    HttpOrigin.from_url(first)
    cfg = crawl.CrawlConfig(
        first, "", kind="urls_file" if seeds else "website" if args.url else "sitemap",
        source=raw_input, seeds=tuple(seeds), allow_local=args.allow_local,
        link_crawl=args.link_crawl, limit=args.max_pages, max_depth=args.max_depth,
        max_variants=args.max_variants, max_bytes=args.max_bytes, max_seconds=args.max_seconds,
        max_requests=args.max_requests, delay=args.delay, retries=args.retries,
        sitemap_paths=tuple(args.sitemap_path or ("/sitemap.xml", "/sitemap_index.xml")),
    )
    return execute(args, tools.AUDIT, cfg, input_fn if interactive else None)


def cmd_history(args):
    history = History(args.workspace)
    if args.cmd == "project":
        if args.operation == "create":
            history.add_project(args.name)
        value = history.projects()
    elif args.cmd == "target":
        if args.operation == "add":
            history.add_target(args.project, args.name, args.kind, args.url)
        value = history.targets(args.project)
    elif args.operation == "show":
        value = history.show(args.run_id)
    elif args.operation == "reindex":
        value = history.reindex()
    else:
        value = history.list_runs(args.project)
    print(json.dumps(value, ensure_ascii=False, indent=None if args.json else 2))
    return 2 if isinstance(value, dict) and value.get("errors") else 0


def cmd_local_data(args):
    from seo_analysis.app.operations import ExportInput, ResearchInput, WorkbookInput, SiteQAInput
    if args.cmd == "import-data":
        req = ExportInput(args.file,args.kind,args.provider,args.observed,args.locale,args.device,args.period_start,json.loads(args.columns))
        return execute(args, tools.IMPORT, req)
    if args.cmd == "site-qa":
        return execute(args, tools.SITE_QA, SiteQAInput(args.directory,args.lighthouse,args.axe,args.access_log,args.baseline,args.screenshot))
    history = History(args.workspace)
    datasets = tuple(history.show(r)["directory"] for r in dict.fromkeys(args.dataset))
    if args.cmd == "research":
        return execute(args, tools.RESEARCH, ResearchInput(datasets, args.owned_host, args.owned_crawl, args.competitor_crawl))
    return execute(args, tools.WORKBOOK, WorkbookInput(history.show(args.crawl)["directory"],datasets,args.report_url))


def cmd_mcp(args):
    from seo_analysis.app.mcp_server import build_server
    build_server(args.workspace, args.allow_run).run(transport="stdio")
    return 0


def cmd_serve(args):
    import uvicorn
    from seo_analysis.ui.server import create_app
    if not 1 <= args.port <= 65535:
        raise ValueError("Select a port between 1 and 65535.")
    uvicorn.run(create_app(args.workspace, args.port), host="127.0.0.1", port=args.port)
    return 0


def cmd_agent(args):
    from seo_analysis.app.agent import run_snapshot_tool
    result = run_snapshot_tool(args.workspace, args.tool, args.run, previous=args.previous, check=args.check)
    print(json.dumps({"run_id": result.run_id, "status": result.status, "counts": result.counts,
                      "artifacts": result.artifacts, "warnings": result.warnings[:10]}, ensure_ascii=False))
    return {"succeeded": 0, "partial": 3}.get(result.status, 2)


def cmd_snapshot(args):
    history = History(args.workspace)
    if args.cmd == "check":
        source = history.show(args.run)["directory"]
        return execute(args, tools.CHECK, SnapshotInput(source, args.check, source_run_id=args.run))
    before, after = (history.show(r)["directory"] for r in (args.before, args.after))
    return execute(args, tools.COMPARE, CompareInput(before, after, args.before, args.after))


def cmd_google(args):
    from seo_analysis.connectors.google import GoogleConnection

    connection = GoogleConnection(args.workspace, args.project, args.service)
    if args.operation == "connect":
        def choose(properties):
            if not properties:
                raise ValueError("Google returned no accessible properties for this account.")
            if args.property_id is not None:
                return args.property_id
            if not sys.stdin.isatty():
                raise ValueError("Pass --property ID when connecting from a noninteractive terminal.")
            choices = sorted(properties)
            for index, property_id in enumerate(choices, 1):
                print(f"{index}. {properties[property_id]} ({property_id})")
            answer = input("Property number: ").strip()
            if not answer.isdecimal() or not 1 <= int(answer) <= len(choices):
                raise ValueError("Choose one of the listed property numbers.")
            return choices[int(answer) - 1]
        if args.service != "sheets" and args.property_id is None and not sys.stdin.isatty():
            raise ValueError("Pass --property ID when connecting from a noninteractive terminal.")
        if args.service == "sheets" and args.property_id is not None:
            raise ValueError("Sheets authorization does not accept a property ID.")
        selected = connection.connect(args.client_file, choose)
    elif args.operation == "disconnect":
        connection.disconnect(revoke=args.revoke)
        selected = None
    else:
        selected = connection.selected()
    print(json.dumps({"service": args.service, "project": args.project, "selected": selected}, ensure_ascii=False))
    return 0


def cmd_search_console(args):
    from seo_analysis.connectors.search_console import InspectionInput, SearchAnalyticsInput

    if args.operation == "inspect-url":
        return execute(args, tools.URL_INSPECTION, InspectionInput(args.url))
    request = SearchAnalyticsInput(args.start, args.end, tuple(args.dimensions),
                                   args.search_type, args.data_state, args.max_rows)
    return execute(args, tools.SEARCH_ANALYTICS, request)


def cmd_ga4(args):
    from seo_analysis.connectors.ga4 import LandingPagesInput

    request = LandingPagesInput(args.start, args.end, args.origin, args.stream_id, args.channel, args.max_rows)
    return execute(args, tools.GA4_LANDING_PAGES, request)


def cmd_performance_key(args):
    from getpass import getpass
    from seo_analysis.connectors.performance import performance_key, validate_key

    if args.action == "set":
        if not sys.stdin.isatty():
            raise ValueError("Use an interactive terminal to save a performance API key.")
        value = validate_key(getpass("Google performance API key: ").strip())
        performance_key(args.workspace, "set", value)
        print("Google performance API key saved to the OS credential store.")
    else:
        performance_key(args.workspace, "delete")
        print("Google performance API key removed locally.")
    return 0


def cmd_performance(args):
    from seo_analysis.connectors.performance import CruxInput, LighthouseInput, PageSpeedInput

    if args.cmd == "lighthouse-report":
        return execute(args, tools.LIGHTHOUSE, LighthouseInput(args.report))
    if args.operation == "pagespeed":
        return execute(args, tools.PAGESPEED, PageSpeedInput(args.url, args.strategy, args.use_key))
    return execute(args, tools.CRUX, CruxInput(args.url, args.scope, args.form_factor))


def cmd_dataset_export(args):
    from seo_analysis.reporting.dataset_export import DatasetExportInput

    return execute(args, tools.DATASET_EXPORT,
                   DatasetExportInput(args.dataset, tuple(args.column), args.title, args.max_rows))


def cmd_sheets_publish(args):
    from seo_analysis.connectors.sheets import SheetsPublishInput

    return execute(args, tools.SHEETS_PUBLISH, SheetsPublishInput(args.export, args.confirm))


def cmd_live_research(args):
    from seo_analysis.research.sources import BraveSearchInput, FeedInput, brave_key

    if args.cmd == "research-feed":
        return execute(args, tools.PUBLIC_FEED, FeedInput(args.url, args.max_items))
    if args.cmd == "research-search":
        return execute(args, tools.BRAVE_SEARCH,
                       BraveSearchInput(args.query, args.country, args.language, args.count, args.allow_storage))
    if args.action == "delete":
        brave_key(args.workspace, delete=True)
        print("Brave Search API key removed locally.")
    else:
        from getpass import getpass
        import re

        if not sys.stdin.isatty():
            raise ValueError("Use an interactive terminal to save the Brave Search key.")
        token = getpass("Brave Search API key: ").strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]{20,256}", token):
            raise ValueError("Enter a valid Brave Search API key.")
        brave_key(args.workspace, token)
        print("Brave Search API key saved to the OS credential store.")
    return 0


def cmd_wordpress(args):
    from seo_analysis.connectors.wordpress import InventoryInput, credentials, site_root

    if args.operation == "inventory":
        return execute(args, tools.WORDPRESS, InventoryInput(args.site, args.resource, args.max_items, args.authenticated))
    if args.operation == "forget":
        credentials(args.workspace, args.project, args.site, delete=True)
        print("WordPress Application Password removed locally.")
        return 0

    from getpass import getpass

    site_root(args.site)
    if not sys.stdin.isatty():
        raise ValueError("Use an interactive terminal to save a WordPress Application Password.")
    account = input("Dedicated WordPress username: ").strip()
    password = getpass("WordPress Application Password: ").strip()
    credentials(args.workspace, args.project, args.site, account=account, password=password)
    print("WordPress credentials saved to the OS credential store.")
    return 0


def cmd_browser_qa(args):
    from seo_analysis.analysis.browserqa import BrowserQAInput

    return execute(args, tools.BROWSER_QA, BrowserQAInput(args.directory, args.page, args.width, args.height,
                                                           args.axe_script, args.baseline, args.chromium))


def cmd_local_lighthouse(args):
    from seo_analysis.analysis.local_lighthouse import LocalLighthouseInput

    return execute(args, tools.LOCAL_LIGHTHOUSE,
                   LocalLighthouseInput(args.directory, args.lighthouse_cli, args.chromium, args.page, args.device))


def build_parser():
    p = argparse.ArgumentParser(prog="seo-analysis", description="Analytics-only SEO audit tools. You make the decisions.")
    p.add_argument("--version", action="version", version=__version__)
    p.add_argument("--config-file", type=Path, help="application workspace settings (TOML)")
    sub = p.add_subparsers(dest="cmd", required=True)

    google = sub.add_parser("google", help="manage Google connections and run Google integrations")
    google_actions = google.add_subparsers(dest="operation", required=True)
    connect = google_actions.add_parser("connect", help="authorize a Google service on this computer")
    connect.add_argument("--client-file", type=Path, required=True, help="OAuth client JSON for a Desktop app")
    connect.add_argument("--property", dest="property_id", help="select this property ID without a numbered prompt")
    status = google_actions.add_parser("status", help="show the local Google connection")
    disconnect = google_actions.add_parser("disconnect", help="remove local Google credentials and property selection")
    disconnect.add_argument("--revoke", action="store_true", help="also revoke the grant with Google")
    for command in (connect, status, disconnect):
        command.add_argument("service", choices=("gsc", "ga4", "sheets"))
        command.add_argument("--project", help="scope the connection to an existing project")
        command.set_defaults(func=cmd_google)


    from seo_analysis.connectors.search_console import DIMENSIONS, MAX_ROWS, SEARCH_TYPES

    search = google_actions.add_parser("search-analytics", help=tools.SEARCH_ANALYTICS.summary)
    search.add_argument("--start", required=True, help="First date, YYYY-MM-DD")
    search.add_argument("--end", required=True, help="Last date, YYYY-MM-DD")
    search.add_argument("--dimensions", choices=DIMENSIONS, nargs="+", default=("query", "page"))
    search.add_argument("--search-type", choices=SEARCH_TYPES, default="web")
    search.add_argument("--data-state", choices=("final", "all"), default="final")
    search.add_argument("--max-rows", type=int, default=MAX_ROWS)
    inspection = google_actions.add_parser("inspect-url", help=tools.URL_INSPECTION.summary)
    inspection.add_argument("url", help="URL in the selected Search Console property")
    for command in (search, inspection):
        command.add_argument("--project", help="use this project's Search Console connection")
        command.add_argument("--json", action="store_true")
        command.set_defaults(func=cmd_search_console)

    from seo_analysis.connectors.ga4 import MAX_ROWS as GA4_MAX_ROWS

    landing = google_actions.add_parser("landing-pages", help=tools.GA4_LANDING_PAGES.summary)
    landing.add_argument("--start", required=True, help="First date, YYYY-MM-DD")
    landing.add_argument("--end", required=True, help="Last date, YYYY-MM-DD")
    landing.add_argument("--origin", default="", help="web origin to assign to reported paths for crawl matching")
    landing.add_argument("--stream-id", default="", help="filter to a numeric GA4 web stream ID")
    landing.add_argument("--channel", default="", help="session default channel group, such as Organic Search")
    landing.add_argument("--max-rows", type=int, default=GA4_MAX_ROWS)
    landing.add_argument("--project", help="use this project's GA4 connection")
    landing.add_argument("--json", action="store_true")
    landing.set_defaults(func=cmd_ga4)

    from seo_analysis.connectors.performance import FORM_FACTORS

    performance_key = google_actions.add_parser("performance-key", help="manage the optional performance API key")
    performance_key.add_argument("action", choices=("set", "delete"))
    performance_key.set_defaults(func=cmd_performance_key)
    pagespeed = google_actions.add_parser("pagespeed", help=tools.PAGESPEED.summary)
    pagespeed.add_argument("url", help="public page URL sent to PageSpeed Insights")
    pagespeed.add_argument("--strategy", choices=("mobile", "desktop"), default="mobile")
    pagespeed.add_argument("--use-key", action="store_true", help="use the saved Google performance API key")
    crux = google_actions.add_parser("crux", help=tools.CRUX.summary)
    crux.add_argument("url", metavar="target", help="public URL or origin sent to CrUX")
    crux.add_argument("--scope", choices=("url", "origin"), default="url")
    crux.add_argument("--form-factor", choices=FORM_FACTORS, default="ALL_FORM_FACTORS")
    lighthouse = sub.add_parser("lighthouse-report", help=tools.LIGHTHOUSE.summary)
    lighthouse.add_argument("report", help="path to a locally generated Lighthouse JSON report")
    for command in (pagespeed, crux, lighthouse):
        command.add_argument("--project")
        command.add_argument("--json", action="store_true")
        command.set_defaults(func=cmd_performance)

    from seo_analysis.reporting.dataset_export import MAX_ROWS as EXPORT_MAX_ROWS

    export = sub.add_parser("export-dataset", help=tools.DATASET_EXPORT.summary)
    export.add_argument("--dataset", required=True, help="normalized dataset run ID")
    export.add_argument("--column", action="append", required=True, help="column to include, repeat in output order")
    export.add_argument("--title", required=True, help="title for the spreadsheet if published")
    export.add_argument("--max-rows", type=int, default=EXPORT_MAX_ROWS)
    export.set_defaults(func=cmd_dataset_export)
    sheets = google_actions.add_parser("publish-sheets", help=tools.SHEETS_PUBLISH.summary)
    sheets.add_argument("export", help="reviewed export run ID")
    sheets.add_argument("--confirm", required=True, help="SHA-256 shown in the export.json preview")
    sheets.set_defaults(func=cmd_sheets_publish)
    for command in (export, sheets):
        command.add_argument("--project")
        command.add_argument("--json", action="store_true")

    feed = sub.add_parser("research-feed", help=tools.PUBLIC_FEED.summary)
    feed.add_argument("url")
    feed.add_argument("--max-items", type=int, default=100)
    search_web = sub.add_parser("research-search", help=tools.BRAVE_SEARCH.summary)
    search_web.add_argument("query")
    search_web.add_argument("--country", default="us")
    search_web.add_argument("--language", default="en")
    search_web.add_argument("--count", type=int, default=10)
    search_web.add_argument("--allow-storage", action="store_true", help="confirm your Brave plan permits storage")
    for command in (feed, search_web):
        command.add_argument("--project")
        command.add_argument("--json", action="store_true")
        command.set_defaults(func=cmd_live_research)
    research_key = sub.add_parser("research-key", help="manage the Brave Search API key")
    research_key.add_argument("action", choices=("set", "delete"))
    research_key.set_defaults(func=cmd_live_research)

    wordpress = sub.add_parser("wordpress", help="inspect a WordPress installation")
    wp_actions = wordpress.add_subparsers(dest="operation", required=True)
    wp_inventory = wp_actions.add_parser("inventory", help=tools.WORDPRESS.summary)
    wp_inventory.add_argument("--resource", default="posts",
                              help="posts, pages, media, types, or a registered custom post type slug")
    wp_inventory.add_argument("--max-items", type=int, default=100)
    wp_inventory.add_argument("--authenticated", action="store_true", help="use the saved Application Password")
    wp_inventory.add_argument("--json", action="store_true")
    wp_connect = wp_actions.add_parser("connect", help="save credentials for this installation")
    wp_forget = wp_actions.add_parser("forget", help="remove local credentials for this installation")
    for command in (wp_inventory, wp_connect, wp_forget):
        command.add_argument("site", help="HTTPS installation base URL")
        command.add_argument("--project")
        command.set_defaults(func=cmd_wordpress)

    browser_qa = sub.add_parser("browser-qa", help=tools.BROWSER_QA.summary)
    browser_qa.add_argument("directory", help="trusted local build directory")
    browser_qa.add_argument("--page", default="/", help="local page path, such as /docs/")
    browser_qa.add_argument("--width", type=int, default=1365)
    browser_qa.add_argument("--height", type=int, default=768)
    browser_qa.add_argument("--axe-script", default="", help="trusted local axe-core JavaScript file")
    browser_qa.add_argument("--baseline", default="", help="approved PNG baseline with matching dimensions")
    browser_qa.add_argument("--chromium", default="", help="use an installed Chromium executable")
    browser_qa.add_argument("--project")
    browser_qa.add_argument("--json", action="store_true")
    browser_qa.set_defaults(func=cmd_browser_qa)

    local_lighthouse = sub.add_parser("lighthouse-run", help=tools.LOCAL_LIGHTHOUSE.summary)
    local_lighthouse.add_argument("directory", help="trusted local build directory")
    local_lighthouse.add_argument("--page", default="/")
    local_lighthouse.add_argument("--device", choices=("desktop", "mobile"), default="mobile")
    local_lighthouse.add_argument("--lighthouse-cli", required=True, help="installed Lighthouse cli/index.js")
    local_lighthouse.add_argument("--chromium", required=True, help="installed Chrome or Chromium executable")
    local_lighthouse.add_argument("--project")
    local_lighthouse.add_argument("--json", action="store_true")
    local_lighthouse.set_defaults(func=cmd_local_lighthouse)

    mcp = sub.add_parser("mcp", help="serve selected local run evidence over stdio")
    mcp.add_argument("--allow-run", required=True, action="append")
    mcp.set_defaults(func=cmd_mcp)
    serve = sub.add_parser("serve", help="open the loopback audit workbench")
    serve.add_argument("--port", type=int, default=8765)
    serve.set_defaults(func=cmd_serve)

    system = sub.add_parser("system", help="inspect the local installation")
    commands = system.add_subparsers(dest="operation", required=True)
    diagnostic = commands.add_parser("doctor", help=tools.DOCTOR.summary)
    diagnostic.add_argument("--json", action="store_true")
    diagnostic.set_defaults(func=cmd_doctor)

    catalogue = sub.add_parser("tools", help="discover installed tools")
    operations = catalogue.add_subparsers(dest="operation", required=True)
    invoke = operations.add_parser("run", help="execute a permitted offline operation on managed snapshots")
    invoke.add_argument("tool", choices=(tools.CHECK.id, tools.COMPARE.id, tools.ANALYZE.id))
    invoke.add_argument("--run", required=True)
    invoke.add_argument("--previous")
    invoke.add_argument("--check", choices=(*CHECKS, "all"), default="all")
    invoke.set_defaults(func=cmd_agent, json=True)
    listing = operations.add_parser("list", help="list tool IDs and commands")
    listing.add_argument("--json", action="store_true")
    listing.set_defaults(func=cmd_list_tools)

    check = sub.add_parser("check", help=tools.CHECK.summary)
    check.add_argument("--run", required=True)
    check.add_argument("--check", choices=(*CHECKS, "all"), default="all")
    compare = sub.add_parser("compare", help=tools.COMPARE.summary)
    compare.add_argument("--before", required=True)
    compare.add_argument("--after", required=True)
    for command in (check, compare):
        command.add_argument("--json", action="store_true")
        command.add_argument("--project")
        command.set_defaults(func=cmd_snapshot)

    from seo_analysis.research.imports import REQUIRED
    imp = sub.add_parser("import-data", help=tools.IMPORT.summary)
    imp.add_argument("file")
    imp.add_argument("--kind", choices=tuple(REQUIRED), required=True)
    imp.add_argument("--provider", required=True)
    imp.add_argument("--observed", required=True, help="Observation or period end date, YYYY-MM-DD")
    imp.add_argument("--period-start", default="")
    imp.add_argument("--locale", default="")
    imp.add_argument("--device", default="")
    imp.add_argument("--columns", default="{}", help="JSON object mapping normalized names to source headers")
    research = sub.add_parser("research", help=tools.RESEARCH.summary)
    research.add_argument("--dataset", action="append", required=True)
    research.add_argument("--owned-host", required=True)
    research.add_argument("--owned-crawl", help="owned site crawl run ID for comparing observed pages")
    research.add_argument("--competitor-crawl", help="competitor crawl run ID for comparing observed pages")
    workbook = sub.add_parser("workbook", help=tools.WORKBOOK.summary)
    workbook.add_argument("--crawl", required=True)
    workbook.add_argument("--dataset", action="append", default=[])
    workbook.add_argument("--report-url", default="")
    qa = sub.add_parser("site-qa", help=tools.SITE_QA.summary)
    qa.add_argument("directory")
    qa.add_argument("--lighthouse", default="")
    qa.add_argument("--axe", default="")
    qa.add_argument("--access-log", default="", help="Selected common or combined web access log")
    qa.add_argument("--baseline", default="", help="Operator-selected approved reference PNG")
    qa.add_argument("--screenshot", default="", help="Current PNG at the same viewport and scale")
    for command in (imp, research, workbook, qa):
        command.add_argument("--json", action="store_true")
        command.add_argument("--project")
        command.set_defaults(func=cmd_local_data)

    projects = sub.add_parser("project", help="manage optional saved projects").add_subparsers(dest="operation", required=True)
    create = projects.add_parser("create")
    create.add_argument("name")
    project_list = projects.add_parser("list")
    targets = sub.add_parser("target", help="manage saved website and sitemap inputs").add_subparsers(dest="operation", required=True)
    add = targets.add_parser("add")
    add.add_argument("name")
    add.add_argument("url")
    add.add_argument("--kind", choices=("website", "sitemap"), default="website")
    target_list = targets.add_parser("list")
    for command in (add, target_list):
        command.add_argument("--project", required=True)
    history = sub.add_parser("history", help="inspect and rebuild the local run index").add_subparsers(dest="operation", required=True)
    runs = history.add_parser("list")
    runs.add_argument("--project")
    show = history.add_parser("show")
    show.add_argument("run_id")
    rebuild = history.add_parser("reindex")
    for command in (create, project_list, add, target_list, runs, show, rebuild):
        command.add_argument("--json", action="store_true")
        command.set_defaults(func=cmd_history)

    audit = sub.add_parser(tools.AUDIT.command, help=tools.AUDIT.summary)
    audit.add_argument("url", nargs="?")
    audit.add_argument("--target", help="explicitly select a saved target within --project")
    audit.add_argument("--project")
    audit.add_argument("--sitemap")
    audit.add_argument("--urls-file")
    audit.add_argument("--sitemap-path", action="append", help="candidate sitemap location; repeatable")
    audit.add_argument("--link-crawl", action="store_true", help="follow internal links if discovery finds no sitemap")
    audit.add_argument("--allow-local", action="store_true", help="approve the selected origin for local/staging access")
    audit.add_argument("--max-pages", type=int, default=100)
    audit.add_argument("--max-depth", type=int, default=2)
    audit.add_argument("--max-requests", type=int, default=500)
    audit.add_argument("--max-seconds", type=float, default=300)
    audit.add_argument("--max-bytes", type=int, default=5_000_000)
    audit.add_argument("--max-variants", type=int, default=5)
    audit.add_argument("--retries", type=int, default=2)
    audit.add_argument("--delay", type=float, default=0.5)
    audit.add_argument("--json", action="store_true")
    audit.add_argument("--non-interactive", dest="yes", action="store_true")
    audit.set_defaults(func=cmd_audit)

    c = sub.add_parser(tools.CRAWL.command, help=tools.CRAWL.summary)
    c.add_argument("--sitemap"); c.add_argument("--out-dir", help="defaults to a new workspace run directory")
    c.add_argument("--delay", type=float, default=0.5); c.add_argument("--retries", type=int, default=2)
    c.add_argument("--limit", type=int, default=100, help="crawl only the first N URLs (test run)")
    c.add_argument("--allow-local", action="store_true", help="allow the selected local/staging origin")
    c.add_argument("--robots", choices=["respect", "ignore"], default=None)
    c.add_argument("--max-redirects", type=int, default=5)
    c.add_argument("--content-selector", default=""); c.add_argument("--exclude-selector", action="append")
    c.add_argument("--skip-sitemap", default=crawl.CrawlConfig.skip_sitemap)
    c.add_argument("--config"); c.add_argument("--variants"); c.add_argument("--user-agent")
    c.add_argument("--no-csv-guard", action="store_true"); c.add_argument("--yes", action="store_true", help="no questions")
    c.set_defaults(func=cmd_crawl)

    v = sub.add_parser(tools.VARIANTS.command, help=tools.VARIANTS.summary)
    v.add_argument("--in-dir", required=True); v.add_argument("--variants")
    v.add_argument("--min-count", type=int, default=2)
    v.set_defaults(func=cmd_variants)

    a = sub.add_parser(tools.ANALYZE.command, help=tools.ANALYZE.summary)
    a.add_argument("--in-dir", required=True); a.add_argument("--out-dir")
    a.add_argument("--gsc-pages"); a.add_argument("--gsc-queries")
    a.add_argument("--shingle", type=int, default=5); a.add_argument("--min-words", type=int, default=80)
    a.add_argument("--min-dup", type=float, default=0.35); a.add_argument("--min-contain", type=float, default=0.80)
    a.add_argument("--min-topic", type=float, default=0.60); a.add_argument("--min-title", type=float, default=0.60)
    a.add_argument("--no-bigrams", action="store_true"); a.add_argument("--brand", action="append")
    a.add_argument("--stopwords"); a.add_argument("--variants")
    a.add_argument("--normalizer", choices=["basic", "hazm"], default="basic")
    a.add_argument("--stem", action="store_true", help="Hazm stemming for the topic signal only (needs hazm)")
    a.add_argument("--include-noindex", action="store_true"); a.add_argument("--yes", action="store_true")
    a.set_defaults(func=cmd_analyze)

    r = sub.add_parser(tools.REVIEW.command, help=tools.REVIEW.summary)
    r.add_argument("--in-dir", required=True); r.add_argument("--decisions")
    r.add_argument("--min-evidence", type=int, default=1); r.add_argument("--limit", type=int, default=0)
    r.set_defaults(func=cmd_review)

    k = sub.add_parser(tools.CALIBRATE.command, help=tools.CALIBRATE.summary)
    k.add_argument("--in-dir", required=True); k.add_argument("--decisions")
    k.set_defaults(func=cmd_calibrate)

    for command in (c, a, k, r, v):
        command.add_argument("--json", action="store_true")
        command.add_argument("--project")
    return p


def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    args = build_parser().parse_args(argv)
    try:
        args.workspace = Workspace.load(args.config_file)
        return args.func(args)
    except (ValueError, RuntimeError, OSError, sqlite3.Error) as exc:
        if getattr(args, "json", False):
            print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False))
        else:
            print(str(exc), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nStopped.")
        return 130
