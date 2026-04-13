# Plan Review: rosetta-validate (Phase 8, Plan 01)

**Date:** 2026-04-13
**Mode:** HOLD
**Gate:** WARN (3 CRITICAL GAPS fixed; plan safe to build after applying patches)

---

## Mode Selected

HOLD — scope accepted as-is. Goal: make it bulletproof.

---

## Critical Gaps Found and Fixed

### GAP 1: `sh:resultMessage` missing OPTIONAL (CRITICAL → fixed)

SHACL spec: `sh:resultMessage` is optional on `sh:ValidationResult`. Shapes using only
`sh:minCount` with no `sh:message` produce violations with no `sh:resultMessage` triple.
The original bare SPARQL binding silently drops those violations from the report.

**Fix applied:**
- SPARQL query: `OPTIONAL { ?result sh:resultMessage ?message . }`
- `ValidationFinding.message: str | None = None`
- New test: `test_validate_finding_message_none` — shape without `sh:message`, violation appears with `message=None`

### GAP 2: Empty `--shapes-dir` → silent false-positive (CRITICAL → fixed)

Empty shapes graph causes pySHACL to report `conforms=True` for any data. A user pointing
`--shapes-dir` at a directory with no `.ttl` files gets a green exit 0 that is meaningless.

**Fix applied:**
- After building shapes graph from dir, if graph has zero triples: `raise click.UsageError("--shapes-dir contained no .ttl files")`
- New test: `test_validate_shapes_dir_empty`

### GAP 3: `click.Path(exists=True)` missing (CRITICAL → fixed)

Without `exists=True`, Click accepts any string and the error surfaces deep inside rdflib
as a cryptic `FileNotFoundError`. All three path options now specify proper Click.Path types.

**Fix applied:** All path option definitions updated with `exists=True`, `dir_okay=False` / `file_okay=False`.

---

## Warnings

| # | Issue | Action |
|---|-------|--------|
| W1 | Pydantic append point stale (plan said after Embeddings; Provenance is now last) | Fixed in Task 1 |
| W2 | No test for empty shapes-dir | Fixed (test added) |
| W3 | No test for Warning-severity findings | Left for builder: `test_validate_finding_message_none` tests message=None path; Warning severity test is not blocking |

---

## Error & Rescue Registry

| CODEPATH | FAILURE MODE | RESCUED? | TEST? | USER SEES | LOGGED? |
|----------|-------------|----------|-------|-----------|---------|
| `rdflib.Graph().parse(data)` | Invalid Turtle | Y (broad except) | N | "Error: ..." stderr | N |
| `pyshacl.validate(...)` | Malformed shapes | Y (broad except) | N | "Error: ..." stderr | N |
| `open_output(output)` | Permission denied | Y (broad except) | N | "Error: ..." stderr | N |
| `--shapes-dir` glob | Zero .ttl files | Y (UsageError) | Y | UsageError message | N |
| SPARQL on results_graph | No ValidationResults | Y (empty list) | Y (conformant test) | conforms=True, 0 findings | N |

---

## Failure Modes Registry

| CODEPATH | FAILURE MODE | RESCUED? | TEST? | USER SEES | LOGGED? |
|----------|-------------|----------|-------|-----------|---------|
| Validate with no shapes arg | Missing required input | Y (UsageError) | Y | UsageError | N |
| Validate violating data | Violation found | Y (exit 1) | Y | JSON report | N |
| Validate conformant data | No violations | Y (exit 0) | Y | JSON report | N |
| shapes without sh:message | message=None dropping | Y (OPTIONAL) | Y | finding.message=None | N |
| Empty shapes dir | Silent pass | Y (UsageError) | Y | UsageError | N |

---

## Test Diagram

```
rosetta-validate CLI
    │
    ├── test_validate_conformant        → exit 0, conforms=True, findings=[]
    ├── test_validate_violation         → exit 1, findings[0].severity="Violation"
    ├── test_validate_missing_shapes_arg → exit!=0, UsageError
    ├── test_validate_shapes_dir        → exit 1, violation detected via dir
    ├── test_validate_shapes_dir_empty  → exit!=0, UsageError (zero .ttl files)  [NEW]
    ├── test_validate_output_file       → --output writes file, stdout empty
    ├── test_validate_report_schema     → JSON deserialises to ValidationReport
    ├── test_validate_finding_fields    → all fields populated
    └── test_validate_finding_message_none → message=None when shape has no sh:message [NEW]
```

---

## Data Flow

```
--data (Turtle)      ──► rdflib.Graph.parse()  ──► data_graph
--shapes (Turtle)    ──┐
--shapes-dir/*.ttl   ──┤ merge via += ──────────► shapes_graph
                       └─ guard: zero triples → UsageError

data_graph + shapes_graph ──► pyshacl.validate() ──► (conforms, results_graph, _text)
                                                         │
                                               SPARQL SELECT (OPTIONAL message)
                                                         │
                                               [ValidationFinding, ...]
                                                         │
                                               ValidationSummary
                                                         │
                                               ValidationReport.model_dump_json()
                                                         │
                                               open_output() → stdout / --output
                                                         │
                                               sys.exit(0 if conforms else 1)
```

---

## What Already Exists

- `rosetta/cli/validate.py` — stub with correct docstring, needs full implementation
- `rosetta/core/models.py` — existing Pydantic infrastructure; append after `# --- Provenance ---`
- `rosetta/core/io.py` — `open_output()` already available
- `pySHACL` — already declared in `pyproject.toml`
- Pattern: `lint.py` — complete reference for error handling, SPARQL constants, open_output usage

---

## Completion Summary

```
+====================================================================+
|            PLAN REVIEW — COMPLETION SUMMARY                        |
+====================================================================+
| Mode selected        | HOLD                                        |
| System Audit         | No FLOWS.md/ERD.md; pySHACL available       |
| Step 0               | HOLD — scope accepted, hardened             |
| Section 1 (Scope)    | 0 issues                                    |
| Section 2 (Errors)   | 5 error paths mapped, 3 CRITICAL GAPS fixed |
| Section 3 (Security) | 1 issue (click.Path) fixed                  |
| Section 4 (Data/UX)  | 2 shadow paths mapped, both addressed       |
| Section 5 (Tests)    | Diagram produced, 2 gaps → 2 tests added   |
| Section 6 (Future)   | Deferred items logged in CONTEXT.md        |
+--------------------------------------------------------------------+
| Section 7 (Eng Arch) | 1 append-point issue fixed                  |
| Section 8 (Code Ql)  | 1 type annotation fix (str → str|None)     |
| Section 9 (Eng Test) | Test diagram produced, 9 tests (was 7)      |
| Section 10 (Perf)    | 0 issues (do_owl_imports=False correct)     |
+--------------------------------------------------------------------+
| PLAN.md updated      | 4 truths added, 2 tests added               |
| CONTEXT.md updated   | 5 decisions locked, 3 items deferred        |
| Error/rescue registry| 5 paths, 3 CRITICAL GAPS → fixed in plan    |
| Failure modes        | 5 total, 0 remaining CRITICAL GAPS          |
| Diagrams produced    | data flow, test coverage                    |
| Unresolved decisions | 0                                           |
+====================================================================+
```
