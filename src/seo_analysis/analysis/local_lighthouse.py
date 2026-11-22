"""Run a trusted local Lighthouse installation against one selected build page."""
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from mimetypes import guess_type
from pathlib import Path
from shutil import which
from subprocess import DEVNULL, Popen, TimeoutExpired, run
from tempfile import TemporaryDirectory
from threading import Lock, Thread
from time import monotonic, sleep
from urllib.parse import quote, urlsplit

from seo_analysis.analysis.browserqa import CSP, MAX_FILE, MAX_REQUESTS, MAX_TOTAL_BYTES, build_file
from seo_analysis.analysis.lighthouse import import_lighthouse
from seo_analysis.connectors.performance import lab_report


@dataclass
class LocalLighthouseInput:
    directory: str
    lighthouse_cli: str
    chromium: str
    page: str = "/"
    device: str = "mobile"


@contextmanager
def serve_build(root):
    counts = Counter()
    guard = Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_CONNECT(self):
            with guard:
                counts["blocked_external"] += 1
            self.send_error(403)

        def do_GET(self):
            self._respond()

        def do_HEAD(self):
            self._respond()

        def _respond(self):
            try:
                target = urlsplit(self.path)
            except ValueError:
                self.send_error(400)
                return
            if (self.headers.get("Host") != host or target.fragment
                    or (target.netloc and (target.scheme != "http" or target.netloc != host))):
                with guard:
                    counts["blocked_external"] += 1
                self.send_error(403)
                return
            try:
                file = build_file(root, target.path)
                if not file:
                    self.send_error(404)
                    return
                with guard:
                    counts["requests"] += 1
                    if counts["requests"] > MAX_REQUESTS:
                        self.send_error(429)
                        return
                    with file.open("rb") as stream:
                        body = stream.read(MAX_FILE + 1)
                    if len(body) > MAX_FILE or counts["served_bytes"] + len(body) > MAX_TOTAL_BYTES:
                        counts["byte_limit"] += 1
                        self.send_error(413)
                        return
                    counts["served_bytes"] += len(body)
            except (OSError, RuntimeError):
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", guess_type(file)[0] or "application/octet-stream")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Content-Security-Policy", CSP)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            if self.command == "GET":
                try:
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError):
                    pass

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        host = f"127.0.0.1:{server.server_port}"
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield "http://" + host, counts
        finally:
            server.shutdown()
            thread.join()


@contextmanager
def debugging_chromium(executable, origin, profile):
    args = [
        executable, "--headless", "--no-first-run", "--disable-background-networking",
        "--remote-debugging-address=127.0.0.1", "--remote-debugging-port=0",
        f"--user-data-dir={profile}", f"--proxy-server={origin}", "--proxy-bypass-list=<-loopback>",
        "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1", "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
        "about:blank",
    ]
    with Popen(args, stdin=DEVNULL, stdout=DEVNULL, stderr=DEVNULL) as process:
        try:
            end = monotonic() + 15
            while monotonic() < end and process.poll() is None:
                try:
                    port = int((profile / "DevToolsActivePort").read_text(encoding="ascii").splitlines()[0])
                except (FileNotFoundError, IndexError, ValueError):
                    sleep(0.1)
                    continue
                if 1 <= port <= 65535:
                    yield port
                    return
            raise RuntimeError("Chromium did not open a local debugging session.")
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except TimeoutExpired:
                    process.kill()
                    process.wait()


def local_lighthouse(ctx, request):
    root = Path(request.directory).resolve(strict=True)
    parts = urlsplit(request.page)
    if not root.is_dir() or not request.page.startswith("/") or parts.netloc or parts.scheme or parts.fragment:
        raise ValueError("Select a build directory and a local page path starting with /.")
    page_file = build_file(root, parts.path)
    if not page_file or page_file.suffix.lower() not in (".html", ".htm"):
        raise ValueError("The selected page has no HTML file in the local build.")
    if request.device not in ("desktop", "mobile"):
        raise ValueError("Select desktop or mobile.")
    cli = Path(request.lighthouse_cli).resolve(strict=True)
    if not cli.is_file() or cli.suffix not in (".js", ".mjs", ".cjs"):
        raise ValueError("Select the installed Lighthouse JavaScript CLI file.")
    chromium = Path(request.chromium).resolve(strict=True)
    if not chromium.is_file():
        raise ValueError("Select an installed Chromium or Chrome executable.")
    node = which("node")
    if not node:
        raise RuntimeError("Install Node.js to run the Lighthouse CLI.")

    output = ctx.directory / "lighthouse.json"
    with serve_build(root) as (origin, counts), TemporaryDirectory(prefix="seo-lighthouse-") as temporary:
        url = origin + quote(parts.path, safe="/%")
        if parts.query:
            url += "?" + parts.query
        with debugging_chromium(str(chromium), origin, Path(temporary)) as port:
            args = [node, str(cli), url, f"--port={port}", "--hostname=127.0.0.1",
                    "--only-categories=performance", "--output=json",
                    f"--output-path={output}", "--quiet", "--max-wait-for-load=30000"]
            if request.device == "desktop":
                args.append("--preset=desktop")
            try:
                process = run(args, cwd=root, stdin=DEVNULL, stdout=DEVNULL, stderr=DEVNULL,
                              timeout=90, check=False)
            except TimeoutExpired:
                raise RuntimeError("Lighthouse exceeded the 90-second run limit.") from None
            if not output.is_file():
                raise RuntimeError(f"Lighthouse returned exit code {process.returncode} without a JSON report.")
            summary = import_lighthouse(output)
    audited = urlsplit(summary["url"] or "")
    if audited.netloc != urlsplit(origin).netloc or audited.scheme != "http":
        if not summary["runtime_error"]:
            raise RuntimeError("Lighthouse did not report the selected local build origin.")
    return lab_report(ctx, summary, "Local Lighthouse run", page=request.page, local_requests=dict(counts))
