---
phase: 15
plan: "01"
title: "rosetta-lint SSSOM enrichment"
status: complete
commit: a78d5ca
tests: 253/253
duration_s: 1510
---

# Summary: Plan 15-01 — rosetta-lint SSSOM Enrichment

## What Was Built

Removed the legacy RDF lint path (`--source`/`--master`/`--suggestions`) and enriched the SSSOM lint path with unit and datatype compatibility checks, emitting a JSON `LintReport`.

**Datatype propagation chain implemented end-to-end:**
`LinkML slot.range → EmbeddingVectors.datatype → SSSOMRow.subject_datatype/object_datatype → SSSOM TSV → lint.py checks`

## Changes by Task

| Task | File(s) | Change |
|------|---------|--------|
| 1 | `rosetta/core/models.py` | `EmbeddingVectors.datatype`, `SSSOMRow.subject_datatype/object_datatype` (optional fields) |
| 2 | `rosetta/cli/embed.py` | `datatype_map` from `schema.slots[].range`; passed to `EmbeddingVectors(datatype=...)` |
| 3 | `rosetta/cli/suggest.py` | 11-column SSSOM TSV; `_DATETIME_MIN` → `DATETIME_MIN`; datatype fields in `SSSOMRow` |
| 3 | `rosetta/core/accredit.py` | Backward-compat `.get("subject_datatype")` parse; `DATETIME_MIN` public |
| 4 | `rosetta/cli/lint.py` | SSSOM-only CLI; `check_sssom_proposals` → `list[LintFinding]`; `_check_units` + `_check_datatype` helpers; `--strict` flag |
| 5 | `rosetta/tests/test_lint.py` | Removed 17 RDF-mode tests; added 12 SSSOM unit/datatype tests |
| 5 | `rosetta/tests/test_embed.py` | Added `test_embed_cli_datatype_propagation` |
| 5 | `rosetta/tests/test_models.py` | Added datatype field round-trip tests |
| 5 | `rosetta/tests/test_suggest.py` | 11-column header assertion; datatype fixtures |
| 6 | `README.md` | Updated `rosetta-lint` section: SSSOM-only usage, 9-rule table, `--strict` note |

## Lint Rules Implemented

| Rule | Severity |
|------|----------|
| `unit_dimension_mismatch` | BLOCK |
| `unit_conversion_required` | WARNING + fnml_suggestion |
| `unit_not_detected` | INFO |
| `unit_vector_missing` | INFO |
| `datatype_mismatch` | WARNING |
| `max_one_mmc_per_pair` | BLOCK |
| `reproposal_of_approved` | BLOCK |
| `reproposal_of_rejected` | BLOCK |
| `invalid_predicate` | BLOCK |

## Quality Gate

- ruff format: ✓
- ruff check: ✓
- basedpyright: ✓ (exit 3 — pre-existing warnings in test_embed/test_validate, not introduced by this phase)
- radon: ✓
- vulture: ✓
- refurb: ✓ (4 FURB fixes applied: FURB143 ×2, FURB135, FURB184)
- bandit: ✓
- pytest: 253/253 ✓

## Issues Encountered

- ruff E501: 7 long lines in new code (message strings + one docstring) — shortened
- refurb FURB143/135/184: 4 modernization issues in new code — fixed before commit
- `_DATETIME_MIN` rename: suggest.py had private import — renamed to `DATETIME_MIN` and import updated
- Test assertion mismatch: `test_lint_sssom_unit_no_iri_mapping` checked for `"no QUDT IRI mapping"` — message was over-shortened during E501 fix; restored "mapping" suffix via variable extraction
