"""Read model over one saved audit run: observed pages, findings and the page query."""
from dataclasses import dataclass, field
from hashlib import sha256
import json
from math import ceil
from pathlib import Path
from urllib.parse import unquote, urlencode, urlsplit

from seo_analysis.core.urls import url_key

PAGE_SIZE = 30


@dataclass
class PageRow:
    """One observed page, joined to the findings that reference it."""
    url: str
    url_decoded: str
    final_url: str
    status: int | None
    first_status: int | None
    redirect_to: str
    redirect_count: int
    indexability: str
    indexability_reason: str
    title: str
    words: int | None
    evidence_id: str
    content_hash: str
    depth: int | None
    rules: list[str] = field(default_factory=list)

    @property
    def fingerprint(self) -> str:
        """Stable per-page evidence identity used to notice that a reviewed page changed."""
        seed = "|".join((self.url, self.final_url, self.status_text, self.indexability_text,
                         self.title, self.content_hash))
        return sha256(seed.encode("utf-8")).hexdigest()[:16]

    @property
    def path(self) -> str:
        """The path and query shown in tables, falling back to the full URL."""
        parts = urlsplit(self.url)
        if not parts.scheme and not parts.netloc:
            return self.url
        return (parts.path or "/") + (f"?{parts.query}" if parts.query else "")

    @property
    def status_text(self) -> str:
        return str(self.status) if self.status is not None else "Unknown"

    @property
    def indexability_text(self) -> str:
        return self.indexability or "unknown"


@dataclass
class FindingRow:
    rule: str
    category: str
    detail: str
    evidence_ids: tuple[str, ...]


@dataclass
class Audit:
    manifest: dict
    pages: list[PageRow]
    findings: list[FindingRow]
    evidence: dict[str, PageRow]

    @property
    def site(self) -> str:
        parameters = self.manifest.get("parameters") or {}
        return str(parameters.get("source") or parameters.get("sitemap") or "")

    def rules(self) -> list[dict]:
        """Group findings by rule, counting occurrences separately from affected URLs."""
        groups: dict[str, dict] = {}
        for finding in self.findings:
            item = groups.setdefault(finding.rule, {
                "rule": finding.rule, "category": finding.category, "detail": finding.detail,
                "occurrences": 0, "urls": set(),
            })
            item["occurrences"] += 1
            for evidence_id in finding.evidence_ids:
                page = self.evidence.get(evidence_id)
                if page is not None:
                    item["urls"].add(page.url)
        rows = []
        for item in groups.values():
            row = dict(item)
            row["urls"] = len(item["urls"])
            rows.append(row)
        rows.sort(key=lambda row: (-row["urls"], -row["occurrences"], row["rule"]))
        return rows


