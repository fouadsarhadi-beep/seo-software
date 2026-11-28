"""CLI command group for provider connections, research sources and browser reports."""

import json
from pathlib import Path
import sys

from seo_analysis.cli_runtime import execute
from seo_analysis.core import tools


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


def add_integration_commands(sub):
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
