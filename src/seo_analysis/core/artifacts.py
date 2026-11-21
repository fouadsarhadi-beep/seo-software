"""Publish completed artifacts by replacing a sibling temporary file."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile


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
