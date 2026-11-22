"""Prepare one explicitly selected dataset table for local use or publication."""
from dataclasses import dataclass
from hashlib import sha256
import json
import math
from pathlib import Path

from seo_analysis.core.artifacts import write_json
from seo_analysis.reporting.report import csv_safe, write_csv
from seo_analysis.storage.history import History

MAX_ROWS = 10000
MAX_COLUMNS = 30
MAX_UPLOAD_BYTES = 1_500_000


@dataclass
class DatasetExportInput:
    dataset: str
    columns: tuple[str, ...]
    title: str
    max_rows: int = MAX_ROWS


def indexed_artifact(workspace, run_id, filename):
    record = History(workspace).show(run_id)
    path = Path(record["directory"]) / filename
    if (filename not in record["manifest"]["artifacts"] or not path.is_file() or path.is_symlink()
            or path.parent.resolve() != workspace.runs_dir.resolve() / run_id):
        raise ValueError(f"Run {run_id} has no indexed {filename} artifact.")
    return record["manifest"], path


def selection_hash(table):
    encoded = json.dumps(table, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))
    return sha256(encoded.encode("utf-8")).hexdigest()


def prepare_dataset(ctx, request):
    if not 1 <= request.max_rows <= MAX_ROWS:
        raise ValueError(f"Choose between 1 and {MAX_ROWS:,} rows.")
    columns = list(request.columns)
    if not columns or len(columns) > MAX_COLUMNS or len(set(columns)) != len(columns):
        raise ValueError(f"Select between 1 and {MAX_COLUMNS} distinct columns.")
    title = request.title.strip()
    if not title or len(title) > 100 or any(ord(c) < 32 for c in title):
        raise ValueError("Enter a spreadsheet title of 1–100 characters without control characters.")
    manifest, path = indexed_artifact(ctx.workspace, request.dataset, "dataset.json")
    if manifest["status"] not in ("succeeded", "partial"):
        raise ValueError("Select a finished dataset run.")
    dataset = json.loads(path.read_text(encoding="utf-8"))
    rows = dataset["rows"]
    known = {column for row in rows for column in row}
    if not rows or set(columns) - known:
        raise ValueError("Choose a nonempty dataset and columns that exist in its normalized rows.")

    values = [[row.get(column) for column in columns] for row in rows[:request.max_rows]]
    for row in values:
        for value in row:
            if (value is not None and type(value) not in (str, int, float, bool)
                    or isinstance(value, float) and not math.isfinite(value)
                    or isinstance(value, str) and len(value) > 32760):
                raise ValueError("The selection contains a value that cannot be exported to a spreadsheet.")
    if len(json.dumps([columns, *values], ensure_ascii=True).encode()) > MAX_UPLOAD_BYTES:
        raise ValueError("Select fewer rows or columns to keep the Sheets upload below 1.5 MB.")

    source_partial = manifest["status"] == "partial"
    capped = len(rows) > len(values)
    table = {
        "schema_version": 1, "title": title, "dataset_run_id": request.dataset,
        "columns": columns, "rows": values, "source_partial": source_partial, "capped": capped,
        "source_rows": len(rows),
    }
    summary = {key: value for key, value in table.items() if key != "rows"}
    summary.update(rows=len(values), sha256=selection_hash(table))
    write_csv(ctx.directory / "selected.csv", columns, values)

    from openpyxl import Workbook
    from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE

    book = Workbook(write_only=True)
    sheet = book.create_sheet("Data")
    sheet.append([csv_safe(column) for column in columns])
    for row in values:
        sheet.append([csv_safe(ILLEGAL_CHARACTERS_RE.sub("", value)) if isinstance(value, str) else value
                      for value in row])
    book.save(ctx.directory / "selected.xlsx")
    write_json(ctx.directory / "table.json", table)
    write_json(ctx.directory / "export.json", summary)
    warnings = []
    if capped:
        warnings.append(f"Selected the first {len(values)} of {len(rows)} normalized rows.")
    if source_partial:
        warnings.append("The source dataset was partial.")
    return {"status": "partial" if warnings else "succeeded", "warnings": warnings,
            "counts": {"rows": len(values), "columns": len(columns), "source_rows": len(rows)}}
