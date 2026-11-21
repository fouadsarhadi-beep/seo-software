"""Publish completed artifacts by replacing a sibling temporary file."""
from contextlib import contextmanager
import json
import os
import shutil

from pathlib import Path
from tempfile import NamedTemporaryFile

from filelock import FileLock


@contextmanager
def atomic_text(path, encoding="utf-8"):
    path = Path(path)
    with NamedTemporaryFile(mode="w", encoding=encoding, newline="", dir=path.parent,
                            prefix=".writing-", delete=False) as stream:
        temporary = Path(stream.name)
        try:
            yield stream
            stream.flush()
            os.fsync(stream.fileno())
            stream.close()
            os.replace(temporary, path)
        finally:
            stream.close()
            temporary.unlink(missing_ok=True)


def write_json(path, value):
    with atomic_text(path) as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)


def write_text(path, value):
    with atomic_text(path) as stream:
        stream.write(value)


def publish_files(directory, destination, names, include_observations=False):
    """Export a snapshot under a directory lock and keep earlier crawl exports intact."""
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    with FileLock(str(destination / ".seo-export.lock"), timeout=10):
        if ((destination / "run.json").is_file() or
                (include_observations and (destination / "observations").exists())):
            destination = destination / directory.name
            destination.mkdir(exist_ok=True)
        sources = [directory / name for name in names]
        if include_observations:
            sources.extend((directory / "observations").glob("page-*.json"))
        for source in sources:
            output = destination / source.relative_to(directory)
            output.parent.mkdir(parents=True, exist_ok=True)
            with source.open(encoding="utf-8", newline="") as reader, atomic_text(output) as writer:
                shutil.copyfileobj(reader, writer)
    return destination
