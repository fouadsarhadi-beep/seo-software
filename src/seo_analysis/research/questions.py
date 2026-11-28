"""Build a question outline from imported parent-child relationships."""
from dataclasses import dataclass, field


@dataclass
class Node:
    question: str
    row: int
    children: list = field(default_factory=list)
    cycle: bool = False
    hidden: int = 0


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


def build_question_tree(rows, seed, *, limit=10):
    """Expand one seed into an outline.

    A question that reappears on its own path is marked as a cycle instead of expanding
    again, so a poisoned export cannot recurse forever. Children beyond ``limit`` are
    counted in ``hidden`` so the page can offer a deliberate "show more".
    """
    edges = question_edges(rows)
    limit = max(1, int(limit))
    root_row = _root_row(rows, seed)

    def walk(question, path, row):
        node = Node(question=question, row=row)
        if question in path:
            node.cycle = True
            return node
        items = edges.get(question, [])
        node.hidden = max(0, len(items) - limit)
        for child, child_row in items[:limit]:
            node.children.append(walk(child, path | {question}, child_row))
        return node

    return walk(seed, frozenset(), root_row)


def outline_edges(node):
    """Every visible parent-child edge, for an export of the expanded branch."""
    seen = []
    for child in node.children:
        seen.append((node.question, child.question, child.row))
        seen.extend(outline_edges(child))
    return seen


def capture_changes(rows, previous_rows):
    """Question edges that appeared or disappeared between two captures of the same seed."""
    current = {(parent, child) for parent, items in question_edges(rows).items() for child, _ in items}
    previous = {(parent, child) for parent, items in question_edges(previous_rows).items() for child, _ in items}
    return {
        "added": sorted(current - previous),
        "removed": sorted(previous - current),
        "persisted": sorted(current & previous),
    }