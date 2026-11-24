"""Receive selected exports from the loopback workbench."""

from contextlib import asynccontextmanager
from dataclasses import replace
from pathlib import Path, PureWindowsPath
from tempfile import TemporaryDirectory

from fastapi import HTTPException
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartException, MultiPartParser

from seo_analysis.app.runner import ToolRunner
from seo_analysis.core import tools


@asynccontextmanager
async def export_form(request):
    if request.headers.get("content-type", "").split(";", 1)[0].lower() != "multipart/form-data":
        raise HTTPException(415, "Select a file to import.")

    async def bounded_stream():
        size = 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > 20_100_000:
                raise MultiPartException("Select an export of 20 MB or less.")
            yield chunk

    try:
        fields = await MultiPartParser(request.headers, bounded_stream(), max_files=1, max_fields=12,
                                       max_part_size=8192).parse()
    except MultiPartException as exc:
        raise HTTPException(400, exc.message) from exc
    try:
        yield fields
    finally:
        await fields.close()


def import_upload(workspace, upload, request, *, project=None):
    if not isinstance(upload, UploadFile) or not upload.filename:
        raise ValueError("Select a CSV, TSV or Excel export.")
    filename = PureWindowsPath(upload.filename).name
    suffix = Path(filename).suffix.lower()
    if suffix not in {".csv", ".tsv", ".xlsx"}:
        raise ValueError("Select a CSV, TSV or Excel export.")
    if upload.size is None or upload.size > 20_000_000:
        raise ValueError("Select an export of 20 MB or less.")
    with TemporaryDirectory(prefix="seo-export-") as directory:
        path = Path(directory) / ("input" + suffix)
        with path.open("wb") as out:
            while chunk := upload.file.read(64 * 1024):
                out.write(chunk)
        return ToolRunner(workspace).run(tools.IMPORT, replace(request, file=str(path), source_filename=filename[:255]),
                                         project=project, log=lambda _: None)
