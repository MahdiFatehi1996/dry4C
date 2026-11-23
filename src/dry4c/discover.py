"""Find C source files.

The skipped directories match the upstream tools. A `.c` or `.h` file is C;
test files follow the C conventions `*_test.c` and `test_*.c`.
"""

import os
from pathlib import Path

EXTENSIONS = {
    ".c": "c",
    ".h": "c",
}

SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".idea",
    ".venv",
    "venv",
    "node_modules",
    "vendor",
    "target",
    "dist",
    "build",
    "out",
    "coverage",
    ".metrics",
    "testdata",
    "__pycache__",
}

TEST_DIRS = {"test", "tests", "spec", "specs", "__tests__"}


def language_of(path: str | Path) -> str | None:
    return EXTENSIONS.get(Path(path).suffix)


def is_test_file(path: str | Path, root: str | Path | None = None) -> bool:
    """Whether `path` is a test file below `root`.

    With a root, only segments below it matter: a project checked out under a
    `tests/` directory is still production code when that project is the walk
    root. Without a root, every path segment is considered.
    """

    file_path = Path(path)
    name = file_path.name
    if name.endswith("_test.c"):
        return True
    if name.startswith("test_") and name.endswith(".c"):
        return True
    if root is None:
        parts = file_path.parts
    else:
        root_path = Path(root)
        try:
            parts = file_path.relative_to(root_path).parts
        except ValueError:
            try:
                parts = file_path.resolve().relative_to(root_path.resolve()).parts
            except ValueError:
                parts = file_path.parts
    return any(part in TEST_DIRS for part in parts)


def _skipped_dir(name: str) -> bool:
    return name in SKIP_DIRS or name in TEST_DIRS


def _walk(root: Path) -> list[Path]:
    if not root.exists():
        return []
    if root.is_file():
        return [root]
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if not _skipped_dir(name)]
        for name in filenames:
            path = Path(dirpath) / name
            if language_of(path) is None or is_test_file(path, root):
                continue
            found.append(path)
    return found


def iter_source_files(roots: list[Path]) -> list[Path]:
    files: set[Path] = set()
    for root in roots:
        for path in _walk(root):
            files.add(path.resolve())
    return sorted(files, key=lambda path: path.as_posix())
