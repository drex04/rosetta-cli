# Plan Review: Phase 15-01 rosetta-lint SSSOM enrichment
**Date:** 2026-04-15 | **Mode:** HOLD SCOPE | **Gate:** PASS (with fixes applied)

---

## Mode Selected

**HOLD SCOPE** — Plan is well-bounded post-milestone cleanup: remove RDF lint path, add SSSOM unit/datatype checks, emit unified JSON LintReport. No expansion or reduction warranted.

---

## Completion Summary

```
+====================================================================+
|            PLAN REVIEW — COMPLETION SUMMARY                        |
+====================================================================+
| Mode selected        | HOLD SCOPE                                  |
| System Audit         | No FLOWS/ERD; ARCH+STRUCT present           |
| Step 0               | HOLD — plan scope accepted                  |
| Section 1  (Scope)   | 2 CRITICAL, 1 WARNING → fixed in PLAN.md   |
| Section 2  (Errors)  | 2 CRITICAL, 2 WARNING → fixed in PLAN.md   |
| Section 3  (UX)      | 1 WARNING (Click default OK)                |
| Section 4  (Impact)  | 1 CRITICAL, 1 WARNING → fixed in PLAN.md   |
| Section 5  (Deps)    | 1 WARNING → fixed in PLAN.md               |
| Section 6  (Correct) | 2 WARNING → fixed in PLAN.md               |
+--------------------------------------------------------------------+
| Section 7  (Arch)    | 2 WARNING → fixed in PLAN.md               |
| Section 8  (Tests)   | 2 CRITICAL, 2 WARNING → fixed in PLAN.md   |
| Section 9  (Perf)    | 0 issues (load_qudt_graph once = correct)   |
| Section 10 (Security)| 2 WARNING → 1 fixed, 1 documented          |
+--------------------------------------------------------------------+
| PLAN.md updated      | 14 truths added, 2 artifacts added          |
| CONTEXT.md created   | 8 decisions locked, 3 items deferred       |
| Error/rescue registry| 4 paths, 2 CRITICAL GAPs → PLAN.md         |
| Failure modes        | 5 total, 2 CRITICAL GAPs → PLAN.md         |
| Delight opps         | N/A (HOLD mode)                             |
| Diagrams produced    | 1 (test coverage ASCII)                     |
+====================================================================+
```

---

## What Already Exists

- `detect_unit(name, description)` in `unit_detect.py` — ready to reuse
- `units_compatible(src, tgt, graph) → bool | None` in `units.py` — ready to reuse
- `suggest_fnml(src, tgt, graph) → FnmlSuggestion | None` in `units.py` — needed for unit_conversion_required fnml_suggestion
- `load_qudt_graph()` in `units.py` — ready to reuse
- `LintFinding`, `LintReport`, `LintSummary` models in `models.py` — ready; fnml_suggestion field already present
- `parse_sssom_tsv` uses csv.DictReader — new optional columns backward-compatible via `.get()`

---

## Error & Rescue Registry

| CODEPATH | FAILURE MODE | RESCUED? | TEST? | USER SEES | LOGGED? |
|----------|-------------|----------|-------|-----------|---------|
| cli() / load_qudt_graph() | FileNotFoundError | Y (parse_error INFO) | N | JSON with error finding | N |
| _check_units / detect_unit() | Unexpected exception | Y (parse_error INFO) | N | JSON with error finding | N |
| _check_units step 3 | detect_unit → None | Y (INFO finding) | Y | unit_not_detected INFO | N |
| _check_units step 4 | UNIT_STRING_TO_IRI → None | Y (INFO finding) | Y | unit_not_detected INFO | N |
| parse_sssom_tsv | Malformed rows | Y (skip+stderr) | N | Empty report + exit 0 | Stderr |

---

## Failure Modes Registry

```
CODEPATH              | FAILURE MODE              | RESCUED? | TEST? | USER SEES?            | LOGGED?
----------------------|---------------------------|----------|-------|-----------------------|--------
cli() sssom=None      | Missing --sssom           | Y (exit1)| N     | "Error: --sssom req'd"| N
_check_units          | compatible=None           | Y (INFO) | Y*    | unit_vector_missing   | N
_check_units          | compatible=False          | Y (BLOCK)| Y     | dimension_mismatch    | N
_check_datatype       | Both dtypes None          | Y (skip) | Y     | no finding emitted    | N
check_sssom_proposals | reproposal of approved    | Y (BLOCK)| Y**   | BLOCK finding in JSON | N
```
*test_lint_sssom_unit_vector_missing added by review
**test_lint_sssom_proposals_json_finding added by review

---

## Test Coverage Diagram

```
NEW CODEPATHS (Task 4)                          TEST
─────────────────────────────────────────────────────────────────────
_check_units: both units None                   test_lint_sssom_unit_not_detected ✓
_check_units: unit → None QUDT IRI              test_lint_sssom_unit_no_iri_mapping ✓
_check_units: compatible=False (BLOCK)          test_lint_sssom_unit_dimension_mismatch ✓
_check_units: compatible=True+diff IRI (WARN)   test_lint_sssom_unit_conversion_required ✓
  └─ fnml_suggestion populated on WARNING       asserted in test_lint_sssom_unit_conversion_required [review]
_check_units: compatible=None (INFO)            test_lint_sssom_unit_vector_missing [review]
_check_datatype: numeric vs string (WARN)       test_lint_sssom_datatype_mismatch ✓
_check_datatype: numeric vs numeric             test_lint_sssom_datatype_both_numeric_no_finding ✓
_check_datatype: fields missing (skip)          test_lint_sssom_datatype_missing_skipped ✓
--strict: WARNING → BLOCK                       test_lint_sssom_strict_warning_becomes_block [review]
--strict: INFO stays INFO                       test_lint_sssom_strict_info_stays_info [review]
check_sssom_proposals JSON LintFinding output   test_lint_sssom_proposals_json_finding [review]
JSON LintReport structure exit 0                test_lint_sssom_json_report_structure ✓
embed.py datatype_map build                     test_embed.py + datatype test [review]
suggest.py round-trip 11 columns               test_suggest.py + column assertion [review]
```

---

## Decisions Made

1. **Error handling in cli():** wrap findings loop in try/except, append parse_error INFO, always write report.
2. **unit_not_detected:** single rule name, distinct messages for "no unit found" vs "unit has no QUDT IRI".
3. **_DATETIME_MIN:** renamed to DATETIME_MIN (public) in accredit.py; suggest.py import updated.

## Dream State Delta

After Phase 15, the tool set is fully SSSOM-native. The RDF lint path (SPARQL queries, custom datatype detection) is gone. The remaining gap to a "complete" lint experience: lint rules for circular mappings and confidence thresholds remain deferred. The datatype propagation chain (LinkML → embed → suggest → lint) is a novel architectural capability not originally in the v2 roadmap.
