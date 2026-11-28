import json
from pathlib import Path

from seo_analysis.cli import main


def _prefix(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text('[paths]\ndata_dir="data"\n', encoding="utf-8")
    return ["--config-file", str(config)]


def test_question_import_keeps_relationships_and_collapses_duplicate_edges(tmp_path, capsys):
    export = tmp_path / "questions.csv"
    export.write_text(
        "seed,parent,child\n"
        "بیمه,چگونه بیمه بگیریم,چه مدارکی لازم است\n"
        "بیمه,چگونه بیمه بگیریم,چه مدارکی لازم است\n"
        "بیمه,چطور بیمه بگیریم,چه مدارکی لازم است\n"
        "بیمه,چگونه بیمه بگیریم,\n"
        ",,ناقص\n",
        encoding="utf-8")
    assert main([*_prefix(tmp_path), "import-data", str(export), "--kind", "questions",
                 "--provider", "AlsoAsked", "--observed", "2026-11-20", "--locale", "fa-IR", "--json"]) == 3
    run = json.loads(capsys.readouterr().out)
    dataset = json.loads((Path(run["out_dir"]) / "dataset.json").read_text(encoding="utf-8"))
    rows = dataset["rows"]
    # The duplicate edge collapses; the same child under a second parent is a second relationship.
    assert len(rows) == 2
    assert rows[0]["child"] == "چه مدارکی لازم است" and rows[1]["child"] == "چه مدارکی لازم است"
    assert {row["parent"] for row in rows} == {"چگونه بیمه بگیریم", "چطور بیمه بگیریم"}
    assert rows[0]["seed"] == "بیمه"
    assert run["counts"]["duplicates"] == 1 and run["counts"]["skipped"] == 2
    assert dataset["source"]["kind"] == "questions"
    assert dataset["source"]["locale"] == "fa-IR" and dataset["source"]["provider"] == "AlsoAsked"
    assert any("duplicate relationship" in warning for warning in run["warnings"])
    assert (Path(run["out_dir"]) / "normalized.csv").is_file()


def test_exported_branch_can_be_reimported_and_keeps_parent_relationships(tmp_path, capsys):
    from seo_analysis.research.questions import build_question_tree, outline_edges

    rows = [
        {"row": 1, "seed": "insurance", "parent": "insurance", "child": "how"},
        {"row": 2, "seed": "insurance", "parent": "how", "child": "documents"},
        {"row": 3, "seed": "insurance", "parent": "how", "child": "cost"},
        {"row": 4, "seed": "insurance", "parent": "cost", "child": "documents"},
        {"row": 5, "seed": "insurance", "parent": "documents", "child": "how"},
    ]
    tree = build_question_tree(rows, "insurance", limit=10)
    export = tmp_path / "branch.csv"
    lines = ["parent,child,source_row"] + [f"{parent},{child},{row}" for parent, child, row in outline_edges(tree)]
    export.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert main([*_prefix(tmp_path), "import-data", str(export), "--kind", "questions",
                 "--provider", "Branch export", "--observed", "2026-11-21", "--json"]) in (0, 3)
    run = json.loads(capsys.readouterr().out)
    dataset = json.loads((Path(run["out_dir"]) / "dataset.json").read_text(encoding="utf-8"))
    recovered = {(row["parent"], row["child"]) for row in dataset["rows"]}
    assert {("insurance", "how"), ("how", "documents"), ("cost", "documents")} <= recovered


def test_question_import_rejects_a_file_without_relationship_columns(tmp_path, capsys):
    export = tmp_path / "flat.csv"
    export.write_text("query,volume\nبیمه,120\n", encoding="utf-8")
    assert main([*_prefix(tmp_path), "import-data", str(export), "--kind", "questions",
                 "--provider", "AlsoAsked", "--observed", "2026-11-20", "--json"]) == 2
    run = json.loads(capsys.readouterr().out)
    assert any("parent" in warning and "child" in warning for warning in run["warnings"])
    assert not (Path(run["out_dir"]) / "dataset.json").exists()