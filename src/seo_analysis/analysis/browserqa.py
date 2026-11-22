"""Capture one page from a trusted local build in a fresh Chromium context."""
from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
from mimetypes import guess_type
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

from seo_analysis.analysis.siteqa import compare_screenshots
from seo_analysis.core.artifacts import write_json

BUILD_ORIGIN = "http://build.test"
MAX_FILE = 20_000_000
MAX_REQUESTS = 300
MAX_TOTAL_BYTES = 60_000_000
CSP = (
    "default-src 'self'; script-src 'self' 'unsafe-inline' blob:; "
    "style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; "
    "worker-src 'none'; object-src 'none'; frame-src 'none'; form-action 'none'; base-uri 'self'"
)


@dataclass
class BrowserQAInput:
    directory: str
    page: str = "/"
    width: int = 1365
    height: int = 768
    axe_script: str = ""
    baseline: str = ""
    chromium: str = ""


def build_file(root, url_path):
    path = unquote(url_path)
    parts = path.split("/")
    if ("\\" in path or "\x00" in path or any(part.startswith(".") or part == "node_modules" for part in parts)):
        return None
    candidate = (root / path.lstrip("/")).resolve()
    if not candidate.is_relative_to(root):
        return None
    if candidate.is_dir():
        candidate = (candidate / "index.html").resolve()
    if (candidate.is_relative_to(root) and candidate.is_file()
            and not any(part.startswith(".") or part == "node_modules" for part in candidate.relative_to(root).parts)):
        return candidate
    return None


def browser_qa(ctx, request):
    root = Path(request.directory).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Select a build directory.")
    parts = urlsplit(request.page)
    if not request.page.startswith("/") or parts.netloc or parts.scheme or parts.fragment:
        raise ValueError("Select a local page path starting with /.")
    page_file = build_file(root, parts.path)
    if page_file is None or page_file.suffix.lower() not in (".html", ".htm"):
        raise ValueError("The selected page has no HTML file in the local build.")
    if not 240 <= request.width <= 3840 or not 240 <= request.height <= 2160:
        raise ValueError("Choose a viewport between 240×240 and 3840×2160.")
    axe_source = None
    axe_digest = None
    if request.axe_script:
        with Path(request.axe_script).open("rb") as stream:
            data = stream.read(2_000_001)
        if len(data) > 2_000_000:
            raise ValueError("The selected axe-core script exceeds 2 MB.")
        axe_source = data.decode("utf-8-sig")
        axe_digest = sha256(data).hexdigest()

    try:
        from playwright.sync_api import Error, sync_playwright
    except ImportError:
        raise RuntimeError("Install the browser extra and run playwright install chromium.") from None

    counts = Counter()
    failures = Counter()
    screenshot = ctx.directory / "screenshot.png"
    url = BUILD_ORIGIN + quote(parts.path, safe="/%")
    if parts.query:
        url += "?" + parts.query

    def handle(route):
        request_url = urlsplit(route.request.url)
        counts["requests"] += 1
        if counts["requests"] > MAX_REQUESTS:
            failures["request limit"] += 1
            route.abort()
            return
        if f"{request_url.scheme}://{request_url.netloc}" != BUILD_ORIGIN or route.request.method != "GET":
            failures["request outside local build"] += 1
            route.abort()
            return
        try:
            path = build_file(root, request_url.path)
            if path is None:
                failures["missing local file"] += 1
                route.fulfill(status=404, body="Missing local file.")
                return
            with path.open("rb") as stream:
                body = stream.read(MAX_FILE + 1)
            if len(body) > MAX_FILE:
                failures["local file exceeds size limit"] += 1
                route.abort()
                return
        except OSError:
            failures["local file read failed"] += 1
            route.abort()
            return
        if counts["served_bytes"] + len(body) > MAX_TOTAL_BYTES:
            failures["build response byte limit"] += 1
            route.abort()
            return
        content_type = guess_type(path)[0] or "application/octet-stream"
        route.fulfill(status=200, body=body, content_type=content_type, headers={
            "Content-Security-Policy": CSP, "X-Content-Type-Options": "nosniff",
        })
        counts["local_responses"] += 1
        counts["served_bytes"] += len(body)

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                executable_path=request.chromium or None,
                args=["--host-resolver-rules=MAP * ~NOTFOUND", "--force-webrtc-ip-handling-policy=disable_non_proxied_udp"],
                timeout=20_000,
            )
            browser_version = browser.version
            with browser.new_context(
                viewport={"width": request.width, "height": request.height},
                device_scale_factor=1, service_workers="block", offline=True,
                reduced_motion="reduce", accept_downloads=False,
            ) as context:
                context.route("**/*", handle)
                context.route_web_socket("**/*", lambda socket: socket.close())
                page = context.new_page()
                page.set_default_timeout(15_000)
                page.on("pageerror", lambda _: failures.update(["page script errors"]))
                response = page.goto(url, wait_until="load")
                landed = urlsplit(page.url)
                if (not response or response.status != 200 or f"{landed.scheme}://{landed.netloc}" != BUILD_ORIGIN
                        or unquote(landed.path) != unquote(parts.path)):
                    raise RuntimeError("The selected local page did not finish loading at the requested path.")
                page.screenshot(path=screenshot, animations="disabled")
                timing = page.evaluate("""() => {
                    const nav = performance.getEntriesByType('navigation')[0];
                    return {dom_content_loaded_ms: nav?.domContentLoadedEventEnd ?? null,
                            load_ms: nav?.loadEventEnd ?? null};
                }""")
                if axe_source:
                    page.add_script_tag(content=axe_source)
                    axe = page.evaluate("""async () => {
                        if (!window.axe?.run) return null;
                        const scan = await window.axe.run({resultTypes: ['violations']});
                        return {
                            url: scan.url, testEngine: scan.testEngine,
                            violations: scan.violations.map(({id, impact, nodes}) => ({
                                id, impact, nodes: nodes.map(({target, failureSummary}) => ({target, failureSummary}))
                            })),
                            manual_review_count: scan.incomplete.length,
                        };
                    }""")
                    if axe is None:
                        raise ValueError("The selected JavaScript did not provide the axe-core API.")
                    axe["script_sha256"] = axe_digest
                    write_json(ctx.directory / "axe.json", axe)
                    counts["axe_violations"] = len(axe["violations"])
            browser.close()
    except Error as exc:
        detail = str(exc)
        if "Executable doesn't exist" in detail:
            raise RuntimeError("Install Chromium with playwright install chromium or supply --chromium.") from None
        raise RuntimeError("Chromium could not capture the selected local build.") from None

    report = {"schema_version": 1, "page": request.page, "viewport": [request.width, request.height],
              "screenshot": screenshot.name, "chromium_version": browser_version, "timings": timing,
              "observations": dict(counts),
              "resource_observations": dict(failures), "axe_report": "axe.json" if axe_source else None}
    if request.baseline:
        report["visual_comparison"] = compare_screenshots(ctx, request.baseline, screenshot)
    write_json(ctx.directory / "browser-qa.json", report)
    warnings = ["Timings describe the local Chromium run. They vary by machine and build."]
    warnings.extend(f"{label}: {count}" for label, count in failures.items())
    return {"status": "partial" if failures else "succeeded", "warnings": warnings, "counts": dict(counts)}
