"""Publish one reviewed export into a new, app-created Google spreadsheet."""
from dataclasses import dataclass
import json
import re

from filelock import FileLock

from seo_analysis.connectors.google import GoogleConnection, TOKEN_URL, google_json
from seo_analysis.core.artifacts import write_json
from seo_analysis.reporting.dataset_export import indexed_artifact, selection_hash

SHEETS_URL = "https://sheets.googleapis.com/v4/spreadsheets"


@dataclass
class SheetsPublishInput:
    export: str
    confirm: str


def publish_sheets(ctx, request):
    manifest, source = indexed_artifact(ctx.workspace, request.export, "table.json")
    if (manifest["tool_id"] != "report.export-dataset" or manifest["status"] not in ("succeeded", "partial")
            or manifest["project"] != ctx.project):
        raise ValueError("Select a finished dataset export from this workspace or project.")
    table = json.loads(source.read_text(encoding="utf-8"))
    digest = selection_hash(table)
    if digest != request.confirm:
        raise ValueError("Confirmation must match the SHA-256 in the export.json preview.")

    columns = table["columns"]
    values = table["rows"]
    directory = ctx.workspace.data_dir / "sheets-publications"
    directory.mkdir(exist_ok=True)
    receipt_path = directory / f"{request.export}.json"
    local_receipt = ctx.directory / "publication.json"
    with FileLock(str(receipt_path) + ".lock", timeout=5):
        receipt = json.loads(receipt_path.read_text(encoding="utf-8")) if receipt_path.is_file() else None
        if receipt and receipt["sha256"] != digest:
            raise ValueError("This export has changed since publication. Prepare a new export for the changed data.")
        if receipt and receipt["status"] == "creating":
            raise RuntimeError("The previous create request has an unknown outcome. Check Google Drive for the title shown in the preview.")
        if not receipt or receipt["status"] != "published":
            connection = GoogleConnection(ctx.workspace, ctx.project, "sheets")
            with connection.session() as (_, session):
                ctx.data_egress.append({"method": "POST", "endpoint": TOKEN_URL,
                                        "purpose": "Refresh the Google access token if needed"})
                if not receipt:
                    receipt = {"status": "creating", "export_run_id": request.export,
                               "sha256": digest, "title": table["title"], "tab": "Data"}
                    write_json(receipt_path, receipt)
                    ctx.data_egress.append({"method": "POST", "endpoint": SHEETS_URL,
                                            "purpose": "Create a spreadsheet", "approval": digest})
                    created = google_json(session, "POST", SHEETS_URL, json={
                        "properties": {"title": table["title"]},
                        "sheets": [{"properties": {"title": "Data", "gridProperties": {
                            "rowCount": len(values) + 1, "columnCount": len(columns), "frozenRowCount": 1,
                        }}}],
                    }, params={"fields": "spreadsheetId"})
                    spreadsheet_id = created.get("spreadsheetId")
                    if not isinstance(spreadsheet_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", spreadsheet_id):
                        raise RuntimeError("Google returned no valid spreadsheet ID. Check Google Drive for the export title.")
                    receipt.update(status="created", spreadsheet_id=spreadsheet_id,
                                   url=f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit")
                    write_json(receipt_path, receipt)
                write_json(local_receipt, receipt)

                endpoint = f"{SHEETS_URL}/{receipt['spreadsheet_id']}/values/Data%21A1"
                ctx.data_egress.append({"method": "PUT", "endpoint": endpoint, "purpose": "Write selected cells",
                                        "fields": columns, "rows": len(values), "approval": digest})
                google_json(session, "PUT", endpoint, params={"valueInputOption": "RAW"}, json={
                    "range": "Data!A1", "majorDimension": "ROWS",
                    "values": [columns, *[[value if value is not None else "" for value in row] for row in values]],
                })
                receipt["status"] = "published"
                write_json(receipt_path, receipt)
        write_json(local_receipt, receipt)
    warnings = ["The published selection represents a partial dataset."] if table["source_partial"] or table["capped"] else []
    ctx.log(receipt["url"])
    return {"status": "partial" if warnings else "succeeded", "warnings": warnings,
            "counts": {"rows": len(values), "columns": len(columns)}}
