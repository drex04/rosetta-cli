# Plan Review: Phase 11 — rosetta-ingest Extensions (XSD + JSON sample)
**Date:** 2026-04-13
**Mode:** HOLD SCOPE
**Plans reviewed:** 11-01 (XSD parser), 11-02 (JSON sample deduction)

---

## Mode Selected
HOLD SCOPE — plans are well-specified; goal is to bulletproof implementation.

---

## Completion Summary

```
+====================================================================+
|            PLAN REVIEW — COMPLETION SUMMARY                        |
+====================================================================+
| Mode selected        | HOLD SCOPE                                  |
| System Audit         | CONTEXT.md G3 contradicted plan; G4 stale;  |
|                      | compute_stats import path unnamed;          |
|                      | dispatch_parser error strings outdated      |
| Step 0               | HOLD SCOPE confirmed by user                |
| Section 1  (Scope)   | 2 issues (G3 contradiction, G4 stale)       |
| Section 2  (UX/AC)   | 2 warnings (extension fixture gap,         |
|                      |   geschwindigkeit type assertion fragility) |
| Section 3  (UX)      | 1 warning (silent XSD name collision)       |
| Section 4  (Risk)    | 2 CRITICALs (circular ref, namespace gap)   |
| Section 5  (Deps)    | 1 warning (dispatch_parser error msgs)      |
| Section 6  (Correct) | 1 CRITICAL (multi-key envelope silent mangle)|
+--------------------------------------------------------------------+
| Section 7  (Eng Arch)| 1 CRITICAL (_collect untyped registry)      |
|                      | 1 WARNING (dispatch error strings)          |
| Section 8  (Testing) | 2 warnings (compute_stats import, empty XSD)|
| Section 9  (Perf)    | 0 issues                                    |
| Section 10 (Sec/Err) | 1 CRITICAL (XXE via stdlib ET), 1 WARNING   |
+--------------------------------------------------------------------+
| 11-01-PLAN.md updated| 5 truths added, 1 artifact added            |
| 11-02-PLAN.md updated| 4 truths added                              |
| CONTEXT.md updated   | G3 rewritten, G4 rewritten,                 |
|                      | 4 decisions added, 2 items deferred         |
| Error/rescue registry| 8 paths mapped, 3 CRITICAL GAPS → PLANs     |
| Failure modes        | 7 total, 3 critical                         |
| Delight opps         | N/A (HOLD mode)                             |
| Diagrams produced    | Test coverage, Failure modes registry       |
| Unresolved decisions | 0                                           |
+====================================================================+
```

---

## Error & Rescue Registry

