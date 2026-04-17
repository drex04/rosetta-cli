---
phase: 17
plan: 1
title: "QUDT-native multi-library unit detection"
created: 2026-04-16
---

# Context — Plan 17-01

## Locked Decisions

- **QUDT-native return:** `detect_unit()` returns QUDT IRI strings directly (`"unit:M"`) or `None`. Never canonical strings.
- **UNIT_STRING_TO_IRI deleted:** No lookup table survives Phase 17. Single source of truth is `_PINT_TO_QUDT_IRI` inside `unit_detect.py`.
- **dBm handled by name pattern returning None:** The `_dbm$` name pattern maps to `None` and short-circuits immediately — no fallthrough to desc or NLP layers.

## Decisions (from review)

- [review] **Split deg/rad patterns:** `(?:deg|grad|grader)` → `unit:DEG` and `(?:rad|radians?)` → `unit:RAD` must be two separate `_NAME_PATTERNS` entries. The combined pattern `deg|grad|grader|rad|radians?` was dead code for `_rad`. Mrad entry stays before both.
- [review] **Module-level UnitRegistry singleton:** `_detect_from_nlp` must use a lazy module-level `_ureg` rather than `UnitRegistry()` per call. Creating N `UnitRegistry` objects in a lint run over N SSSOM rows that miss regex is unacceptable at scale.
- [review] **Outer try guards q3.parse():** The `except Exception` block must wrap the `q3.parse()` call — not only `ureg.parse_expression()`. Quantulum3 model errors must return `None`, never crash the lint CLI.
- [review] **ImportError → None:** `_detect_from_nlp` wraps its imports in `try/except ImportError: return None` so a missing quantulum3/pint install degrades gracefully instead of crashing.
- [review] **dBm test message assertion relaxed (Issue 4 — option A chosen):** `test_lint_sssom_unit_no_iri_mapping` checks `rule == "unit_not_detected"` only; message text not asserted. The dBm path collapsed from two steps (detect → IRI lookup) to one (detect returns None), so the old "no QUDT IRI mapping" message no longer applies.
- [review] **Task 5 preserves `_unit_label()`:** lint.py change uses `src_unit_str`/`tgt_unit_str` directly as IRIs, via the existing `_unit_label()` helper — does not regress to `subject_id.split(":")[-1]`.
- [review] **Task 2 done criterion adds unit:MIN SPARQL check:** `unit:MIN` appears in `_DESC_PATTERNS` and `_PINT_TO_QUDT_IRI`. If absent from the TTL graph, dimension checks silently return `None`. Done criterion must verify it.
- [review] **4 duplicate detect_unit tests in test_lint.py deleted, not replaced:** Coverage already exists in `test_unit_detect.py`. Adding duplicates violates CLAUDE.md stub-test convention.
- [review] **`test_detect_unit_dBm_desc_exact_case` updated to assert `is None`:** Old assertion `== "dBm"` (canonical string) will fail after IRI-native migration.

## Deferred Ideas

- **One-time `warnings.warn()` on NLP layer failure:** When quantulum3 fails silently, operators have no signal that the NLP path is non-functional. Deferred — adds complexity and a module-level flag; acceptable for Phase 17 given graceful None return.
- **Verify quantulum3 bundles spaCy model:** If quantulum3 requires a separate `python -m spacy download` step, CI model drift is a risk. Deferred — verify at implementation time; pin if needed.
- **Mock/spy on `_detect_from_nlp` in quantulum3 path test:** Adding a call-count assertion to `test_detect_unit_quantulum3_megahertz` would ensure it actually exercises the NLP path and doesn't silently pass if someone adds "megahertz" to `_DESC_PATTERNS`. Deferred — low risk for now.
