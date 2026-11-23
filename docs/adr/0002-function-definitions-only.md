# Compare function definitions only

A C function unit is a `function_definition` with a body. Declarations in headers are ignored; `static inline` definitions in headers are included. Macros are textual and have no function unit.

This matches the granularity crap4C scores, so a duplicate pair and a CRAP entry name the same span. The cost is that function-like macros and duplicated statement blocks are not candidates.
