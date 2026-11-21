"""Command-line interface for the local SEO workbench."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import sys
from pathlib import Path

from seo_analysis import __version__
from seo_analysis.analysis import analyze, fa_text, review, similarity, variants as variants_mod
from seo_analysis.web import crawl
from seo_analysis.app.system import doctor
from seo_analysis.core import tools
from seo_analysis.core.network import HttpOrigin
from seo_analysis.core.workspace import Workspace
from seo_analysis.reporting.report import write_csv


def ask(question, default="", input_fn=input):
    suffix = f" [{default}]" if default else ""
    ans = input_fn(f"{question}{suffix}: ").strip()
    return ans or default


def _interactive(args) -> bool:
    return sys.stdin.isatty() and not getattr(args, "yes", False)


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
    cfg = crawl.CrawlConfig(sitemap=sitemap_url, out_dir=args.out_dir or str(args.workspace.create_run_directory()), delay=args.delay, retries=args.retries,
                            limit=args.limit, allow_local=args.allow_local, max_redirects=args.max_redirects,
                            robots=robots, content_selector=selector or "", exclude_selectors=args.exclude_selector or [],
                            skip_sitemap=args.skip_sitemap, config_file=args.config or "",
                            variants_file=args.variants or "", page_types=page_types,
                            user_agent=args.user_agent or crawl.CrawlConfig.__dataclass_fields__["user_agent"].default,
                            csv_guard=not args.no_csv_guard)
    crawl.run_crawl(cfg, input_fn=input_fn if inter else None)
    print(f"\nNext: seo-analysis variants --in-dir \"{cfg.out_dir}\"   (optional, Persian spelling variants)\n"
          f"      seo-analysis analyze --in-dir \"{cfg.out_dir}\"")
    return 0


def cmd_variants(args, input_fn=input):
    recs = analyze.load_snapshot(Path(args.in_dir) / "snapshot.jsonl")
    toks = [fa_text.tokenize(r["text"]) for r in recs if r["fetch_state"].startswith("ok")]
    cands = variants_mod.find_candidates(toks, min_split=args.min_count)
    if not cands:
        print("No spelling-variant candidates found.")
        return 0
    path = Path(args.variants or Path(args.in_dir) / "persian_variants.json")
    print(f"{len(cands)} candidate(s). You approve each one; nothing is applied without your answer.")
    ok = variants_mod.review(cands, path, input_fn)
    print(f"{len(ok)} variant(s) saved in {path}. 'analyze' will use them automatically.")
    return 0


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
    analyze.run_analyze(args.in_dir, args.out_dir, pages, qp, s, args.stopwords, args.variants, args.normalizer,
                        args.stem, args.include_noindex)
    out = args.out_dir or args.in_dir
    print(f"\nNext: seo-analysis review --in-dir \"{out}\"    (you decide, pair by pair)")
    return 0


def cmd_review(args, input_fn=input):
    d = Path(args.in_dir)
    pairs = json.loads((d / "pairs.json").read_text(encoding="utf-8"))
    dec_path = Path(args.decisions or d / "decisions.jsonl")
    review.review_loop(pairs, dec_path, args.min_evidence, args.limit, input_fn)
    decisions = review.load_decisions(dec_path)
    if decisions:
        write_csv(
            d / "decisions.csv",
            ["URL A", "URL B", "Decision", "Note", "Decided at (UTC)"],
            ([x["url_a"], x["url_b"], x["decision"], x["note"], x["ts"]] for x in decisions.values()),
        )
        print(f"Your decisions are also in {d / 'decisions.csv'}.")
    return 0


def cmd_calibrate(args, input_fn=input):
    d = Path(args.in_dir)
    pairs = json.loads((d / "pairs.json").read_text(encoding="utf-8"))
    text = review.calibrate(pairs, Path(args.decisions or d / "decisions.jsonl"))
    (d / "calibration.txt").write_text(text, encoding="utf-8")
    return 0


def cmd_doctor(args):
    facts = doctor(args.workspace)
    if args.json:
        print(json.dumps(facts, ensure_ascii=False))
    else:
        print(f"SEO Analysis {facts['app_version']} on Python {facts['python']}")
        for key in ("interpreter", "config_file", "data_dir", "runs_dir", "export_dir"):
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
    from seo_analysis.app.audit import run_audit
    from seo_analysis.web.discovery import read_seeds

    interactive = _interactive(args) and not args.json
    selected = [item for item in (args.url, args.sitemap, args.urls_file) if item]
    if not selected and interactive:
        args.url = ask("Website URL", input_fn=input_fn)
    if sum(bool(item) for item in (args.url, args.sitemap, args.urls_file)) != 1:
        raise ValueError("Select one website URL, --sitemap URL, or --urls-file PATH.")
    seeds = read_seeds(args.urls_file) if args.urls_file else []
    first = seeds[0] if seeds else args.url or args.sitemap
    HttpOrigin.from_url(first)
    directory = args.workspace.create_run_directory()
    cfg = crawl.CrawlConfig(
        first, str(directory), kind="urls_file" if seeds else "website" if args.url else "sitemap",
        source=args.urls_file or first, seeds=tuple(seeds), allow_local=args.allow_local,
        link_crawl=args.link_crawl, limit=args.max_pages, max_depth=args.max_depth,
        max_variants=args.max_variants, max_bytes=args.max_bytes, max_seconds=args.max_seconds,
        max_requests=args.max_requests, delay=args.delay, retries=args.retries,
        sitemap_paths=tuple(args.sitemap_path or ("/sitemap.xml", "/sitemap_index.xml")),
    )
    result = run_audit(cfg, log=lambda msg: print(msg, file=sys.stderr), prompt=input_fn if interactive else None)
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(f"{result['status']}: {result['counts']['observed']} observations in {directory}")
        for warning in result["warnings"]:
            print(warning)
    return {"succeeded": 0, "partial": 3, "cancelled": 130}.get(result["status"], 2)


def build_parser():
    p = argparse.ArgumentParser(prog="seo-analysis", description="Analytics-only SEO audit tools. You make the decisions.")
    p.add_argument("--version", action="version", version=__version__)
    p.add_argument("--config-file", type=Path, help="application workspace settings (TOML)")
    sub = p.add_subparsers(dest="cmd", required=True)

    system = sub.add_parser("system", help="inspect the local installation")
    commands = system.add_subparsers(dest="operation", required=True)
    diagnostic = commands.add_parser("doctor", help=tools.DOCTOR.summary)
    diagnostic.add_argument("--json", action="store_true")
    diagnostic.set_defaults(func=cmd_doctor)

    catalogue = sub.add_parser("tools", help="discover installed tools")
    operations = catalogue.add_subparsers(dest="operation", required=True)
    listing = operations.add_parser("list", help="list tool IDs and commands")
    listing.add_argument("--json", action="store_true")
    listing.set_defaults(func=cmd_list_tools)

    audit = sub.add_parser("audit", help="crawl a selected site and report evidence-backed findings")
    audit.add_argument("url", nargs="?")
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
    except (ValueError, RuntimeError, OSError) as exc:
        if getattr(args, "json", False):
            print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False))
        else:
            print(str(exc), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nStopped.")
        return 130
