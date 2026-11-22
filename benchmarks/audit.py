"""Measure the audit path against a local HTML fixture corpus."""
from argparse import ArgumentParser
from collections import Counter
from contextlib import ExitStack
from functools import wraps
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from random import Random
from tempfile import TemporaryDirectory
import sys
from threading import Thread
from time import perf_counter, process_time
from unittest.mock import patch

from fastapi.testclient import TestClient

from seo_analysis.app import audit
from seo_analysis.app.runner import ToolRunner
from seo_analysis.core import tools
from seo_analysis.core.workspace import Workspace
from seo_analysis.storage.history import History
from seo_analysis.ui.server import create_app
from seo_analysis.web.crawl import CrawlConfig


def sample(count):
    random = Random(25)
    pages = []
    for index in range(count):
        topic = index % 30
        words = [f"topic{topic}term{random.randrange(100)}" for _ in range(240)]
        paragraphs = "".join(f"<p>{' '.join(words[i:i + 30])}</p>" for i in range(0, len(words), 30))
        pages.append(
            f'<html lang="fa"><title>راهنما {topic} شماره {index}</title><meta name="description" content="نمونه">'
            f'<header>Website</header><main><article><h1>راهنما {topic} شماره {index}</h1>{paragraphs}'
            f'<img src="/assets/{topic}.png" alt="نمونه"><a href="/documents/{(index + 1) % count}">بعدی</a>'
            "</article></main><footer>Contact</footer></html>"
        )
    return [body.encode("utf-8") for body in pages]


def run(pages):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/robots.txt":
                body = b"User-agent: *\nAllow: /"
            elif self.path == "/sitemap.xml":
                origin = f"http://127.0.0.1:{self.server.server_port}"
                body = ("<urlset>" + "".join(f"<url><loc>{origin}/documents/{i}</loc></url>"
                                            for i in range(len(pages))) + "</urlset>").encode()
            else:
                body = pages[int(self.path.rsplit("/", 1)[-1])]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    durations = Counter()

    def measure(name, function):
        @wraps(function)
        def wrapper(*args, **kwargs):
            before = perf_counter()
            try:
                return function(*args, **kwargs)
            finally:
                durations[name] += perf_counter() - before
        return wrapper

    with TemporaryDirectory() as scratch, ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server, ExitStack() as patches:
        Thread(target=server.serve_forever, daemon=True).start()
        patches.callback(server.shutdown)
        patches.enter_context(patch.object(audit, "run_crawl", measure("crawl", audit.run_crawl)))
        patches.enter_context(patch.object(audit, "run_analyze", measure("analysis", audit.run_analyze)))
        patches.enter_context(patch.object(audit, "report_findings", measure("findings", audit.report_findings)))
        patches.enter_context(patch.object(History, "index", measure("history_index", History.index)))
        base = Path(scratch)
        workspace = Workspace(base / "config.toml", base / "data", base / "exports")
        cfg = CrawlConfig(f"http://127.0.0.1:{server.server_port}/sitemap.xml", "",
                          limit=len(pages), allow_local=True, delay=0, retries=0,
                          max_requests=len(pages) + 10)
        start, cpu_start = perf_counter(), process_time()
        result = ToolRunner(workspace).run(tools.AUDIT, cfg, log=lambda _: None)
        durations["audit_total"] = perf_counter() - start
        durations["audit_cpu"] = process_time() - cpu_start
        assert result.status == "succeeded" and result.counts["observed"] == len(pages), result.warnings
        with TestClient(create_app(workspace), base_url="http://127.0.0.1:8765") as client:
            fetch = measure("results_request", client.get)
            assert fetch(f"/runs/{result.run_id}").status_code == 200
        return {"observed": result.counts["observed"], "requests": result.counts["requests"],
                "pages_compared": result.counts["pages_compared"], "pairs": result.counts["pairs_flagged"],
                "seconds": {name: round(value, 4) for name, value in durations.items()}}


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--pages", type=int, default=300, help="number of generated fixture pages")
    parser.add_argument("--html-dir", type=Path, help="directory of saved .html responses to replay instead")
    args = parser.parse_args()
    corpus = ([path.read_bytes() for path in sorted(args.html_dir.glob("*.html"))]
              if args.html_dir else sample(args.pages))
    if not 1 <= len(corpus) <= 1000:
        parser.error("Supply 1–1,000 HTML pages.")
    summary = run(corpus)
    if sys.platform.startswith("linux"):
        from resource import RUSAGE_SELF, getrusage

        summary["peak_rss_kib"] = getrusage(RUSAGE_SELF).ru_maxrss
    print(json.dumps(summary, indent=2))
