"""Polite HTTP fetching: bounded redirects with scope checks, retries only for temporary
failures (429/5xx and connection errors, honouring Retry-After), body-size cap, and
Persian-aware decoding (UTF-8 first, then the declared charset, then windows-1256)."""
from __future__ import annotations

import math
import random
import re
import time
from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin

import requests
from urllib3.exceptions import HTTPError

from seo_analysis.core.network import HttpOrigin
from seo_analysis.web.transport import BudgetExceeded, CrawlBudget, scoped_adapter
from seo_analysis.core.urls import url_key

REDIRECTS = {301, 302, 303, 307, 308}
RETRY_STATUSES = {429, 500, 502, 503, 504}


def decode_body(raw: bytes, content_type: str = "") -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        pass
    declared = re.search(r"charset=([\w-]+)", content_type or "", re.I)
    sniff = re.search(rb"<meta[^>]+charset=[\"']?([\w-]+)", raw[:4096], re.I)
    for cs in (declared.group(1) if declared else None, sniff.group(1).decode() if sniff else None, "cp1256"):
        if not cs:
            continue
        try:
            return raw.decode(cs)
        except (LookupError, UnicodeDecodeError):
            continue
    return raw.decode("utf-8", errors="replace")


@dataclass
class FetchResult:
    requested_url: str
    final_url: str = ""
    first_status: int = 0
    final_status: int = 0
    chain: list = field(default_factory=list)        # [(url, status), ...]
    redirect_note: str = ""                          # "", loop, too_many, blocked_external:<url>, blocked_robots:<url>
    content_type: str = ""
    x_robots: list = field(default_factory=list)
    link_headers: list = field(default_factory=list)
    raw: bytes = b""
    truncated: bool = False
    error: str = ""
    retries_used: int = 0

    @property
    def text(self) -> str:
        return decode_body(self.raw, self.content_type)

    @property
    def redirect_count(self) -> int:
        return max(0, len(self.chain) - 1) if self.chain else 0


def _getlist(resp, name: str) -> list:
    try:
        return list(resp.raw.headers.getlist(name))
    except Exception:
        v = resp.headers.get(name)
        return [v] if v else []


class Fetcher:
    def __init__(self, user_agent: str, delay: float = 0.5, timeout=(10, 30), retries: int = 2,
                 max_redirects: int = 5, max_bytes: int = 5_000_000, *, origin: HttpOrigin,
                 robots=None, robots_agent: str = "*", backoff_base: float = 1.0,
                 sleep=time.sleep, allow_local=False, max_requests=500, max_seconds=300):
        if not (math.isfinite(delay) and delay >= 0 and 0 < max_seconds <= 86400):
            raise ValueError("Invalid pacing or time budget.")
        if min(max_requests, max_bytes) < 1 or min(retries, max_redirects) < 0:
            raise ValueError("Invalid request, response, retry or redirect budget.")
        self.budget = CrawlBudget(max_requests, max_seconds)
        self.session = requests.Session()
        self.session.trust_env = False
        self.session.mount(origin.scheme + "://", scoped_adapter(origin, allow_local, self.budget))
        self.session.headers.update({"User-Agent": user_agent})
        self.delay, self.timeout, self.retries = delay, timeout, retries
        self.max_redirects, self.max_bytes = max_redirects, max_bytes
        self.origin = origin
        self.robots, self.robots_agent = robots, robots_agent
        self.backoff_base, self.sleep = backoff_base, sleep
        self._last = 0.0

    # -- scope and pacing
    def in_scope(self, url: str) -> bool:
        return self.origin.allows(url)

    def _pace(self):
        wait = self.delay - (time.monotonic() - self._last)
        if wait > 0:
            self._wait(wait)
        self._last = time.monotonic()

    def _wait(self, seconds):
        if seconds >= self.budget.remaining():
            raise BudgetExceeded("Time budget insufficient for the next request.")
        self.sleep(seconds)

    def _retry_delay(self, resp, attempt: int) -> float:
        ra = resp.headers.get("Retry-After") if resp is not None else None
        if ra:
            ra = ra.strip()
            try:
                return min(60.0, max(0.0, float(ra)))
            except ValueError:
                try:
                    delta = (parsedate_to_datetime(ra).timestamp() - time.time())
                    return min(60.0, max(0.0, delta))
                except Exception:
                    pass
        return min(30.0, self.backoff_base * 2 ** (attempt - 1)) + random.uniform(0, self.backoff_base * 0.25)

    def _request(self, url):
        attempt = 0
        while True:
            attempt += 1
            self.budget.charge()
            self._pace()
            try:
                resp = self.session.get(url, timeout=tuple(min(t, self.budget.remaining()) for t in self.timeout), allow_redirects=False, stream=True)
            except requests.RequestException as exc:
                if attempt > self.retries:
                    return None, f"{type(exc).__name__}: {exc}", attempt - 1
                self._wait(self._retry_delay(None, attempt))
                continue
            if resp.status_code in RETRY_STATUSES and attempt <= self.retries:
                delay = self._retry_delay(resp, attempt)
                resp.close()
                self._wait(delay)
                continue
            return resp, "", attempt - 1

    def _read_final(self, resp, res: FetchResult, url: str):
        res.final_url, res.final_status = url, resp.status_code
        res.content_type = resp.headers.get("Content-Type", "")
        res.x_robots = _getlist(resp, "x-robots-tag")
        res.link_headers = _getlist(resp, "link")
        chunks, total = [], 0
        while True:
            remaining = self.budget.remaining()
            connection = resp.raw.connection
            if connection is not None and connection.sock is not None:
                connection.sock.settimeout(min(self.timeout[1], remaining))
            chunk = resp.raw.read1(min(65536, self.max_bytes - total + 1), decode_content=True)
            if not chunk:
                break
            if total + len(chunk) > self.max_bytes:
                chunks.append(chunk[: self.max_bytes - total])
                res.truncated = True
                break
            total += len(chunk)
            chunks.append(chunk)
        resp.close()
        res.raw = b"".join(chunks)

    def get(self, url: str) -> FetchResult:
        res = FetchResult(requested_url=url)
        current, seen = url, set()
        for hop in range(self.max_redirects + 1):
            if not self.in_scope(current):
                res.redirect_note, res.final_url = f"blocked_external:{current}", current
                return res
            if self.robots and not self.robots.allowed(current, self.robots_agent):
                res.redirect_note, res.final_url = f"blocked_robots:{current}", current
                return res
            seen.add(url_key(current))
            resp, err, used = self._request(current)
            res.retries_used += used
            if resp is None:
                res.error, res.final_url = err, current
                return res
            res.chain.append((current, resp.status_code))
            if hop == 0:
                res.first_status = resp.status_code
            loc = resp.headers.get("Location")
            if resp.status_code in REDIRECTS and loc:
                nxt = urljoin(current, loc)
                resp.close()
                res.final_status, res.final_url = resp.status_code, nxt
                if self.in_scope(nxt) and url_key(nxt) in seen:
                    res.redirect_note = "loop"
                    return res
                current = nxt
                continue
            try:
                self._read_final(resp, res, current)
            except (requests.RequestException, HTTPError) as exc:
                res.error = f"Response interrupted: {type(exc).__name__}"
            finally:
                resp.close()
            return res
        res.redirect_note = "too_many"
        return res
