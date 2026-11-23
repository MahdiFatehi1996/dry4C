from dataclasses import dataclass


@dataclass(frozen=True)
class Span:
    """Where one candidate function sits in a source file."""

    file: str
    start_line: int
    end_line: int


@dataclass(frozen=True)
class Duplicate:
    """One pair of functions whose normalized structure is similar enough to report."""

    score: float
    language: str
    left: Span
    right: Span
    left_nodes: int
    right_nodes: int


@dataclass(frozen=True)
class Entry:
    """A normalized function ready to compare."""

    language: str
    file: str
    start_line: int
    end_line: int
    nodes: int
    fingerprints: frozenset[str]
