from pathlib import Path

from dry4c.extract import entries_in_source
from dry4c.model import Entry
from dry4c.scan import _keep, find_duplicates, scan_files
from dry4c.shape import jaccard


def write_source(root: Path, name: str, text: str) -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def duplicates(root: Path, **options):
    files = sorted(path for path in root.rglob("*") if path.is_file())
    entries, warnings = scan_files(
        files,
        root,
        options.get("min_lines", 4),
        options.get("min_nodes", 20),
    )
    assert warnings == []
    return find_duplicates(entries, options.get("threshold", 0.82))


def forms(language: str, source: str, file: str) -> list[Entry]:
    entries, warning = entries_in_source(language, source, file, file)
    assert warning is None
    return entries


def spans(language: str, source: str, file: str) -> list[tuple[int, int]]:
    return [(entry.start_line, entry.end_line) for entry in forms(language, source, file)]


def test_renamed_functions_match(tmp_path):
    write_source(
        tmp_path,
        "left.c",
        "int alpha(int *values, int count) {\n"
        "    int total = 0;\n"
        "    for (int i = 0; i < count; i++) {\n"
        "        if (values[i] > 0) {\n"
        "            total += values[i];\n"
        "        } else {\n"
        "            total -= 1;\n"
        "        }\n"
        "    }\n"
        "    return total;\n"
        "}\n",
    )
    write_source(
        tmp_path,
        "right.c",
        "int beta(int *items, int size) {\n"
        "    int sum = 0;\n"
        "    for (int j = 0; j < size; j++) {\n"
        "        if (items[j] > 0) {\n"
        "            sum += items[j];\n"
        "        } else {\n"
        "            sum -= 2;\n"
        "        }\n"
        "    }\n"
        "    return sum;\n"
        "}\n",
    )
    found = duplicates(tmp_path, threshold=1.0, min_lines=1, min_nodes=1)
    assert len(found) == 1
    assert found[0].score == 1.0
    assert found[0].language == "c"
    assert (found[0].left.file, found[0].left.start_line, found[0].left.end_line) == (
        "left.c",
        1,
        11,
    )
    assert (found[0].right.file, found[0].right.start_line, found[0].right.end_line) == (
        "right.c",
        1,
        11,
    )


def test_comments_strings_and_literals_normalize_away(tmp_path):
    body = (
        "int alpha(void) {\n"
        "    char *name = \"left\";\n"
        "    /* a comment */\n"
        "    return name[0] + 1;\n"
        "}\n"
    )
    other = (
        "int beta(void) {\n"
        "    char *label = \"right\";\n"
        "    // another comment\n"
        "    return label[1] + 2;\n"
        "}\n"
    )
    write_source(tmp_path, "left.c", body)
    write_source(tmp_path, "right.c", other)
    found = duplicates(tmp_path, threshold=1.0, min_lines=1, min_nodes=1)
    assert len(found) == 1
    assert found[0].score == 1.0


def test_a_different_callee_is_not_the_same_structure(tmp_path):
    write_source(
        tmp_path,
        "left.c",
        "int alpha(int *xs) {\n"
        "    int total = 0;\n"
        "    total = first(xs);\n"
        "    return total + second(xs);\n"
        "}\n",
    )
    write_source(
        tmp_path,
        "right.c",
        "int beta(int *items) {\n"
        "    int sum = 0;\n"
        "    sum = first(items);\n"
        "    return sum + other(items);\n"
        "}\n",
    )
    assert duplicates(tmp_path, threshold=1.0, min_lines=1, min_nodes=1) == []


def test_a_different_operator_is_not_the_same_structure(tmp_path):
    write_source(
        tmp_path,
        "left.c",
        "int alpha(int left, int right) {\n"
        "    int total = left + right;\n"
        "    return total;\n"
        "}\n",
    )
    write_source(
        tmp_path,
        "right.c",
        "int beta(int first, int second) {\n"
        "    int sum = first - second;\n"
        "    return sum;\n"
        "}\n",
    )
    assert duplicates(tmp_path, threshold=1.0, min_lines=1, min_nodes=1) == []


