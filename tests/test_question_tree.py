from seo_analysis.research.questions import (
    build_question_tree,
    capture_changes,
    capture_rows,
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


def test_two_captures_show_what_appeared_and_what_stopped_appearing():
    earlier = [
        {"row": 1, "parent": "insurance", "child": "how"},
        {"row": 2, "parent": "how", "child": "documents"},
        {"row": 3, "parent": "how", "child": "old question"},
    ]
    later = [
        {"row": 1, "parent": "insurance", "child": "how"},
        {"row": 2, "parent": "how", "child": "documents"},
        {"row": 3, "parent": "documents", "child": "new question"},
    ]
    changes = capture_changes(later, earlier)
    assert changes["added"] == [("documents", "new question")]
    assert changes["removed"] == [("how", "old question")]
    assert changes["persisted"] == [("how", "documents"), ("insurance", "how")]


def test_an_empty_seed_column_falls_back_to_parentless_roots():
    rows = [
        {"row": 1, "seed": "", "parent": "insurance", "child": "how"},
        {"row": 2, "seed": "", "parent": "how", "child": "documents"},
    ]
    assert question_seeds(rows) == ["insurance"]
    assert build_question_tree(rows, "insurance").children[0].question == "how"


def test_a_seed_that_is_only_a_topic_heading_shows_the_observed_roots():
    """The seed names the capture; it need not be a parent question itself."""
    rows = [
        {"row": 1, "seed": "insurance", "parent": "how", "child": "documents"},
        {"row": 2, "seed": "insurance", "parent": "how", "child": "cost"},
    ]
    tree = build_question_tree(rows, "insurance")
    assert tree.topic_only is True
    assert [child.question for child in tree.children] == ["how"]
    assert [child.question for child in tree.children[0].children] == ["cost", "documents"]


def test_edges_belong_to_their_own_capture_topic():
    rows = [
        {"row": 1, "seed": "insurance", "parent": "how", "child": "documents"},
        {"row": 2, "seed": "tax", "parent": "how", "child": "documents"},
    ]
    assert question_edges(capture_rows(rows, "insurance"))["how"] == [("documents", 1)]
    tree = build_question_tree(rows, "tax")
    assert [child.row for child in tree.children[0].children] == [2]


def test_updating_one_topic_leaves_another_untouched():
    before = [{"row": 1, "seed": "insurance", "parent": "how", "child": "documents"},
              {"row": 2, "seed": "tax", "parent": "how", "child": "filing"}]
    after = before + [{"row": 3, "seed": "tax", "parent": "how", "child": "deadline"}]
    assert capture_changes(after, before, "insurance") == {
        "added": [], "removed": [], "persisted": [("how", "documents")]}
    assert capture_changes(after, before, "tax")["added"] == [("how", "deadline")]


def test_more_than_fifty_siblings_are_reachable_by_raising_the_limit():
    rows = [{"row": index, "seed": "topic", "parent": "topic", "child": f"child {index:02d}"}
            for index in range(1, 61)]
    narrow = build_question_tree(rows, "topic", limit=50)
    assert len(narrow.children) == 50 and narrow.hidden == 10
    wide = build_question_tree(rows, "topic", limit=200)
    assert len(wide.children) == 60 and wide.hidden == 0


def test_a_deep_branch_stops_at_the_depth_bound():
    rows = [{"row": index, "seed": "topic", "parent": f"q{index}", "child": f"q{index + 1}"}
            for index in range(10)]
    rows.insert(0, {"row": 99, "seed": "topic", "parent": "topic", "child": "q0"})
    tree = build_question_tree(rows, "topic", max_depth=3)
    node, depth = tree, 0
    while node.children:
        node, depth = node.children[0], depth + 1
    assert depth == 3 and node.truncated


def test_outline_edges_lists_the_visible_branch():
    tree = build_question_tree(ROWS, "insurance", limit=10)
    pairs = {(parent, child) for parent, child, _ in outline_edges(tree)}
    assert ("insurance", "how") in pairs
    assert ("how", "documents") in pairs
    assert ("documents", "which documents") in pairs