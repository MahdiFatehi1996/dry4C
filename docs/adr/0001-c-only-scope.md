# C-only scope

The upstream Python tool compares Clojure, Java, Go, TypeScript, Rust, and Python. dry4C exists for C projects, so the fork keeps only the C function picker and C node normalization; C++ is out of scope.

Consequences: every comparison is C-to-C, so no cross-language candidate can appear. Restoring another language means restoring the upstream picker seam.
