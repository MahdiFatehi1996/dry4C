"""Pick the C function units each file contributes.

A C function unit is a `function_definition` with a body. That includes
`static` and `inline` definitions in headers. A function nested inside another
function stays part of the enclosing candidate, so only outermost definitions
are entries.
"""

from __future__ import annotations

from dry4c.astnorm import normalize
from dry4c.model import Entry
from dry4c.shape import fingerprints, node_count
from dry4c.treesitter import child_of_type, descendants, end_line, parse, start_line


def _inside(node, types: set[str]) -> bool:
    current = node.parent
    while current is not None:
        if current.type in types:
            return True
        current = current.parent
    return False


def _c_nodes(data: bytes, root) -> list:
    found = []
    for node in descendants(root):
        if node.type != "function_definition":
            continue
        if child_of_type(node, "compound_statement") is None:
            continue
        if _inside(node, {"function_definition"}):
            continue
        found.append(node)
    return found


_PICKERS = {
    "c": ("c", _c_nodes),
}


def entries_in_source(
    language: str, source: str, path: str, file: str
) -> tuple[list[Entry], str | None]:
    if language not in _PICKERS:
        return [], None
    grammar, pick = _PICKERS[language]
    data, tree = parse(source, grammar)
    entries = []
    for node in pick(data, tree.root_node):
        normalized = normalize(node, data)
        if normalized is None:
            continue
        entries.append(
            Entry(
                language=language,
                file=file,
                start_line=start_line(node),
                end_line=end_line(node),
                nodes=node_count(normalized),
                fingerprints=fingerprints(normalized),
            )
        )
    return entries, None
