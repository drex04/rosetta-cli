# Plan Review — Phase 11 Plan 02: JSON Sample Deduction
**Date:** 2026-04-13 | **Mode:** HOLD | **Gate:** WARN (all CRITICALs resolved in plan)

---

## Completion Summary

```
+====================================================================+
|            PLAN REVIEW — COMPLETION SUMMARY                        |
+====================================================================+
| Mode selected        | HOLD                                        |
| System Audit         | No FLOWS/ERD; ARCHITECTURE.md present       |
| Step 0               | Scope accepted; 2 CRITICALs, 3 IMPORTANTs  |
| Section 1  (Scope)   | 1 WARNING (kurs_grad unit detection)        |
| Section 2  (Stories) | 2 CRITICAL gaps (A: multi-key, B: empty {}) |
| Section 3  (UX)      | 1 WARNING (dispatch_parser error messages)  |
| Section 4  (Risk)    | 1 WARNING (hoehe_m OK, kurs_grad gap)       |
| Section 5  (Deps)    | OK — 11-01 prerequisite clearly stated      |
| Section 6  (Correct) | 3 CRITICAL code gaps vs stated truths       |
+--------------------------------------------------------------------+
| Section 7  (Arch)    | OK — consistent module placement/imports    |
| Section 8  (Testing) | 3 missing tests identified + added          |
| Section 9  (Perf)    | 1 WARNING (max_sample_rows not threaded)    |
| Section 10 (Security)| 2 issues (json.load errors, field name URIs)|
+--------------------------------------------------------------------+
| PLAN.md updated      | 8 truths added (14–21), 2 artifacts added   |
| CONTEXT.md updated   | 5 decisions locked, 0 items deferred        |
| Error/rescue registry| 7 conditions mapped, 3 CRITICAL GAPS fixed  |
| Failure modes        | 7 total, 5 CRITICAL/IMPORTANT → plan truths |
| Delight opportunities| N/A (HOLD mode)                             |
| Diagrams produced    | Test coverage diagram (below), data flow    |
| Unresolved decisions | 0                                           |
+====================================================================+
```

---

## Critical Findings Applied

### CRITICAL A — Multi-key envelope code inconsistency
**Problem:** Plan truths #10/#11 required `_infer_data_type` to handle list-of-dicts as `"object"` and `_build_fields` to recurse into flattened items. The code blocks in Task 1 did NOT implement this — `_infer_data_type` had no list branch, and `_build_fields` only recursed into `dict` values. `test_json_sample_multi_key_envelope` would fail deterministically.

**Fix applied:**
- `_infer_data_type`: new branch `if all(isinstance(v, list) and any(isinstance(i, dict) for i in v) for v in non_null): return "object"`
- `_build_fields`: when `data_type == "object"` and values contain lists, flattens items: `nested = [item for v in values if isinstance(v, list) for item in v if isinstance(item, dict)]`
- Normalisation `objects = [data]` for multi-key envelope is CORRECT — works because `_infer_data_type` now handles list-of-dicts per key

