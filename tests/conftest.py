import threading
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote

import pytest


class Site:
    """A tiny local web server so tests never touch a real website."""

    def __init__(self):
        self.routes, self.hits = {}, Counter()
        site = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                key = unquote(self.path.split("?")[0])
                site.hits[key] += 1
                spec = site.routes.get(key)
                if callable(spec):
                    spec = spec(site.hits[key])
                status, headers, body = spec if spec else (404, [], b"not found")
                self.send_response(status)
                for k, v in headers:
                    self.send_header(k, v)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        self.base = f"http://127.0.0.1:{self.port}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def add(self, path, body="", status=200, headers=None, ctype="text/html; charset=utf-8"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        h = list(headers or [])
        if ctype:
            h.append(("Content-Type", ctype))
        self.routes[path] = (status, h, body)

    def redirect(self, path, to, status=301):
        self.routes[path] = (status, [("Location", to)], b"")

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def site():
    s = Site()
    yield s
    s.close()


@pytest.fixture(autouse=True)
def isolated_default_workspace(tmp_path, monkeypatch):
    from seo_analysis.core.workspace import Workspace
    original = Workspace.load
    def load(config_file=None):
        if config_file is not None:
            return original(config_file)
        return Workspace(tmp_path / "config.toml", tmp_path / "workspace", tmp_path / "exports")
    monkeypatch.setattr(Workspace, "load", staticmethod(load))
