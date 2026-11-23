# Read source text without preprocessing

Duplicates are found in the source as written, using the tree-sitter C grammar. `#if` branches are compared as written and macros are not expanded.

Two files that compile to the same code through different macros will not be reported; two files whose text shares structure will be. This keeps reported line spans aligned with the developer's editor.
