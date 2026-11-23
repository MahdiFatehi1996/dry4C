# dry4C

Structural duplicate finder for C codebases. A C-only adaptation of
[unclebob/dryer](https://github.com/unclebob/dryer).

The tool compares C function definitions by the shape of their normalized
syntax trees. Names, types, field names, and literal values are erased; called
functions, called member names, and operators stay. The score is Jaccard
similarity of structural fingerprints, so a renamed copy scores `1.0` and a
pair whose calls or operators differ scores lower.

## Run

```bash
./dry4c
```

The first run creates `.venv` and installs the tool. From a project root it
walks the tree for `.c` and `.h` files, skips test and generated directories,
and writes two results:

- a report on stdout, closest match first
- `.metrics/dry.edn`, replaced on every successful analysis

```bash
./dry4c src/demo include         # these files and trees
./dry4c --changed                # git additions and edits
./dry4c billing                  # path fragment
./dry4c --threshold 0.9 src
./dry4c --edn --min-lines 3 src
```

```text
--threshold N    Minimum structural similarity score, default 0.82
--min-lines N    Minimum source lines in a candidate function, default 4
--min-nodes N    Minimum normalized syntax nodes, default 20
--format F       text or edn, default text
--edn            Same as --format edn
--text           Same as --format text
```

Text output:

```text
DUPLICATE score=1.00
  src/billing/invoice.c:12-25
  src/billing/receipt.c:30-44
```

EDN output keeps the upstream `{:candidates ...}` shape; no candidates prints
`{:candidates []}`.

```clojure
{:candidates [
 {:score 1.0
  :language "c"
  :left {:file "src/billing/invoice.c", :start-line 12, :end-line 25}
  :right {:file "src/billing/receipt.c", :start-line 30, :end-line 44}
  :left-nodes 88
  :right-nodes 91}
]}
```

## What C compares

A candidate function is a `function_definition` with a body, including
`static` and `inline` definitions in headers. A declaration is not a candidate
function. A duplicate candidate is a pair of candidate functions at or above
the similarity threshold. A function nested inside another function stays part
of the enclosing function, so only the outer function is reported. Macros are
not expanded and `#if` branches are compared as written.

Test files (`*_test.c`, `test_*.c`) and test directories are skipped unless
named explicitly.

## Exit codes

`0` after a report, `1` on a usage error with the usage text on stderr, and
`2` on an unknown `--format`. `--changed` keeps git's own exit code when the
repository cannot be read.

## Development

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/pytest
```

## License

0BSD. Derived from Uncle Bob's `dryer`; the upstream license and attribution
are kept in [LICENSE](LICENSE).

## Agent skills

See `AGENTS.md`.
