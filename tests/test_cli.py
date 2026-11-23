import subprocess
from pathlib import Path

import pytest

from dry4c.cli import (
    GitStatusError,
    _changed_files,
    _count,
    _tracked_source,
    main,
    parse_args,
    run,
    select_files,
)
from dry4c.discover import is_test_file, iter_source_files, language_of


LEFT = (
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
    "}\n"
)

RIGHT = (
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
    "}\n"
)

OTHER = (
    "int gamma(int *rows, int length) {\n"
    "    int result = 0;\n"
    "    while (result < length) {\n"
    "        result += parse(rows[result]);\n"
    "    }\n"
    "    return result;\n"
    "}\n"
)

NEAR = (
    "int beta(int *items, int size) {\n"
    "    int sum = 0;\n"
    "    for (int j = 0; j < size; j++) {\n"
    "        if (items[j] > 0) {\n"
    "            sum += items[j];\n"
    "        } else {\n"
    "            sum -= 2;\n"
    "            sum += 1;\n"
    "        }\n"
    "    }\n"
    "    return sum;\n"
    "}\n"
)


def write_source(root: Path, name: str, text: str) -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_language_detection():
    assert language_of("src/app/core.c") == "c"
    assert language_of("include/core.h") == "c"
    assert language_of("core.cpp") is None
    assert language_of("core.py") is None
    assert language_of("notes.md") is None


def test_help_does_not_scan(capsys):
    assert run(["--help"]) == 0
    out = capsys.readouterr().out
    assert "Usage: dry4c" in out
    assert "__pycache__" in out
    assert "*_test.c" in out
    assert "--threshold" in out
    assert "--edn" in out
    assert "--changed" in out


def test_unknown_format(capsys):
    assert run(["--format", "csv"]) == 2
    err = capsys.readouterr().err
    assert err == "Unknown format: csv\n"


def test_unknown_option(capsys):
    assert run(["--nope"]) == 1
    err = capsys.readouterr().err
    assert "Unknown option: --nope" in err
    assert "Usage: dry4c" in err


def test_parse_defaults_and_flags():
    options = parse_args(
        ["--threshold", "0.9", "--min-lines", "5", "--min-nodes", "30", "--edn", "spec"]
    )
    assert options.threshold == 0.9
    assert options.min_lines == 5
    assert options.min_nodes == 30
    assert options.format == "edn"
    assert options.positionals == ["spec"]


def test_text_wins_when_it_comes_last():
    assert parse_args(["--edn", "--text"]).format == "text"
    assert parse_args(["--text", "--edn"]).format == "edn"


def test_project_report_and_snapshot(tmp_path, capsys):
    write_source(tmp_path, "src/left.c", LEFT)
    write_source(tmp_path, "src/right.c", RIGHT)
    write_source(tmp_path, "tests/test_left.c", LEFT)
    code = run(["--root", str(tmp_path), "--min-lines", "3", "--min-nodes", "1"])
    captured = capsys.readouterr()
    assert code == 0
    assert "DUPLICATE score=1.00" in captured.out
    assert "src/left.c:1-11" in captured.out
    assert "src/right.c:1-11" in captured.out
    assert "test_left.c" not in captured.out
    text = (tmp_path / ".metrics" / "dry.edn").read_text(encoding="utf-8")
    assert ':language "c"' in text
    assert ':file "src/left.c"' in text
    assert "Wrote" in captured.err


