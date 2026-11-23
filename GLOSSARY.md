# dry4C

Structural duplicate detection for C projects: it compares C functions by the shape of their normalized syntax and reports pairs whose fingerprints overlap enough to review.

## Language

**C function unit**:
A `function_definition` with a body in a `.c` or `.h` file, including `static` and `inline` functions.
_Avoid_: method, procedure, routine

**Normalized form**:
The function's syntax tree with identifiers, field names, type names, and literal values erased; called functions and operators stay.
_Avoid_: canonical form, skeleton

**Fingerprint**:
The serialized normalized form of one syntax node; a function owns the set of fingerprints for its whole subtree.
_Avoid_: hash, signature

**Jaccard similarity**:
Shared fingerprints divided by all fingerprints seen in either function; `1.0` means identical normalized structure.
_Avoid_: overlap score, match percentage

**Duplicate candidate**:
A pair of C function units at or above the similarity threshold.
_Avoid_: clone, match
