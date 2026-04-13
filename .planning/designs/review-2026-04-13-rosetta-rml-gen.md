# Plan Review — rosetta-rml-gen (Phase 06 Plan 01)
Date: 2026-04-13  
Mode: HOLD  
Reviewer: plan-review skill

## Completion Summary

```
+====================================================================+
|            PLAN REVIEW — COMPLETION SUMMARY                        |
+====================================================================+
| Mode selected        | HOLD                                        |
| System Audit         | All impl files exist; FLOWS/ERD absent       |
| Step 0               | HOLD — scope accepted, bulletproofing only  |
| Section 1  (Correct) | 3 issues: 1 CRITICAL, 2 WARNING             |
| Section 2  (Errors)  | 9 error paths mapped, 1 CRITICAL GAP        |
| Section 3  (Tests)   | 9/9 tests exist; 1 gap (conversion_fn path) |
| Section 4  (Arch)    | OK — BNode usage correct, no external deps  |
| Section 5  (Perf)    | OK — pure in-memory, no I/O in core         |
| Section 6  (Sec)     | OK — no injection risk                      |
+--------------------------------------------------------------------+
| PLAN.md updated      | 4 truths added                              |
| CONTEXT.md created   | 4 review decisions, 4 deferred items        |
| README.md fixed      | 3 documentation bugs corrected              |
| Error/rescue registry| 9 paths mapped, 1 CRITICAL GAP documented   |
| Failure modes        | 4 total, 1 CRITICAL (conversion_fn silent)  |
| Delight opportunities| N/A (HOLD mode)                             |
| Diagrams produced    | Error/rescue table, test coverage diagram   |
| Unresolved decisions | 0                                           |
+====================================================================+
```

## Critical Finding Fixed

**conversion_fn silent failure (README-driven):**  
- README documented `conversion_fn` key in decisions format  
- `MappingDecision` model field is `fnml_function`, not `conversion_fn`  
- Pydantic v2 silently ignores unknown fields (no `extra="forbid"`)  
- User following README would get exit 0 but plain RML with no unit conversion  
- **Fix applied:** Removed `conversion_fn` from README example; replaced with `field_ref` example. Added note that FnML is a later phase.

## README Fixes Applied

1. `--source-format TEXT` → `--source-format [json|csv]` (matches Click Choice rendering)
2. `conversion_fn` removed from decisions format example (Plan 02 scope)
3. Subject field convention documented: source data must have `id` field for `rr:subjectMap` template

## Error/Rescue Registry

| CODEPATH | FAILURE | RESCUED? | TEST? | USER SEES? | LOGGED? |
|----------|---------|----------|-------|-----------|---------|
| Path.read_text() | FileNotFoundError | Y | N | "Error reading: ..." | stderr |
| json.loads() | JSONDecodeError | Y | N | "Error reading: ..." | stderr |
| isinstance(raw,dict) | Array/null | Y | Y | "must be a JSON object" | stderr |
| `not raw` | Empty dict | Y | Y | "decisions file is empty" | stderr |
| target_uri missing | KeyError | Y | Y | "missing 'target_uri'" | stderr |
| MappingDecision(**props) | ValidationError | Y | Y | "invalid decision for X" | stderr |
| build_rml_graph() | ValueError (bad format) | Y | Y | "Error: ..." | stderr |
| open_output() | PermissionError | N | N | raw traceback | none |
| URIRef(target_uri) | Malformed URI | N | N | silent invalid RDF | none |

## Test Coverage Diagram

```
build_rml_graph()
├── happy: two decisions, json format         ✓ test_basic_rml_two_decisions
├── field_ref=None → last URI segment         ✓ test_field_ref_from_uri
├── csv format → bare column name             ✓ test_csv_format_bare_ref
└── unsupported format → ValueError           ✓ test_unsupported_format_raises

cli()
├── empty dict {}                             ✓ test_cli_empty_decisions_exits_1
├── missing target_uri                        ✓ test_cli_missing_target_uri_exits_1
├── valid → stdout turtle w/ rml:logicalSource✓ test_cli_writes_turtle_to_stdout
├── array input []                            ✓ test_cli_json_array_input_exits_1
└── invalid field type (multiplier)           ✓ test_cli_invalid_decision_type_exits_1

GAPS (no test / accepted deferred):
├── conversion_fn silently ignored            CRITICAL → fixed in README (no test needed post-fix)
├── malformed target_uri                      deferred (D-06-R03)
└── open_output PermissionError               consistent with all other tools
```

## What Already Exists

All Phase 01 implementation is complete and committed in `4e76f65`:
- `rosetta/core/rml_builder.py` — full builder with BNode graph construction
- `rosetta/cli/rml_gen.py` — Click CLI with all error guards
- `rosetta/tests/test_rml_gen.py` — 9 tests
- `rosetta/core/models.py:126` — MappingDecision model

## Dream State Delta

Phase 01 delivers structural RML only. The 12-month ideal adds:
- FnML `fnml:functionValue` blocks for unit conversion (Plan 02)
- Per-schema TriplesMaps (multi-source decisions)
- URI validation at `MappingDecision` parse time