def test_field_names_erase_but_called_member_names_stay():
    left = (
        "int alpha(struct box *a) {\n"
        "    int total = a->width + a->height;\n"
        "    return total;\n"
        "}\n"
    )
    right = (
        "int beta(struct panel *p) {\n"
        "    int sum = p->depth + p->length;\n"
        "    return sum;\n"
        "}\n"
    )
    assert duplicates_for_source(left, right) == 1.0

    called_left = (
        "int alpha(struct box *a) {\n"
        "    int total = a->width();\n"
        "    return total;\n"
        "}\n"
    )
    called_right = (
        "int beta(struct panel *p) {\n"
        "    int sum = p->depth();\n"
        "    return sum;\n"
        "}\n"
    )
    assert duplicates_for_source(called_left, called_right) < 1.0


def duplicates_for_source(left: str, right: str) -> float:
    left_entry = forms("c", left, "left.c")[0]
    right_entry = forms("c", right, "right.c")[0]
    return jaccard(left_entry.fingerprints, right_entry.fingerprints)


def test_pointer_and_cast_shapes_are_structural():
    left = (
        "int alpha(int *values) {\n"
        "    int total = (int)values[0];\n"
        "    return total;\n"
        "}\n"
    )
    right = (
        "int beta(long *items) {\n"
        "    int sum = (long)items[1];\n"
        "    return sum;\n"
        "}\n"
    )
    assert duplicates_for_source(left, right) == 1.0


def test_a_pointer_access_differs_from_a_value_access():
    left = (
        "int alpha(struct box *a) {\n"
        "    int total = a->width;\n"
        "    return total;\n"
        "}\n"
    )
    right = (
        "int beta(struct box *p) {\n"
        "    int sum = p.width;\n"
        "    return sum;\n"
        "}\n"
    )
    assert duplicates_for_source(left, right) < 1.0


def test_switch_loops_and_calls_keep_their_shape():
    left = (
        "int alpha(int *xs, int n) {\n"
        "    int total = 0;\n"
        "    for (int i = 0; i < n; i++) {\n"
        "        switch (xs[i]) {\n"
        "        case 0:\n"
        "            total += parse(xs[i]);\n"
        "            break;\n"
        "        default:\n"
        "            total -= 1;\n"
        "        }\n"
        "    }\n"
        "    return total;\n"
        "}\n"
    )
    right = (
        "int beta(int *items, int size) {\n"
        "    int sum = 1;\n"
        "    while (sum < size) {\n"
        "        switch (items[sum]) {\n"
        "        case 7:\n"
        "            sum += parse(items[sum]);\n"
        "            break;\n"
        "        default:\n"
        "            sum -= 2;\n"
        "        }\n"
        "    }\n"
        "    return sum;\n"
        "}\n"
    )
    assert duplicates_for_source(left, right) < 1.0


def test_a_nested_function_stays_inside_its_enclosing_function():
    source = (
        "int outer(int *xs) {\n"
        "    int helper(int value) {\n"
        "        return value + 1;\n"
        "    }\n"
        "    return helper(xs[0]);\n"
        "}\n"
    )
    assert spans("c", source, "nested.c") == [(1, 6)]


def test_a_declaration_without_a_body_is_not_a_candidate():
    source = "int declared(int value);\nint defined(int value) {\n    return value;\n}\n"
    assert spans("c", source, "decl.h") == [(2, 4)]


def test_a_header_function_is_a_candidate():
    source = (
        "static inline int floor_value(int value, int low) {\n"
        "    if (value < low) {\n"
        "        return low;\n"
        "    }\n"
        "    return value;\n"
        "}\n"
    )
    assert spans("c", source, "numbers.h") == [(1, 6)]


