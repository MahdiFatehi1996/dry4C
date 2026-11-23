"""Normalize a tree-sitter C tree.

The name in call position stays: `filter`, `malloc`, a struct member function
reached through `->`, an operator. Local names, parameter names, field names,
type names, and literal values become generic markers. Two functions that call
the same operations in the same shape therefore share a fingerprint set even
when their locals, types, and literals differ.
"""

from __future__ import annotations

from dry4c.shape import K
from dry4c.treesitter import node_text

_SKIP = {
    "comment",
}

# Names that carry no structure. `primitive_type` and `sized_type_specifier`
# are type names spelled as nodes, and `statement_identifier` is a label.
_IDENTIFIERS = {
    "identifier",
    "type_identifier",
    "field_identifier",
    "primitive_type",
    "sized_type_specifier",
    "statement_identifier",
}

_LITERALS = {
    "string_literal",
    "char_literal",
    "number_literal",
    "true",
    "false",
    "null",
}

# C operators are anonymous tokens. Keeping them separates `a + b` from
# `a - b`, and `p.x` from `p->x`.
_OPERATORS = {
    "+",
    "-",
    "*",
    "/",
    "%",
    "==",
    "!=",
    "<",
    ">",
    "<=",
    ">=",
    "&&",
    "||",
    "&",
    "|",
    "^",
    "<<",
    ">>",
    "+=",
    "-=",
    "*=",
    "/=",
    "%=",
    "&=",
    "|=",
    "^=",
    "<<=",
    ">>=",
    "!",
    "~",
    "++",
    "--",
    "=",
    "->",
    ".",
    "?",
    ":",
}

_CALLS = {
    "call_expression",
}

_ATTRIBUTES = {
    "field_expression",
}

_ACCESS_OPERATORS = {"->", "."}

_ARG_LISTS = {"argument_list"}

_DATA: bytes = b""


def normalize(node, data: bytes):
    """Normalized tree for `node`, or None when the node is only punctuation."""

    global _DATA
    _DATA = data
    return _normalize(node)


def _text(node) -> str:
    return node_text(_DATA, node)


_PENDING = object()


def _is_literal(node) -> bool:
    return node.type in _LITERALS


def _named(node) -> list:
    """Named children without comments, which carry no structure."""

    return [child for child in node.named_children if child.type not in _SKIP]


def _named_before_args(node):
    incoming = []
    for child in _named(node):
        if child.type in _ARG_LISTS:
            return incoming, child
        incoming.append(child)
    return incoming, None


def _callee_leaf(node):
    if node.type in _IDENTIFIERS:
        return [K("symbol"), _text(node)]
    return _PENDING


def _named_leaf(node, head: bool):
    if node.type in _IDENTIFIERS:
        if head:
            return [K("symbol"), _text(node)]
        return K("symbol")
    if _is_literal(node):
        return K("literal")
    return _PENDING


def _try_leaf(node, mode: str, head: bool):
    if mode == "callee":
        return _callee_leaf(node)
    if node.type in _SKIP:
        return None
    if node.type in _OPERATORS:
        return [K("symbol"), node.type]
    if not node.is_named:
        return None
    return _named_leaf(node, head)


def _call_jobs(node):
    incoming, args = _named_before_args(node)
    jobs = []
    if incoming:
        *receivers, callee = incoming
        jobs.extend((child, "norm", False) for child in receivers)
        jobs.append((callee, "callee", False))
    if args is not None:
        jobs.append((args, "norm", False))
    return jobs


def _attr_jobs(node, head: bool):
    named = _named(node)
    if not named:
        return []
    *objects, name = named
    jobs = [(obj, "norm", False) for obj in objects]
    if name.type in _IDENTIFIERS:
        return jobs
    if head:
        jobs.append((name, "callee", False))
    else:
        jobs.append((name, "norm", False))
    return jobs


def _callee_jobs(node):
    if node.type in _ATTRIBUTES:
        return _attr_jobs(node, True)
    return [(node, "norm", True)]


def _jobs(node, mode: str, head: bool):
    if mode == "callee":
        return _callee_jobs(node)
    if node.type == "parenthesized_expression":
        named = _named(node)
        if len(named) == 1:
            return [(named[0], "norm", head)]
    if node.type in _CALLS:
        return _call_jobs(node)
    if node.type in _ATTRIBUTES:
        return _attr_jobs(node, head)
    return [(child, "norm", False) for child in node.children]


def _name_value(name, head: bool, cache):
    """Keep a member's spelling when it is the thing being called."""

    if name.type in _IDENTIFIERS:
        if head:
            return [K("symbol"), _text(name)]
        return K("symbol")
    if head:
        return cache[(id(name), "callee", False)]
    return cache[(id(name), "norm", False)]


def _assemble_call(node, cache):
    incoming, args = _named_before_args(node)
    out = [K(node.type)]
    if incoming:
        *receivers, callee = incoming
        for child in receivers:
            norm = cache[(id(child), "norm", False)]
            if norm is not None:
                out.append(norm)
        out.append(cache[(id(callee), "callee", False)])
    if args is not None:
        norm = cache[(id(args), "norm", False)]
        if norm is not None:
            out.append(norm)
    return out


def _assemble_attr(node, head: bool, cache):
    named = _named(node)
    if not named:
        return [K(node.type)]
    *objects, name = named
    parts = [K(node.type)]
    for obj in objects:
        norm = cache[(id(obj), "norm", False)]
        if norm is not None:
            parts.append(norm)
    for child in node.children:
        if child.type in _ACCESS_OPERATORS:
            parts.append([K("symbol"), child.type])
            break
    nested = _name_value(name, head, cache)
    if nested is not None:
        parts.append(nested)
    return parts


def _callee_value(node, cache):
    if node.type in _ATTRIBUTES:
        return _assemble_attr(node, True, cache)
    return cache[(id(node), "norm", True)]


def _assemble_children(node, cache):
    children = []
    for child in node.children:
        norm = cache[(id(child), "norm", False)]
        if norm is not None:
            children.append(norm)
    return [K(node.type), *children]


def _assemble(node, mode: str, head: bool, cache):
    if mode == "callee":
        return _callee_value(node, cache)
    if node.type == "parenthesized_expression":
        named = _named(node)
        if len(named) == 1:
            return cache[(id(named[0]), "norm", head)]
    if node.type in _CALLS:
        return _assemble_call(node, cache)
    if node.type in _ATTRIBUTES:
        return _assemble_attr(node, head, cache)
    return _assemble_children(node, cache)


def _normalize(node, head: bool = False):
    # Post-order. A 1,200-deep expression must not raise RecursionError.
    cache = {}
    stack = [(node, "norm", head, False)]
    while stack:
        current, mode, is_head, expanded = stack.pop()
        key = (id(current), mode, is_head)
        if not expanded:
            if key in cache:
                continue
            leaf = _try_leaf(current, mode, is_head)
            if leaf is not _PENDING:
                cache[key] = leaf
                continue
            stack.append((current, mode, is_head, True))
            for child, child_mode, child_head in reversed(_jobs(current, mode, is_head)):
                stack.append((child, child_mode, child_head, False))
            continue
        cache[key] = _assemble(current, mode, is_head, cache)
    return cache[(id(node), "norm", head)]
