"""Build a question outline from imported parent-child relationships."""
from dataclasses import dataclass, field


@dataclass
class Node:
    question: str
    row: int
    children: list = field(default_factory=list)
    cycle: bool = False
    hidden: int = 0
    topic_only: bool = False
    truncated: bool = False


def capture_rows(rows, seed):
    """Rows belonging to one capture topic. A file without a seed column is a single capture."""
    tagged = [row for row in rows if str(row.get("seed") or "").strip()]
    if not tagged:
        return list(rows)
    return [row for row in rows if str(row.get("seed") or "").strip() == seed]


def question_edges(rows):
    """Group child questions under their parent, with the source row of each edge."""
    edges = {}
    for row in rows:
        parent = str(row.get("parent") or "").strip()
        child = str(row.get("child") or "").strip()
        if not parent or not child:
            continue
        edges.setdefault(parent, []).append((child, int(row.get("row") or 0)))
    for children in edges.values():
        children.sort(key=lambda item: (item[0], item[1]))
    return edges


def question_seeds(rows):
    """Seeds if the source names them, otherwise the roots that no edge points at."""
    seeds = {str(row.get("seed") or "").strip() for row in rows}
    seeds.discard("")
    if seeds:
        return sorted(seeds)
    edges = question_edges(rows)
    parents = set(edges)
    children = {child for items in edges.values() for child, _ in items}
    return sorted(parents - children) or sorted(parents)


def _root_row(rows, seed):
    for row in rows:
        if str(row.get("seed") or "").strip() == seed or str(row.get("parent") or "").strip() == seed:
            return int(row.get("row") or 0)
    return 0


def build_question_tree(rows, seed, *, limit=50, max_nodes=200, max_depth=6):
    """Expand one capture topic into an outline.

    The seed names the capture, so it need not be a parent question itself: when no row
    supplies an edge from it, the questions observed under that capture are attached as
    its children and the node is marked ``topic_only``. A question that reappears on its
    own path is marked as a cycle instead of expanding again. Children beyond ``limit``
    are counted in ``hidden``; the traversal stops at ``max_nodes`` and ``max_depth``.
    """
    capture = capture_rows(rows, seed)
    edges = question_edges(capture)
    children = {child for items in edges.values() for child, _ in items}
    roots = [parent for parent in edges if parent not in children]
    limit = max(1, int(limit))
    max_nodes = max(2, int(max_nodes))
    max_depth = max(1, int(max_depth))
    budget = {"nodes": 0}

    def walk(question, path, row, depth):
        node = Node(question=question, row=row)
        budget["nodes"] += 1
        if question in path:
            node.cycle = True
            return node
        items = edges.get(question, [])
        node.hidden = max(0, len(items) - limit)
        if depth >= max_depth and items:
            node.truncated = True
            node.hidden = len(items)
            return node
        for child, child_row in items[:limit]:
            if budget["nodes"] >= max_nodes:
                node.truncated = True
                node.hidden += len(items) - len(node.children)
                break
            node.children.append(walk(child, path | {question}, child_row, depth + 1))
        return node

    root = walk(seed, frozenset(), _root_row(capture, seed), 0)
    if not root.children:
        # The seed is a capture topic rather than a supplied parent question.
        observed = [walk(item, frozenset({seed}), _root_row(capture, item), 1) for item in roots[:limit]]
        if observed:
            root.topic_only = True
            root.hidden = max(0, len(roots) - limit)
            root.children = observed
    return root


def outline_edges(node):
    """Every visible parent-child edge, for an export of the expanded branch."""
    seen = []
    for child in node.children:
        seen.append((node.question, child.question, child.row))
        seen.extend(outline_edges(child))
    return seen


def capture_changes(rows, previous_rows, seed=""):
    """Question edges that appeared or disappeared between two captures of the same topic."""
    current = {(parent, child) for parent, items in question_edges(capture_rows(rows, seed)).items()
               for child, _ in items}
    previous = {(parent, child) for parent, items in question_edges(capture_rows(previous_rows, seed)).items()
                for child, _ in items}
    return {
        "added": sorted(current - previous),
        "removed": sorted(previous - current),
        "persisted": sorted(current & previous),
    }