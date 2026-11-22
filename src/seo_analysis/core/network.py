"""Origin scope for a sitemap crawl. Transport address policy belongs in the fetcher."""
from dataclasses import dataclass
from urllib.parse import urlsplit

from requests import Request, RequestException


@dataclass(frozen=True)
class HttpOrigin:
    scheme: str
    host: str
    port: int

    @classmethod
    def from_url(cls, url: str) -> "HttpOrigin":
        try:
            if not url or "\\" in url or any(c.isspace() or ord(c) < 32 for c in url):
                raise ValueError
            parts = urlsplit(url)
            if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username is not None:
                raise ValueError
            prepared = Request("GET", url).prepare()
            host = urlsplit(prepared.url).hostname
            port = parts.port
            if not host or port == 0:
                raise ValueError
            return cls(parts.scheme, host, port or (443 if parts.scheme == "https" else 80))
        except (ValueError, RequestException) as exc:
            raise ValueError("Expected an HTTP(S) URL with a hostname and no credentials.") from exc

    def allows(self, url: str) -> bool:
        try:
            return self == HttpOrigin.from_url(url)
        except ValueError:
            return False