def test_header_static_functions_are_compared(tmp_path):
    write_source(
        tmp_path,
        "include/math.h",
        "static inline int floor_value(int value, int low) {\n"
        "    if (value < low) {\n"
        "        return low;\n"
        "    }\n"
        "    return value;\n"
        "}\n"
        "\n"
        "static inline int cap_value(int amount, int limit) {\n"
        "    if (amount < limit) {\n"
        "        return limit;\n"
        "    }\n"
        "    return amount;\n"
        "}\n",
    )
    found = duplicates(tmp_path, threshold=1.0, min_lines=1, min_nodes=1)
    assert len(found) == 1
    assert found[0].score == 1.0
    assert found[0].left.file == found[0].right.file == "include/math.h"
    assert (found[0].left.start_line, found[0].left.end_line) == (1, 6)
    assert (found[0].right.start_line, found[0].right.end_line) == (8, 13)


def test_a_macro_is_not_a_candidate():
    source = (
        "#define MAX(a, b) ((a) > (b) ? (a) : (b))\n"
        "int alpha(void) {\n"
        "    return 1;\n"
        "}\n"
    )
    assert spans("c", source, "macro.c") == [(2, 4)]


def test_a_parenthesized_callee_matches_the_bare_call():
    left = "int alpha(int x) {\n    return (parse)(x);\n}\n"
    right = "int beta(int y) {\n    return parse(y);\n}\n"
    assert duplicates_for_source(left, right) == 1.0


def test_block_comments_do_not_change_the_shape():
    left = "int alpha(void) {\n    return 1;\n}\n"
    right = "int beta(void) {\n    /* explain */\n    return 2;\n}\n"
    assert duplicates_for_source(left, right) == 1.0


def test_a_comment_inside_an_expression_does_not_change_the_shape():
    left = "int alpha(void) {\n    return (1);\n}\n"
    right = "int beta(void) {\n    return (/* note */ 2);\n}\n"
    assert duplicates_for_source(left, right) == 1.0


def test_preprocessor_blocks_normalize_as_written():
    left = (
        "int alpha(int *xs) {\n"
        "#ifdef TRACE\n"
        "    xs[0] = 1;\n"
        "#else\n"
        "    xs[1] = 2;\n"
        "#endif\n"
        "    return xs[0];\n"
        "}\n"
    )
    right = (
        "int beta(int *items) {\n"
        "#ifdef DEBUG\n"
        "    items[0] = 9;\n"
        "#else\n"
        "    items[1] = 8;\n"
        "#endif\n"
        "    return items[0];\n"
        "}\n"
    )
    assert duplicates_for_source(left, right) == 1.0


def test_end_line_uses_the_closing_brace():
    source = "int alpha(void) {\n    return 1;\n}\n\nint beta(void) {\n    return 2;\n}\n"
    assert spans("c", source, "two.c") == [(1, 3), (5, 7)]


def entry(file: str, start: int, end: int, names: set[str], nodes: int = 20) -> Entry:
    return Entry("c", file, start, end, nodes, frozenset(names))


def test_the_same_span_is_not_a_pair():
    entries = [
        entry("a.c", 1, 4, {"x", "y"}),
        entry("a.c", 1, 4, {"x", "y"}),
        entry("a.c", 6, 9, {"x", "y"}),
    ]
    found = find_duplicates(entries, 1.0)
    assert [(item.left.start_line, item.right.start_line) for item in found] == [(1, 6), (1, 6)]


def test_a_score_equal_to_the_threshold_is_kept():
    entries = [entry("a.c", 1, 4, {"x", "y"}), entry("b.c", 1, 4, {"x", "z"})]
    assert len(find_duplicates(entries, 1 / 3)) == 1
    assert find_duplicates(entries, 0.34) == []


def test_the_higher_score_is_reported_first():
    entries = [
        entry("a.c", 1, 4, {"x", "y", "z"}),
        entry("b.c", 1, 4, {"x", "y", "z"}),
        entry("c.c", 1, 4, {"x", "y"}),
    ]
    found = find_duplicates(entries, 0.5)
    assert found[0].score == 1.0
    assert [item.score for item in found] == sorted(
        [item.score for item in found], reverse=True
    )


def test_keep_uses_the_line_and_node_minimums():
    assert _keep(entry("a.c", 1, 4, {"x"}, nodes=20), 4, 20) is True
    assert _keep(entry("a.c", 1, 3, {"x"}, nodes=20), 4, 20) is False
    assert _keep(entry("a.c", 1, 4, {"x"}, nodes=19), 4, 20) is False
