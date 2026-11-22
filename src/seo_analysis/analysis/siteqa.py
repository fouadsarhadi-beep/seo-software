"""Read-only inspection of a selected build directory and optional browser test reports."""

from collections import Counter
from dataclasses import dataclass
import json
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

from seo_analysis.analysis.lighthouse import import_lighthouse
from seo_analysis.core.artifacts import write_json
from seo_analysis.reporting.report import write_csv
from seo_analysis.web.extract import extract_page


@dataclass
class SiteQAInput:
    directory: str
    lighthouse: str = ""
    axe: str = ""
    access_log: str = ""
    baseline: str = ""
    screenshot: str = ""


def compare_screenshots(ctx, baseline, screenshot):
    from PIL import Image, ImageChops

    if not baseline or not screenshot:
        raise ValueError("Select both an approved baseline and a current PNG screenshot.")
    with Image.open(baseline, formats=["PNG"]) as first, Image.open(screenshot, formats=["PNG"]) as second:
        if first.size != second.size or first.width * first.height > 16_000_000:
            raise ValueError("Select same-sized screenshots of up to 16 megapixels.")
        difference = ImageChops.difference(first.convert("RGBA"), second.convert("RGBA"))
        mask = difference.getchannel("R")
        for channel in ("G", "B", "A"):
            mask = ImageChops.lighter(mask, difference.getchannel(channel))
        changed = mask.width * mask.height - mask.histogram()[0]
        if changed:
            mask.point(lambda value: 255 if value else 0).save(ctx.directory / "changed-pixels.png")
        return dict(
            baseline=Path(baseline).name,
            screenshot=Path(screenshot).name,
            size=first.size,
            changed_pixels=changed,
            total_pixels=mask.width * mask.height,
            bounding_box=mask.getbbox(),
        )


def summarize_log(filename):
    """Count paths and statuses from Apache/Nginx common and combined request lines."""
    path = Path(filename)
    if path.stat().st_size > 25_000_000:
        raise ValueError("Select an access log of 25 MB or less.")
    request_line = re.compile(r'^\S+ \S+ \S+ \[[^\]]+\] "[A-Z]+ (/[^ ]*) HTTP/[0-9.]+" ([1-5][0-9]{2}) ')
    counts, skipped = Counter(), 0
    with path.open(encoding="utf-8", errors="replace") as file:
        for line in file:
            match = request_line.match(line)
            if not match:
                skipped += 1
                continue
            route = match[1].split("?", 1)[0].split("#", 1)[0]
            counts[route, int(match[2])] += 1
    return dict(
        source_file=path.name,
        skipped=skipped,
        observations=[
            dict(path=route, status=status, requests=count)
            for (route, status), count in sorted(counts.items())
        ],
    )


def inspect_build(ctx, request):
    root = Path(request.directory).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Select a local HTML build directory.")
    pages, findings, skipped = [], [], Counter()
    for current, dirs, files in root.walk(follow_symlinks=False):
        dirs[:] = sorted(
            d
            for d in dirs
            if not d.startswith(".")
            and d not in ("node_modules", "__pycache__")
            and not (current / d).is_symlink()
        )
        for name in sorted(files):
            path = current / name
            if path.suffix.lower() not in (".htm", ".html"):
                continue
            if path.is_symlink() or path.stat().st_size > 2_000_000 or len(pages) >= 1000:
                skipped["html files outside limits"] += 1
                continue
            relative = path.relative_to(root).as_posix()
            html = path.read_text(encoding="utf-8-sig", errors="replace")
            pd = extract_page(html, "https://build.invalid/" + relative)
            pages.append(
                {
                    "file": relative,
                    "title": pd.title,
                    "h1": pd.h1_list,
                    "canonical": pd.canonicals,
                    "lang": pd.lang,
                    "schema": pd.markup["schema"],
                }
            )
            for field in ("title", "meta_description", "lang", "h1_list"):
                if not getattr(pd, field):
                    findings.append([relative, "missing-" + field, ""])
            for asset in pd.markup["assets"]:
                ref = urlsplit(asset["url"])
                if ref.hostname == "build.invalid":
                    target = (root / unquote(ref.path).lstrip("/")).resolve()
                    if not target.is_relative_to(root):
                        findings.append([relative, "asset outside selected directory", ref.path])
                    elif not target.is_file():
                        findings.append([relative, "missing build asset", ref.path])
                if asset["alt_state"] == "absent":
                    findings.append([relative, "image lacks alt attribute", asset["url"]])
    diagnostics = {}
    if request.lighthouse:
        diagnostics["lighthouse"] = import_lighthouse(request.lighthouse)
    if request.axe:
        path = Path(request.axe)
        if path.stat().st_size > 25_000_000:
            raise ValueError("QA report exceeds 25 MB.")
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict) or not isinstance(data.get("violations"), list) or any(
            not isinstance(v, dict)
            or not isinstance(v.get("id"), str)
            or not isinstance(v.get("nodes", []), list)
            for v in data["violations"]
        ):
            raise ValueError("Expected an axe report with violations.")
        diagnostics["axe"] = {
            "url": data.get("url"),
            "source_file": path.name,
            "violations": [
                {"id": v["id"], "impact": v.get("impact"), "nodes": len(v.get("nodes", []))}
                for v in data["violations"]
            ],
        }
    if request.baseline or request.screenshot:
        diagnostics["visual_comparison"] = compare_screenshots(ctx, request.baseline, request.screenshot)
    if request.access_log:
        log = summarize_log(request.access_log)
        diagnostics["access_log"] = log
        if log["skipped"]:
            skipped["unrecognized log lines"] = log["skipped"]
    if not pages:
        raise ValueError("No inspectable HTML files.")
    write_json(
        ctx.directory / "site-qa.json",
        dict(
            schema_version=1,
            root=str(root),
            pages=pages,
            findings=findings,
            imported_reports=diagnostics,
            skipped=skipped,
        ),
    )
    write_csv(ctx.directory / "site-qa.csv", ["Build file", "Observation", "Reference"], findings)
    return dict(
        status="partial" if skipped else "succeeded",
        counts=dict(pages=len(pages), findings=len(findings), skipped=skipped),
    )
