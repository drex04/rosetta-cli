# Plan Review — Phase 7 rosetta-provenance (2026-04-13)

## Mode: HOLD

Scope accepted as-is. Review hardened the plan against failure modes, injection vulnerabilities, and test gaps.

---

## Completion Summary

```
+====================================================================+
|            PLAN REVIEW — COMPLETION SUMMARY                        |
+====================================================================+
| Mode selected        | HOLD                                        |
| System Audit         | No FLOWS.md/ERD.md; STRUCTURE.md available  |
| Step 0               | HOLD confirmed; no scope changes            |
| Section 1  (Scope)   | 1 issue — version field semantics undoc'd   |
| Section 2  (Errors)  | 4 error paths mapped, 4 CRITICAL GAPS fixed |
| Section 3  (UX)      | 2 warnings fixed (Choice, help text)        |
| Section 4  (Risk)    | 1 warning — concurrent write documented     |
| Section 5  (Deps)    | 1 CRITICAL fixed — namespace import         |
| Section 6  (Correct) | 1 CRITICAL fixed — version semantics/SPARQL |
+--------------------------------------------------------------------+
| Section 7  (Eng Arch)| 2 issues — SPARQL f-string (CRITICAL fixed),|
|                      |   query_graph utility directed               |
| Section 8  (Code Ql) | 3 warnings fixed (label default, version doc,|
|                      |   ProvenanceRecord instance in CLI)          |
| Section 9  (Eng Test)| Test diagram produced; 2 GAPs → 2 new tests |
| Section 10 (Perf/Sec)| 2 CRITICAL injection paths fixed in plan    |
+--------------------------------------------------------------------+
| PLAN.md updated      | 4 truths added, 1 key_link fixed            |
| CONTEXT.md created   | 13 decisions locked, 3 items deferred       |
| Error/rescue registry| 4 methods, 4 CRITICAL GAPS → PLAN.md        |
| Failure modes        | 6 total, 2 CRITICAL injection → PLAN.md     |
| Delight opportunities| N/A (HOLD mode)                             |
| Diagrams produced    | 1 (test coverage ASCII)                     |
| Unresolved decisions | 0                                           |
+====================================================================+
```

---

## Test Coverage Diagram

```
stamp_artifact (core)
├── [COVERED] test_stamp_returns_version_1_on_first_call
├── [COVERED] test_stamp_increments_version
├── [COVERED] test_stamp_adds_prov_entity_triple
├── [COVERED] test_stamp_adds_activity_triple
├── [COVERED] test_stamp_adds_agent_triple
├── [COVERED] test_stamp_datetime_injected
├── [COVERED] test_stamp_label_optional
└── [COVERED] test_stamp_label_present

query_provenance (core)
├── [COVERED] test_query_empty_graph_returns_empty_list
├── [COVERED] test_query_returns_one_record_after_stamp
└── [COVERED] test_query_returns_two_records_after_two_stamps
           (NOTE: both records assert version==2, not 1 and 2)

ProvenanceRecord (model)
└── [COVERED] test_provenance_record_model_roundtrip

CLI stamp
├── [COVERED] test_cli_stamp_writes_valid_turtle
├── [COVERED] test_cli_stamp_exits_zero
└── [ADDED]   test_cli_stamp_invalid_input  ← new, was missing

CLI query
├── [COVERED] test_cli_query_after_stamp
├── [COVERED] test_cli_query_json_format
└── [ADDED]   test_cli_query_no_records     ← new, was missing
```

---

## Critical Fixes Applied

### 1. SPARQL Injection (stamp_artifact MAX query)
**Before:** `f"SELECT (MAX(?v) AS ?max_v) WHERE {{ <{artifact_uri}> rose:version ?v }}"`
**After:** `query_graph(g, SPARQL, bindings={"artifact": URIRef(artifact_uri)})` where SPARQL uses `?artifact`.

### 2. SPARQL Injection (query_provenance skeleton)
**Before:** `<{artifact_uri}>` in SPARQL skeleton with a contradictory note to use initBindings.
**After:** SPARQL skeleton uses `?artifact` throughout; called via `query_graph()` with `initBindings`.

### 3. Namespace Import Collision
**Before:** `from rdflib.namespace import PROV` — creates a second `Namespace` object at same URI as `_PROV` in rdf_utils.
**After:** `from rosetta.core.rdf_utils import _PROV as PROV` — single authoritative source.

### 4. None-guard on MAX aggregate
**Before:** No mention of None-guard on SPARQL aggregate result.
**After:** Explicit pattern documented: `int(rows[0]["max_v"]) if rows and rows[0]["max_v"] is not None else 0`.

### 5. CLI Error Handling
**Before:** "Exit 1 on any exception" — no spec for which exceptions or how.
**After:** Explicit try/except wrapping load_graph + stamp_artifact + save_graph; covers ValueError (bad TTL/missing file) and OSError (read-only path).

---

## What Already Exists

- `query_graph()` in `rdf_utils.py` — provides initBindings dispatch, row-to-dict conversion. Plan now directs both queries to use it.
- `bind_namespaces()` — already binds `_PROV` as "prov"; plan no longer adds redundant binding.
- `load_graph()` / `save_graph()` — accept Path or TextIO; save_graph handles in-place write.
- Pydantic v2 pattern established in models.py — `= None` defaults for optional fields.

---

---

## Second Review Pass — 2026-04-13 (post-implementation)

Implementation was committed in `4e76f65`. This second pass reviews the actual code against plan truths.

### CRITICAL: `PROV.type` used instead of `RDF.type`

**Files:** `rosetta/core/provenance.py:89,96,98`, `rosetta/tests/test_provenance.py:68,73,80`

The implementation uses `PROV.type` (`http://www.w3.org/ns/prov#type`) as the predicate for all three type assertions instead of `RDF.type` (`rdf:type`). Generated Turtle contains:

```turtle
rose:activity/uuid prov:type prov:Activity .   # WRONG
```
instead of:
```turtle
rose:activity/uuid a prov:Activity .           # CORRECT
```

Root cause: `RDF` is not imported in `provenance.py`. Tests 3–5 also use `PROV.type`, masking the bug. The `# type: ignore[attr-defined]` comments are the signal. Fix: add `RDF` to imports, replace 3× `PROV.type` with `RDF.type`, update tests 3–5.

New truths added to PLAN.md:
- `[review] stamp_artifact MUST use RDF.type (rdf:type) — not PROV.type — for type assertions`
- `[review] test_cli_stamp_writes_valid_turtle must assert PROV-O content, not merely len(g) > 0`
- `[review] A test must cover the write-failure path (unwritable output path → exit 1)`

### WARNING: Synthetic `activity_uri` in stamp CLI summary

`rosetta/cli/provenance.py:75` constructs the stderr ProvenanceRecord with `activity_uri="rose:activity/summary"` — a placeholder, not the real UUID activity URI. Tracked as tech debt. Fix: return `(int, str)` from `stamp_artifact`.

---

## Dream State Delta

This plan lands PROV-O stamping for v1. Known gaps vs ideal:
- `ProvenanceRecord.version` is "current at query time," not historical per-activity. A per-activity version would require storing `rose:version` on each Activity node — deferred.
- No concurrent write safety (file locking). Deferred.
- No PKI signatures on provenance records. Explicitly out of scope for v1.