| CODEPATH | FAILURE MODE | RESCUED? | TEST? | USER SEES? | LOGGED? |
|---|---|---|---|---|---|
| `ET.parse(xsd)` stdlib | XXE / billion-laughs injection | **Y (defusedxml)** | implicit | blocked at parse | — |
| `_collect` circular type | RecursionError on self-ref type | **Y (visited set)** | Y (new) | stderr warning, continues | stderr |
| `parse_xsd` empty result | silent zero-triple Turtle, exit 0 | **Y (ValueError)** | Y (new) | exit 1 + message | stderr |
| `_build_fields` list-of-dicts | `"string"` inferred for array fields | **Y (extended infer)** | Y (new) | correct output | — |
| `dispatch_parser` unknown fmt | old error message lists 3 formats | **Y (update msg)** | Y (test 8-D) | updated message | stderr |
| `_collect` unqualified NS | zero fields returned silently | WARNING (doc'd) | partial | exit 1 via empty guard | stderr |
| `fields_to_graph` refactor | regression in 165 tests | **Y (exact behavior copy)** | all 165+ | test suite | CI |
| `parse_xsd` ET.Element access | untyped registry access | **Y (annotation)** | CI | CI failure | CI log |

---

## Failure Modes Registry

| CODEPATH | FAILURE | RESCUED? | TEST? | USER SEES? | LOGGED? |
|---|---|---|---|---|---|
| stdlib ET.parse | XXE injection | Y | implicit | blocked | — |
| `_collect` circular type | RecursionError | Y | Y (new) | warning+skip | stderr |
| `parse_xsd` empty result | silent exit 0, empty graph | Y | Y (new) | exit 1 + msg | stderr |
| Multi-key dict envelope | "string" for array fields | Y | Y (new) | correct fields | — |
| XSD field name collision | silent last-wins data loss | WARN only | N | stderr warning | stderr |
| `dispatch_parser` old msg | user sees wrong format list | Y (updated) | Y (new) | new format list | stderr |
| Unqualified namespace XSD | 0 fields silently | PARTIAL (empty guard→exit1) | N | exit 1 | stderr |

---

## Test Coverage Diagram

```
xsd_parser (11-01)
├── xs:element leaf → FieldSchema             ─── COVERED (test_xsd_simple)
├── xs:element container → children           ─── COVERED (test_xsd_nesting)
├── rose:hasChild arcs in Turtle              ─── COVERED (test_xsd_has_child_in_turtle)
├── xs:choice → required=False                ─── COVERED (test_xsd_choice_optional)
├── xs:enumeration → sample_values            ─── COVERED (test_xsd_enumeration_sample_values)
├── xs:attribute → field                      ─── COVERED (test_xsd_attribute_field)
├── xs:extension base+extended                ─── COVERED (test_xsd_extension)
├── xs:include → ValueError                   ─── COVERED (test_xsd_include_raises)
├── .xsd auto-detect                          ─── COVERED (test_xsd_auto_detect)
├── CLI roundtrip                             ─── COVERED (test_xsd_cli_roundtrip)
├── malformed XML → exit 1                    ─── COVERED (test_xsd_cli_invalid)
├── empty XSD → ValueError                    ─── COVERED [review] (new)
├── circular type → warning+skip             ─── COVERED [review] (new)
├── unit detection                            ─── COVERED (test_xsd_unit_detection)
└── unqualified namespace                     ─── NOT COVERED (documented gap)

json_sample_parser (11-02)
├── envelope unwrap (single key)              ─── COVERED (test_json_sample_envelope)
├── multi-key envelope → containers          ─── COVERED [review] (test_json_sample_multi_key_envelope)
├── nesting via _build_fields                 ─── COVERED (test_json_sample_nesting)
├── rose:hasChild in Turtle                   ─── COVERED (test_json_sample_has_child_in_turtle)
├── unit detection                            ─── COVERED (test_json_sample_unit_detection)
├── numeric_stats populated                   ─── COVERED (test_json_sample_stats_populated)
├── direct array input                        ─── COVERED (test_json_sample_direct_array)
├── flat single object                        ─── COVERED (test_json_sample_single_flat_object)
├── empty array → ValueError                  ─── COVERED (test_json_sample_empty_array_raises)
├── non-object array → ValueError             ─── COVERED (test_json_sample_non_object_array_raises)
├── stdin → slug="sample"                     ─── COVERED (test_json_sample_stdin_slug)
├── .json still → json-schema (regression)    ─── COVERED (test_json_sample_no_auto_detect)
└── CLI roundtrip                             ─── COVERED (test_json_sample_cli_roundtrip)
```

---

## Decisions Made During Review

| Decision | Rationale |
|---|---|
| defusedxml replaces stdlib ET | XXE attack surface for NATO XSD files; drop-in compatible |
| `visited: set[str]` in `_collect` | Circular type refs → RecursionError without guard |
| `parse_xsd` empty result → ValueError | Silent empty graph is worse than a clear error |
| Multi-key envelope → container fields | `_infer_data_type` extended to handle list-of-dicts; preserves structure |
| G3 rewritten | "flat list, leaf only" contradicted the actual nested design |
| G4 genson ref removed | genson was discarded; direct data walking is the actual implementation |

## Deferred

- Unqualified-namespace XSD test (no `xs:` prefix) — low probability, documented in README
- XSD xs:choice with nested complexType branch test — handled correctly by code, no test
- Language tag preservation on `rose:originalLabel` — from phase 10, unrelated to phase 11