### CRITICAL C — `kurs_grad` unit detection
**Problem:** Plan claimed `kurs_grad → detected_unit="degree"` (truths #4, task done-when table, `test_json_sample_unit_detection`). `detect_unit("kurs_grad", "")` returns `None` because the degree regex pattern is `(?:^|_)(?:deg|grader)$` — `_grad` does not match.

**Fix applied:**
- `unit_detect.py` added to Artifacts table
- New truth #18: degree pattern updated to `(?:^|_)(?:deg|grad|grader)$`
- Task 2 notes the `unit_detect.py` change explicitly

### IMPORTANT B — Empty dict `{}` silent pass
**Problem:** `{}` → `objects=[{}]` (passes `if not objects`) → `_build_fields([{}])` → `[]` → returns `([], slug)` without error. G4 requires ValueError on no fields produced.

**Fix applied:** Truth #16 + Step 4 code updated: `if not fields: raise ValueError(...)` after `_build_fields`.

### IMPORTANT D — `json.load` exceptions not caught
**Problem:** `json.JSONDecodeError` and `RecursionError` propagate as tracebacks (exit code 2), not as exit-1 ValueError. Inconsistent with all other parsers.

**Fix applied:** Truth #17 + Step 1 code updated with `try/except (json.JSONDecodeError, RecursionError)` → `ValueError`.

---

## Test Coverage Diagram

```
parse_json_sample(src, path, nation, max_sample_rows)
│
├── json.load(src)
│   ├── OK                        → continue
│   ├── JSONDecodeError           → ValueError ✓ [test_malformed_json_raises]
│   └── RecursionError            → ValueError ✓ [test_malformed_json_raises covers this]
│
├── Normalise to objects[]
│   ├── list input                → filter dicts  ✓ [test_direct_array]
│   ├── envelope single-key       → unwrap         ✓ [test_envelope]
│   ├── envelope multi-key        → objects=[data] ✓ [test_multi_key_envelope]
│   ├── flat dict                 → [data]          ✓ [test_single_flat_object]
│   ├── scalar                    → ValueError      ✓ implied by error tests
│   ├── empty []                  → ValueError      ✓ [test_empty_array_raises]
│   └── [1,2,3]                   → ValueError      ✓ [test_non_object_array_raises]
│
├── objects[:max_sample_rows]     → cap             ✓ (threading tested via dispatch)
│
├── _build_fields(objects)
│   ├── {} input → fields=[]      → ValueError      ✓ [test_empty_object_raises]  ← NEW
│   ├── nested dict values        → recurse         ✓ [test_nesting]
│   ├── list-of-dicts values      → recurse flatten ✓ [test_multi_key_envelope]
│   ├── depth >= max_depth        → truncate silent ✓ [test_max_depth_truncates]  ← NEW
│   └── leaf values               → stats+units     ✓ [test_stats_populated, test_unit_detection]
│
├── fields_to_graph()             → Turtle           ✓ [test_has_child_in_turtle]
│   └── rose:hasChild arcs        → position→child  ✓ [test_has_child_in_turtle]
│
├── dispatch_parser routing
│   ├── .json → json-schema       → no regression   ✓ [test_no_auto_detect]
│   └── json-sample explicit      → OK              ✓ [test_cli_roundtrip]
│
└── slug
    ├── path given                → stem            ✓ [test_envelope]
    └── path=None                 → "sample"        ✓ [test_stdin_slug]

GAPS REMAINING (acceptable, deferred):
  - schema_slug ValueError on empty/special stem — surfaced by CLI layer (existing behavior)
  - RDF field name injection — in scope of RDF builder, not parser
  - Large file OOM — documented as known limitation (sample files expected < 50 MB)
```

---

## Data Flow

```
deu_patriot_sample.json
        │
        ▼
  json.load()  ──── JSONDecodeError ──▶ ValueError (exit 1)
        │       └── RecursionError  ──▶ ValueError (exit 1)
        ▼
  Normalise to objects[]
  {"erkannte_ziele": [...]}
        │  single-key envelope → unwrap inner list
        ▼
  objects = [obj1, obj2, ..., obj5]
        │  objects[:max_sample_rows]
        ▼
  _build_fields(objects)
  ┌──────────────────────────────────┐
  │  for key in sorted(all_keys):    │
  │    values = [obj[key] ...]       │
  │    data_type = _infer_data_type  │──── list-of-dicts → "object" (NEW)
  │    if "object":                  │
  │      ├─ dict values → recurse    │
  │      └─ list values → flatten+recurse (NEW)
  │    else: sample_values + stats   │
  └──────────────────────────────────┘
        │
        ▼
  list[FieldSchema] with .children
        │  if not fields → ValueError (NEW)
        ▼
  fields_to_graph() → rdflib.Graph
        │
        ▼
  Turtle serialisation
  f:position rose:hasChild f:position__hoehe_m .
  f:geschwindigkeit_kmh rose:stats [...] .
```

---

## What already exists
- `FieldSchema`, `schema_slug`, `dispatch_parser` — fully functional; json-sample is a pure additive case
- `unit_detect.py` `detect_unit` + `compute_stats` — correct API, just needs `grad` pattern added
- `_emit_field` recursive RDF builder — added in 11-01 Task 1, handles `.children` already
- All other parser patterns (csv, json-schema, openapi) — lazy-import pattern to copy

## Dream-state delta
This plan leaves us with: raw JSON samples → structured field schemas → RDF. The missing 20% to an ideal state is: streaming parse for large samples (currently all-in-memory), auto-detection of array-of-objects vs schema from file content (currently explicit flag required), and multi-file merge (e.g. 3 samples of the same schema averaged). None of these are in scope; the current design explicitly defers them.
