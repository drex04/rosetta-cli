# Plan Review — Phase 6 Plan 01 (Core RML Engine)

**Date:** 2026-04-13  
**Mode:** HOLD  
**Plan:** `.planning/phases/06-rosetta-rml-gen/06-01-PLAN.md`

## Completion Summary

```
+====================================================================+
|            PLAN REVIEW — COMPLETION SUMMARY                        |
+====================================================================+
| Mode selected        | HOLD                                        |
| System Audit         | claude-mem unavailable; ast-grep available  |
| Step 0               | Scope accepted as-is                        |
| Section 1  (Scope)   | 0 issues — matches phase goal exactly       |
| Section 2  (Errors)  | 3 error paths mapped, 2 CRITICAL GAPS fixed |
| Section 3  (Security)| 0 issues                                    |
| Section 4  (Data/UX) | 2 edge cases found, 1 fixed (array input)   |
| Section 5  (Tests)   | 2 gaps added as tests 8+9                   |
| Section 6  (Future)  | Reversibility: 5/5, 0 debt items            |
+--------------------------------------------------------------------+
| Section 7  (Arch)    | 0 issues — single-source design is correct  |
| Section 8  (Code Ql) | 1 unused import fixed (CRITICAL)            |
| Section 9  (Tests)   | Test diagram produced, 2 gaps closed        |
| Section 10 (Perf)    | 0 issues                                    |
+--------------------------------------------------------------------+
| PLAN.md updated      | 3 truths added, 2 tests added (7→9)         |
| CONTEXT.md updated   | N/A (no CONTEXT.md for this phase yet)      |
| Error/rescue registry| 3 methods, 2 CRITICAL GAPS → fixed in plan  |
| Failure modes        | 4 total, 2 CRITICAL fixed, 2 WARNING noted  |
| Diagrams produced    | 1 (test coverage)                           |
| Unresolved decisions | 0                                           |
+====================================================================+
```

## Test Coverage Diagram

```
rml_builder.py
├── build_rml_graph()
│   ├── unsupported format → ValueError          [test 4 ✓]
│   ├── happy path json, 2 decisions             [test 1 ✓]
│   ├── happy path csv                           [test 3 ✓]
│   └── _field_ref dispatch
│       ├── explicit field_ref                   [test 1 ✓]
│       ├── derived from URI (json) → "$.name"   [test 2 ✓]
│       └── derived from URI (csv)  → "name"     [test 3 ✓]
│
rml_gen.py (CLI)
├── JSON parse error                             [implicit in except ✓]
├── JSON not a dict (array)                      [test 8 ✓ added]
├── empty raw dict                               [test 5 ✓]
├── missing target_uri                           [test 6 ✓]
├── pydantic.ValidationError in loop             [test 9 ✓ added]
├── valid stdout output                          [test 7 ✓]
└── --output file flag                           [not tested — acceptable]
```

## Error & Rescue Registry

| CODEPATH | FAILURE MODE | RESCUED? | TEST? | USER SEES | LOGGED? |
|----------|-------------|----------|-------|-----------|---------|
| `json.loads(...)` | JSONDecodeError / IOError | Y | implicit | "Error reading decisions: ..." | N |
| `isinstance(raw, dict)` | JSON array input | Y | Y (test 8) | "must be a JSON object" | N |
| `MappingDecision(**props)` | ValidationError | Y | Y (test 9) | "invalid decision for {uri}: ..." | N |
| `"target_uri" not in props` | Missing required key | Y | Y (test 6) | "missing 'target_uri' for {uri}" | N |
| `build_rml_graph(...)` | ValueError (bad format) | Y | Y (test 4) | "Error: ..." | N |

## Failure Modes Registry

| CODEPATH | FAILURE MODE | RESCUED? | TEST? | USER SEES? | LOGGED? |
|----------|-------------|----------|-------|------------|---------|
| `import rdflib` bare import | ruff F401 — CI block | FIXED | — | CI fail | — |
| `MappingDecision(**props)` | ValidationError uncaught | FIXED | Y | error + exit 1 | N |
| `raw.items()` on list input | AttributeError uncaught | FIXED | Y | error + exit 1 | N |
| `_field_ref("")` json | Returns `"$."` invalid JSONPath | N (warning) | N | silent bad output | N |

## What Already Exists

- `rosetta/core/io.py`: `open_output()` — reused correctly in rml_gen.py
- `rosetta/core/models.py`: `FnmlSuggestion` already has `fnml_function`, `multiplier`, `offset` — `MappingDecision` should use consistent field names (it does)
- `rosetta/core/config.py`: `get_config_value` pattern for rosetta.toml — Plan 02 will wire this

## Dream State Delta

Plan 01 delivers the core engine. Plan 02 adds FnML and `--from-suggest`. After both plans, the only gap vs. 12-month ideal is multi-source support (multiple `rml:logicalSource` in one file) — deferred by design, acceptable for v1.
