# Plan Review — Phase 17 Unit Detection (2026-04-16)

**Human reference only — not consumed by downstream skills.**

## Mode Selected

HOLD — scope accepted; review focused on correctness and reliability.

## Completion Summary

```
+====================================================================+
|            PLAN REVIEW — COMPLETION SUMMARY                        |
+====================================================================+
| Mode selected        | HOLD                                        |
| System Audit         | No FLOWS/ERD; 3 consumers of                |
|                      | UNIT_STRING_TO_IRI identified               |
| Step 0               | HOLD — scope is well-calibrated             |
| Section 1  (Scope)   | 2 issues found (Task 5 pseudocode, min unit)|
| Section 2  (AC)      | 2 warnings (done criteria gaps)             |
| Section 3  (UX)      | 1 CRITICAL (dBm message regression)        |
| Section 4  (Risk)    | 2 CRITICAL (UnitRegistry, ImportError)     |
| Section 5  (Deps)    | 1 CRITICAL (rad dead code), 1 WARNING      |
| Section 6  (Correct) | 1 CRITICAL (dBm message confirmed)         |
+--------------------------------------------------------------------+
| Section 7  (Arch)    | 2 CRITICAL (rad dead code, None docstring)  |
| Section 8  (Testing) | 3 issues (quantulum3 test fragility,        |
|                      | duplicate tests, missing crash test)        |
| Section 9  (Perf)    | 1 CRITICAL (UnitRegistry per-call)         |
| Section 10 (Sec)     | 2 warnings (silent degradation, model pin)  |
+--------------------------------------------------------------------+
| PLAN.md updated      | 10 truths added, 0 artifacts added          |
| CONTEXT.md updated   | 9 decisions locked, 3 items deferred       |
| Error/rescue registry| 2 methods mapped, 2 CRITICAL GAPS → PLAN.md|
| Failure modes        | 4 total, 4 CRITICAL GAPS → PLAN.md         |
| Delight opportunities| N/A (HOLD mode)                            |
| Diagrams produced    | 1 (error flow)                             |
| Unresolved decisions | 0                                          |
+====================================================================+
```

## Critical Gaps Fixed (all → PLAN.md truths)

| # | Gap | Fix Applied |
|---|-----|-------------|
| 1 | `_rad` dead code — combined deg/rad pattern shadows unit:RAD entry | Split into two patterns: deg/grad/grader and rad/radians? |
| 2 | `UnitRegistry()` per-call — N expensive objects in lint loop | Module-level `_ureg` lazy singleton |
| 3 | `q3.parse()` unguarded — crashes propagate to lint CLI | Wrap entire for-body in outer except |
| 4 | `test_lint_sssom_unit_no_iri_mapping` message assertion fails | Assert rule only, not message text (option A chosen) |

## Failure Modes Registry

```
CODEPATH                    | FAILURE MODE              | RESCUED? | TEST? | USER SEES?    | LOGGED?
----------------------------|---------------------------|----------|-------|---------------|--------
_detect_from_nlp import     | ImportError (missing dep) | Y        | N     | None returned | N
_detect_from_nlp q3.parse() | RuntimeError/OSError      | Y        | N     | None returned | N
_NAME_PATTERNS _rad match   | Returns DEG not RAD       | Y(fixed) | Y     | Wrong IRI     | N
_check_units dBm path       | Message text mismatch     | Y(fixed) | Y     | test updated  | N
```

## Error Flow Diagram

```
detect_unit(name, desc)
  │
  ├─ _NAME_PATTERNS match?
  │   ├─ Yes, IRI="unit:X" ──────────────────────────────► return "unit:X"
  │   ├─ Yes, IRI=None (dBm) ───────────────────────────► return None
  │   └─ No match
  │
  ├─ _DESC_PATTERNS match?
  │   ├─ Yes, IRI="unit:X" ──────────────────────────────► return "unit:X"
  │   └─ No match
  │
  └─ _detect_from_nlp(desc)
      │
      ├─ ImportError (missing quantulum3/pint) ──────────► return None
      │
      ├─ q3.parse() raises ──────────────────────────────► except → return None
      │
      └─ for qty in q3.parse(desc):
          ├─ ureg.parse_expression() raises ────────────► continue
          ├─ str(units) in _PINT_TO_QUDT_IRI (None val) ► return None
          ├─ str(units) in _PINT_TO_QUDT_IRI (IRI val) ─► return "unit:X"
          └─ str(units) not in dict ────────────────────► continue
      └─ exhausted ─────────────────────────────────────► return None
```

## What Already Exists

- `_unit_label()` in lint.py correctly prefers human label over ID tail — preserved by Task 5
- `units_compatible()`, `dimension_vector()`, `suggest_fnml()` in units.py — completely unchanged
- `test_lint_sssom_unit_dimension_mismatch`, `_unit_conversion_required`, `_unit_not_detected` integration tests — all expected to pass without changes (verified by review)

## Dream State Delta

Phase 17 leaves the system at: single-IRI-output detection with three-layer cascade, dBm handled cleanly, no sync tables. Next phase gap: no dimension vector for newly added units is verified at test time (only TTL parse is checked). A future phase could add a parametrized test that calls `dimension_vector()` for every IRI in `_PINT_TO_QUDT_IRI` and asserts non-None.
