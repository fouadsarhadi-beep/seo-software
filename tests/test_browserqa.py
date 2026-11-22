import json
from pathlib import Path
from shutil import which

from PIL import Image
import pytest

from seo_analysis.analysis.browserqa import build_file
from seo_analysis.cli import main


def test_browser_build_path_resolution_stays_within_selected_directory(tmp_path):
    root = tmp_path / "build"
    root.mkdir()
    docs = root / "docs"
    docs.mkdir()
    index = docs / "index.html"
    index.write_text("<h1>Docs</h1>", encoding="utf-8")
    (tmp_path / "outside.css").write_text("x {}", encoding="utf-8")
    assert build_file(root, "/docs/") == index
    assert build_file(root, "/%2e%2e/outside.css") is None
    assert build_file(root, "/.env") is None


def test_browser_qa_captures_local_build_and_blocks_external_fetch(site, tmp_path, capsys):
    pytest.importorskip("playwright.sync_api")
    chromium = which("chromium") or which("chromium-browser")
    if chromium is None:
        pytest.skip("System Chromium is unavailable.")

    build = tmp_path / "build"
    build.mkdir()
    (build / "index.html").write_text(
        f'<!doctype html><title>Fixture</title><link rel="stylesheet" href="/main.css">'
        f'<img src="{site.base}/outside"><main><h1>Fixture</h1></main>', encoding="utf-8",
    )
    (build / "main.css").write_text("main {color: blue}", encoding="utf-8")
    config = tmp_path / "config.toml"
    config.write_text('[paths]\ndata_dir="data"\n', encoding="utf-8")
    code = main(["--config-file", str(config), "browser-qa", str(build), "--chromium", chromium,
                 "--width", "400", "--height", "300", "--json"])
    result = json.loads(capsys.readouterr().out)
    assert code in (0, 3), result
    assert not site.hits
    assert result["data_egress"] == []
    directory = Path(result["out_dir"])
    report = json.loads((directory / "browser-qa.json").read_text(encoding="utf-8"))
    assert report["observations"]["local_responses"] == 2
    assert report["timings"]["load_ms"] >= 0
    with Image.open(directory / "screenshot.png") as screenshot:
        assert screenshot.size == (400, 300)
