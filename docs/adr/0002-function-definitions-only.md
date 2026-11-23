# Compare function definitions only

A C function unit is a `function_definition` with a body. Declarations in headers are ignored; `static inline` definitions in headers are included. A function definition nested inside another function is part of the enclosing unit, not a candidate of its own. Macros are textual and have no function unit.

The enclosing function is the unit. crap4C may score a nested definition on its own, so a duplicate pair need not name exactly the same span as a CRAP entry. The cost is that function-like macros and duplicated statement blocks are not candidates.