def _number(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _status(value):
    """A status of 0 means no HTTP response was received, not a real status code."""
    number = _number(value)
    return number if number else None


def _redirected_to(url: str, final_url: str, redirect_count: int) -> str:
    """Compare normalised URLs so an encoding or case change is not read as a redirect."""
    if not final_url or redirect_count <= 0:
        return ""
    try:
        if url_key(url) == url_key(final_url):
            return ""
    except ValueError:
        if url == final_url:
            return ""
    return final_url


def load_audit(directory, manifest: dict) -> Audit:
    """Build the read model from the saved run directory. Missing files are empty, not errors."""
    directory = Path(directory)
    pages: list[PageRow] = []
    evidence: dict[str, PageRow] = {}
    snapshot = directory / "snapshot.jsonl"
    if snapshot.is_file():
        for line in snapshot.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            url = str(record.get("url") or record.get("raw_url") or "")
            if not url:
                continue
            final_url = str(record.get("final_url") or "")
            chain = record.get("chain")
            redirect_count = max(0, len(chain) - 1) if isinstance(chain, list) else 0
            page = PageRow(
                url=url,
                url_decoded=unquote(url),
                final_url=final_url,
                status=_status(record.get("final_status")),
                first_status=_status(record.get("first_status")),
                redirect_to=_redirected_to(url, final_url, redirect_count),
                redirect_count=redirect_count,
                indexability=str(record.get("effective_indexability") or "unknown"),
                indexability_reason=str(record.get("indexability_reason") or ""),
                title=str(record.get("title") or ""),
                words=_number(record.get("words")),
                evidence_id=str(record.get("evidence_id") or ""),
                content_hash=str(record.get("content_hash") or ""),
                depth=_number(record.get("depth")),
            )
            pages.append(page)
            if page.evidence_id:
                evidence[page.evidence_id] = page
    findings: list[FindingRow] = []
    findings_file = directory / "findings.json"
    if findings_file.is_file():
        data = json.loads(findings_file.read_text(encoding="utf-8"))
        for item in data.get("findings") or ():
            findings.append(FindingRow(
                rule=str(item.get("rule") or ""),
                category=str(item.get("category") or ""),
                detail=str(item.get("detail") or ""),
                evidence_ids=tuple(item.get("evidence_ids") or ()),
            ))
    for finding in findings:
        for evidence_id in finding.evidence_ids:
            target = evidence.get(evidence_id)
            if target is not None and finding.rule not in target.rules:
                target.rules.append(finding.rule)
    return Audit(manifest=manifest, pages=pages, findings=findings, evidence=evidence)


@dataclass
class PageQuery:
    rows: list[PageRow]
    total: int
    matched: int
    page: int
    page_count: int
    per_page: int
    first: int
    last: int
    filters: dict
    active: bool

    def href(self, page: int) -> str:
        """Link to one page of results that keeps the current filters."""
        params = {key: value for key, value in self.filters.items()
                  if value and not (key == "sort" and value == "url")}
        params.pop("page", None)
        if page > 1:
            params["page"] = page
        return "?" + urlencode(params) if params else "?"


def _matches_status(page: PageRow, term: str) -> bool:
    term = term.strip().lower()
    if not term:
        return True
    if term in ("error", "failed"):
        return page.status is None or page.status >= 400
    if len(term) == 3 and term.endswith("xx") and term[0].isdigit():
        return page.status is not None and page.status // 100 == int(term[0])
    value = _number(term)
    return value is not None and page.status == value


def query_pages(pages, *, url="", status="", redirect="", indexability="", rule="", sort="url",
                page=1, per_page=PAGE_SIZE) -> PageQuery:
    """Filter, sort and slice observed pages. Shared by the page table and filtered exports."""
    term = unquote(url).strip().casefold()
    redirect = redirect.strip().lower()
    indexability = indexability.strip().lower()
    rule = rule.strip()
    rows = []
    for item in pages:
        if term and not any(term in value.casefold() for value in (item.url, item.url_decoded, item.final_url)):
            continue
        if not _matches_status(item, status):
            continue
        if redirect == "any" and item.redirect_count <= 0:
            continue
        if redirect == "none" and item.redirect_count > 0:
            continue
        if indexability == "unknown":
            if item.indexability != "unknown":
                continue
        elif indexability == "excluded":
            # A known exclusion: the HTTP status itself keeps the page out of the index.
            if item.indexability != "not_indexable_status":
                continue
        elif indexability and item.indexability != indexability:
            continue
        if rule and rule not in item.rules:
            continue
        rows.append(item)
    if sort == "status":
        rows.sort(key=lambda item: (item.status is None, item.status or 0, item.url))
    elif sort == "findings":
        rows.sort(key=lambda item: (-len(item.rules), item.url))
    else:
        rows.sort(key=lambda item: item.url)
    total = len(pages)
    matched = len(rows)
    page_count = max(1, ceil(matched / per_page)) if matched else 1
    page = min(max(1, _number(page) or 1), page_count)
    start = (page - 1) * per_page
    return PageQuery(
        rows=rows[start:start + per_page], total=total, matched=matched, page=page,
        page_count=page_count, per_page=per_page,
        first=start + 1 if matched else 0, last=min(start + per_page, matched),
        filters={"url_q": url, "status": status, "redirect": redirect, "indexability": indexability,
                 "rule": rule, "sort": sort},
        active=bool(term or status.strip() or redirect or indexability or rule),
    )