def test_edn_stdout(tmp_path, capsys):
    write_source(tmp_path, "src/left.c", LEFT)
    write_source(tmp_path, "src/right.c", RIGHT)
    assert (
        run(
            [
                "--root",
                str(tmp_path),
                "--edn",
                "--min-lines",
                "3",
                "--min-nodes",
                "1",
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert out.startswith("{:candidates [\n {:score 1.0\n")
    assert ':language "c"\n' in out
    assert ':left {:file "src/left.c", :start-line 1, :end-line 11}\n' in out
    assert ':right {:file "src/right.c", :start-line 1, :end-line 11}\n' in out
    assert ":left-nodes " in out
    assert ":right-nodes " in out
    assert out.endswith("]}\n")


def test_edn_is_empty_when_no_candidates(tmp_path, capsys):
    write_source(tmp_path, "one.c", "int alpha(void) {\n    return 1;\n}\n")
    assert (
        run(["--root", str(tmp_path), "--edn", "--min-lines", "1", "--min-nodes", "1"])
        == 0
    )
    assert capsys.readouterr().out == "{:candidates []}\n"


def test_format_edn_selects_the_edn_report(tmp_path, capsys):
    write_source(tmp_path, "one.c", "int alpha(void) {\n    return 1;\n}\n")
    assert (
        run(
            [
                "--root",
                str(tmp_path),
                "--format",
                "edn",
                "--min-lines",
                "1",
                "--min-nodes",
                "1",
            ]
        )
        == 0
    )
    assert capsys.readouterr().out == "{:candidates []}\n"


def test_text_is_the_default(tmp_path, capsys):
    write_source(tmp_path, "one.c", "int alpha(void) {\n    return 1;\n}\n")
    assert run(["--root", str(tmp_path)]) == 0
    assert capsys.readouterr().out == "No duplicate candidates found.\n"


def test_empty_project(tmp_path, capsys):
    assert run(["--root", str(tmp_path)]) == 0
    assert capsys.readouterr().out == "No source files to analyze.\n"


def test_path_filter(tmp_path, capsys):
    write_source(tmp_path, "src/board/a.c", LEFT)
    write_source(tmp_path, "src/board/b.c", RIGHT)
    write_source(tmp_path, "src/other/a.c", LEFT)
    write_source(tmp_path, "src/other/b.c", RIGHT)
    assert run(["--root", str(tmp_path), "--min-lines", "3", "--min-nodes", "1", "board"]) == 0
    out = capsys.readouterr().out
    assert "src/board/a.c" in out
    assert "src/other/a.c" not in out


def test_explicit_test_file_is_included(tmp_path, capsys):
    write_source(tmp_path, "src/a.c", LEFT)
    write_source(tmp_path, "tests/test_a.c", RIGHT)
    assert (
        run(
            [
                "--root",
                str(tmp_path),
                "--min-lines",
                "3",
                "--min-nodes",
                "1",
                "src/a.c",
                "tests/test_a.c",
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "src/a.c" in out
    assert "tests/test_a.c" in out


def test_main_exits(monkeypatch):
    codes = []
    monkeypatch.setattr("dry4c.cli.sys.exit", lambda code: codes.append(code))
    main(["--help"])
    assert codes == [0]


def test_names_that_are_tests():
    names = [
        "src/app_test.c",
        "src/test_app.c",
        "tests/app.c",
        "test/app.h",
    ]
    for name in names:
        assert is_test_file(name), name
    assert not is_test_file("src/app.c")
    assert not is_test_file("src/testing.c")


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "dev@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Dev"], cwd=path, check=True)


def _commit(path: Path, message: str) -> None:
    subprocess.run(["git", "add", "-A"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", message], cwd=path, check=True, capture_output=True)


def test_changed_files_reads_real_status(tmp_path):
    _init_repo(tmp_path)
    write_source(tmp_path, "src/a.c", "int a(void) { return 1; }\n")
    write_source(tmp_path, "src/old.c", "int b(void) { return 1; }\n")
    write_source(tmp_path, "gone.c", "int c(void) { return 1; }\n")
    _commit(tmp_path, "base")
    (tmp_path / "gone.c").unlink()
    subprocess.run(
        ["git", "mv", "src/old.c", "src/b.c"], cwd=tmp_path, check=True, capture_output=True
    )
    write_source(tmp_path, "src/c d.c", "int d(void) { return 1; }\n")
    write_source(tmp_path, "src/café.c", "int e(void) { return 1; }\n")
    write_source(tmp_path, "fresh/nested/new.c", "int f(void) { return 1; }\n")
    found = set(_changed_files(tmp_path))
    assert (tmp_path / "src/b.c").resolve() in found
    assert (tmp_path / "src/c d.c").resolve() in found
    assert (tmp_path / "src/café.c").resolve() in found
    assert (tmp_path / "fresh/nested/new.c").resolve() in found
    assert (tmp_path / "gone.c").resolve() not in found
    assert (tmp_path / "src/old.c").resolve() not in found


def test_changed_files_reports_git_failure(tmp_path, capsys):
    with pytest.raises(GitStatusError) as caught:
        _changed_files(tmp_path)
    assert caught.value.code == 128
    assert "not a git repository" in caught.value.message
    assert capsys.readouterr().err == ""

    code = run(["--changed", "--root", str(tmp_path)])
    captured = capsys.readouterr()
    assert code == 128
    assert "not a git repository" in captured.err
    assert "No source files" not in captured.out


def test_an_empty_git_error_uses_the_fallback_text(monkeypatch, tmp_path):
    def fail(args, **kwargs):
        return subprocess.CompletedProcess(args, 128, b"", b"   \n")

    monkeypatch.setattr("dry4c.cli.subprocess.run", fail)
    with pytest.raises(GitStatusError, match="git status failed") as caught:
        _changed_files(tmp_path)
    assert caught.value.code == 128


def test_changed_limits_the_report(tmp_path, capsys):
    _init_repo(tmp_path)
    write_source(tmp_path, "src/c.c", LEFT)
    _commit(tmp_path, "base")
    write_source(tmp_path, "src/a.c", LEFT)
    write_source(tmp_path, "src/b.c", RIGHT)
    write_source(tmp_path, "tests/test_a.c", RIGHT)
    write_source(tmp_path, "README.md", "notes\n")
    assert run(["--root", str(tmp_path), "--changed", "--min-lines", "3", "--min-nodes", "1"]) == 0
    out = capsys.readouterr().out
    assert "src/a.c" in out
    assert "src/b.c" in out
    assert "src/c.c" not in out
    assert "test_a.c" not in out


def test_an_option_without_a_value_is_a_usage_error(capsys):
    assert run(["--threshold"]) == 1
    err = capsys.readouterr().err
    assert "--threshold requires a value" in err
    assert "Usage: dry4c" in err


def test_an_empty_value_is_rejected(capsys):
    assert run(["file.c", "--min-lines", ""]) == 1
    assert "--min-lines requires a value" in capsys.readouterr().err


def test_a_flag_is_not_a_value(capsys):
    assert run(["--min-lines", "--min-nodes", "1"]) == 1
    assert "--min-lines requires a value" in capsys.readouterr().err


def test_zero_is_a_valid_count():
    options = parse_args(["--min-lines", "0", "--min-nodes", "0"])
    assert options.action == "scan"
    assert options.min_lines == 0
    assert options.min_nodes == 0


def test_a_negative_count_is_rejected():
    with pytest.raises(ValueError, match="non-negative"):
        _count("-1", "--min-lines")


def test_a_count_must_be_an_integer(capsys):
    assert run(["--min-lines", "nope"]) == 1
    assert "--min-lines requires an integer" in capsys.readouterr().err


def test_a_threshold_must_be_a_number(capsys):
    assert run(["--threshold", "nope"]) == 1
    assert "--threshold requires a number" in capsys.readouterr().err


def test_parse_reads_the_process_arguments(monkeypatch):
    monkeypatch.setattr("dry4c.cli.sys.argv", ["dry4c", "only-this"])
    assert parse_args().positionals == ["only-this"]


def test_source_root_limits_the_walk(tmp_path):
    write_source(tmp_path, "src/a.c", "int a(void) { return 1; }\n")
    write_source(tmp_path, "extra/b.c", "int b(void) { return 1; }\n")
    options = parse_args(["--root", str(tmp_path), "--source-root", "src"])
    files = [path.relative_to(tmp_path).as_posix() for path in select_files(options)]
    assert files == ["src/a.c"]


def test_changed_from_a_subdirectory_stays_inside_it(tmp_path):
    repo = tmp_path / "repo"
    sub = repo / "sub"
    repo.mkdir()
    _init_repo(repo)
    write_source(repo, "src/above.c", "int a(void) { return 1; }\n")
    write_source(sub, "src/below.c", "int b(void) { return 1; }\n")
    chosen = select_files(parse_args(["--root", str(sub), "--changed"]))
    assert chosen == [(sub / "src/below.c").resolve()]


def test_a_short_untracked_name_is_a_file(tmp_path):
    _init_repo(tmp_path)
    write_source(tmp_path, "a.c", "int a(void) { return 1; }\n")
    assert _changed_files(tmp_path) == [(tmp_path / "a.c").resolve()]


def test_changed_source_skips_unknown_and_test_files(tmp_path):
    assert _tracked_source(tmp_path / "README.md") is False
    assert _tracked_source(tmp_path / "tests" / "test_a.c") is False
    assert _tracked_source(tmp_path / "src" / "a.c") is True
    assert _tracked_source(tmp_path / "target" / "app.c") is False


def test_test_files_and_skipped_directories_are_left_out(tmp_path):
    write_source(tmp_path, "src/app.c", "int a(void) { return 1; }\n")
    write_source(tmp_path, "src/foo_test.c", "int a(void) { return 1; }\n")
    write_source(tmp_path, "src/test_foo.c", "int a(void) { return 1; }\n")
    write_source(tmp_path, "src/widget.h", "int b(void) { return 1; }\n")
    write_source(tmp_path, "target/app.c", "int a(void) { return 1; }\n")
    write_source(tmp_path, "tests/app.c", "int a(void) { return 1; }\n")
    relative = [path.relative_to(tmp_path).as_posix() for path in iter_source_files([tmp_path])]
    assert sorted(relative) == ["src/app.c", "src/widget.h"]


def test_an_explicitly_named_test_directory_is_walked(tmp_path, capsys):
    write_source(tmp_path, "tests/left.c", LEFT)
    write_source(tmp_path, "tests/right.c", RIGHT)
    relative = [
        path.relative_to(tmp_path).as_posix()
        for path in iter_source_files([tmp_path / "tests"])
    ]
    assert sorted(relative) == ["tests/left.c", "tests/right.c"]
    assert (
        run(["--root", str(tmp_path), "--min-lines", "3", "--min-nodes", "1", "tests"])
        == 0
    )
    assert "DUPLICATE score=1.00" in capsys.readouterr().out


def test_a_project_below_a_tests_ancestor_is_walked(tmp_path, capsys):
    project = tmp_path / "tests" / "project"
    write_source(project, "src/left.c", LEFT)
    write_source(project, "src/right.c", RIGHT)
    assert run(["--root", str(project), "--min-lines", "3", "--min-nodes", "1"]) == 0
    assert "DUPLICATE score=1.00" in capsys.readouterr().out


def test_is_test_file_ignores_ancestors_above_the_walk_root(tmp_path):
    project = tmp_path / "tests" / "project"
    write_source(project, "src/app.c", "int a(void) { return 1; }\n")
    assert is_test_file(project / "src" / "app.c", project) is False
    assert is_test_file(project / "tests" / "app.c", project) is True
    assert is_test_file(project / "src" / "app_test.c", project) is True
    assert is_test_file(project / "src" / "test_app.c", project) is True


def test_a_second_report_replaces_the_snapshot(tmp_path, capsys):
    write_source(tmp_path, "one.c", "int alpha(void) {\n    return 1;\n}\n")
    args = ["--root", str(tmp_path), "--min-lines", "1", "--min-nodes", "1"]
    assert run(args) == 0
    assert run(args) == 0
    assert (tmp_path / ".metrics" / "dry.edn").read_text(encoding="utf-8") == (
        "{:candidates []}\n"
    )


def test_minimum_lines_filters_candidates(tmp_path, capsys):
    write_source(tmp_path, "left.c", "int alpha(void) { return 1; }\n")
    write_source(tmp_path, "right.c", "int beta(void) { return 2; }\n")
    assert run(["--root", str(tmp_path), "--min-lines", "2", "--min-nodes", "1"]) == 0
    assert "DUPLICATE" not in capsys.readouterr().out
    assert run(["--root", str(tmp_path), "--min-lines", "1", "--min-nodes", "1"]) == 0
    assert "DUPLICATE score=1.00" in capsys.readouterr().out


def test_minimum_nodes_filters_candidates(tmp_path, capsys):
    write_source(tmp_path, "left.c", "int alpha(void) { return 1; }\n")
    write_source(tmp_path, "right.c", "int beta(void) { return 2; }\n")
    assert run(["--root", str(tmp_path), "--min-lines", "1", "--min-nodes", "1000"]) == 0
    assert "DUPLICATE" not in capsys.readouterr().out
    assert run(["--root", str(tmp_path), "--min-lines", "1", "--min-nodes", "1"]) == 0
    assert "DUPLICATE score=1.00" in capsys.readouterr().out


def test_threshold_filters_candidates(tmp_path, capsys):
    write_source(tmp_path, "left.c", LEFT)
    write_source(tmp_path, "right.c", NEAR)
    assert (
        run(
            [
                "--root",
                str(tmp_path),
                "--min-lines",
                "1",
                "--min-nodes",
                "1",
                "--threshold",
                "0.7",
            ]
        )
        == 0
    )
    assert "DUPLICATE" in capsys.readouterr().out
    assert run(["--root", str(tmp_path), "--min-lines", "1", "--min-nodes", "1"]) == 0
    assert "DUPLICATE" not in capsys.readouterr().out
