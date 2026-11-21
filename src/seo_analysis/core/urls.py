"""URL helpers that respect Persian-site realities.

WordPress stores non-Latin slugs percent-encoded with lower-case hex, browsers and
Search Console may show them decoded or with upper-case hex, and a Persian domain can be
written as Unicode or punycode. Comparing raw strings would report false differences,
so everything goes through url_key().
"""
from __future__ import annotations

import re
import string
import unicodedata
from urllib.parse import unquote_to_bytes

import idna
from urllib.parse import unquote, urlsplit


def _component(value):
    def decode_match(match):
        raw = unquote_to_bytes(match.group())
        try:
            chars = raw.decode("utf-8")
        except UnicodeDecodeError:
            return match.group().upper()
        return "".join(c if ord(c) > 127 or c in string.ascii_letters + string.digits + "-._~"
                       else f"%{ord(c):02X}" for c in chars)
    return unicodedata.normalize("NFC", re.sub(r"(?:%[0-9a-fA-F]{2})+", decode_match, value))


def _parts(url: str):
    s = urlsplit((url or "").strip())
    scheme = s.scheme.lower()
    host = (s.hostname or "").rstrip(".")
    try:
        host = idna.encode(host, uts46=True).decode("ascii")
    except (UnicodeError, idna.IDNAError):
        pass
    host = host.lower()
    try:
        port = s.port
    except ValueError:
        port = None
    if port == {"http": 80, "https": 443}.get(scheme):
        port = None
    path = _component(s.path) or "/"
    query = _component(s.query)
    return scheme, host, port, path, query


def url_key(url: str, loose: bool = False) -> str:
    """Comparison key. Strict: scheme+host+decoded path+query. Loose: ignores scheme, www, trailing slash."""
    scheme, host, port, path, query = _parts(url)
    if loose:
        scheme = "*"
        host = host[4:] if host.startswith("www.") else host
        path = path.rstrip("/") or "/"
    if ":" in host:
        host = f"[{host}]"
    hostport = host + (f":{port}" if port else "")
    return f"{scheme}://{hostport}{path}" + (f"?{query}" if query else "")


def relation(a: str, b: str) -> tuple[str, str]:
    """How does URL b relate to URL a? -> (code, human text)."""
    if a == b:
        return "same", "same"
    if url_key(a) == url_key(b):
        return "same_encoding", "same page (written differently: encoding or case)"
    if url_key(a, loose=True) == url_key(b, loose=True):
        sa, ha, _, pa, _ = _parts(a)
        sb, hb, _, pb, _ = _parts(b)
        diffs = []
        if sa != sb:
            diffs.append("scheme")
        if ha != hb:
            diffs.append("www/host")
        if pa != pb:
            diffs.append("trailing slash")
        return "variant", "differs only by " + ", ".join(diffs or ["formatting"])
    return "other", "different URL"


def decoded(url: str) -> str:
    return unquote(url or "")


def host_of(url: str) -> str:
    return _parts(url)[1]


def is_http(url: str) -> bool:
    return urlsplit((url or "").strip()).scheme.lower() in ("http", "https")
