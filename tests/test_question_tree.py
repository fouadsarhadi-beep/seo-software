from seo_analysis.research.questions import (
    build_question_tree,
    outline_edges,
    question_edges,
    question_seeds,
)

ROWS = [
    {"row": 1, "seed": "insurance", "parent": "insurance", "child": "how"},
    {"row": 2, "seed": "insurance", "parent": "how", "child": "documents"},
    {"row": 3, "seed": "insurance", "parent": "how", "child": "cost"},
    {"row": 4, "seed": "insurance", "parent": "documents", "child": "which documents"},
    {"row": 5, "seed": "insurance", "parent": "which documents", "child": "documents"},
    {"row": 6, "seed": "insurance", "parent": "cost", "child": "documents"},
]


def _nodes(node):
    yield node
    for child in node.children:
        yield from _nodes(child)


def test_tree_expands_one_seed_and_flags_a_cycle_on_its_own_path():
    tree = build_question_tree(ROWS, "insurance", limit=10)
    assert tree.question == "insurance" and tree.row == 1
    questions = [node.question for node in _nodes(tree)]
    # Two real branches (under how, under cost) plus the repeat each branch hits.
    assert questions.count("documents") == 4
    cyclic = [node for node in _nodes(tree) if node.cycle]
    assert len(cyclic) == 2 and {node.question for node in cyclic} == {"documents"}
    assert all(not node.children for node in cyclic)


def test_a_child_under_two_parents_appears_under_both():
    tree = build_question_tree(ROWS, "insurance", limit=10)
    how = next(node for node in _nodes(tree) if node.question == "how")
    cost = next(node for node in _nodes(tree) if node.question == "cost")
    assert "documents" in [child.question for child in how.children]
    assert "documents" in [child.question for child in cost.children]


def test_children_beyond_the_limit_are_counted_not_dropped():
    tree = build_question_tree(ROWS, "insurance", limit=1)
    how = next(node for node in _nodes(tree) if node.question == "how")
    assert len(how.children) == 1 and how.hidden == 1


def test_seeds_come_from_the_seed_column_or_from_parentless_roots():
    assert question_seeds(ROWS) == ["insurance"]
    roots_only = [{key: value for key, value in row.items() if key != "seed"} for row in ROWS]
    assert question_seeds(roots_only) == ["insurance"]


def test_edges_group_by_parent_and_ignore_incomplete_rows():
    edges = question_edges(ROWS + [{"row": 7, "parent": "how", "child": ""}])
    assert [child for child, _ in edges["how"]] == ["cost", "documents"]


def test_outline_edges_lists_the_visible_branch():
    tree = build_question_tree(ROWS, "insurance", limit=10)
    pairs = {(parent, child) for parent, child, _ in outline_edges(tree)}
    assert ("insurance", "how") in pairs
    assert ("how", "documents") in pairs
    assert ("documents", "which documents") in pairs