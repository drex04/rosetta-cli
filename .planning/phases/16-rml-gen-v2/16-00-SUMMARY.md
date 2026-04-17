---
plan: 16-00
phase: 16-rml-gen-v2
status: complete
commit: 52e4999
completed: 2026-04-16
test_metrics:
  total: 266
  passing: 266
  new_tests: 12
  spec_tests_count: 0
  coverage: not configured
---

# Plan 16-00 — SSSOM Audit-Log Schema Extension

## Outcome

All 7 tasks complete across 4 waves. 266/266 tests passing. All 8 mandatory quality gates pass clean.

## Wave-by-wave

| Wave | Tasks | Status |
|------|-------|--------|
| W1 | T1 (SSSOMRow +4 fields), T6+T7 combined (collision lint + source-format annotations) | Complete |
| W2 | T2 (suggest TSV 11→15 cols), T3 (audit log 9→13 cols + round-trip) | Complete |
| W3 | T3b (atomic migration of pre-16-00 audit log) | Complete |
| W4 | T4 (12 new tests across 3 files), T5 (README) | Complete |

T6 + T7 were combined into one subagent because they edit the same files (`normalize.py`, `ingest.py`, `test_ingest.py`) and would race in parallel.

## Files changed

| File | Change |
|------|--------|
| `rosetta/core/models.py` | SSSOMRow +4 optional fields (subject_type, object_type, mapping_group_id, composition_expr) |
| `rosetta/cli/suggest.py` | `_SSSOM_COLUMNS` 11→15; writer emits empty placeholders |
| `rosetta/core/accredit.py` | AUDIT_LOG_COLUMNS 9→13; `_parse_sssom_row` extended with SYNC comment; `append_log` drives writer from column list; new `_migrate_audit_log_if_needed` + `_write_migrated_audit_log` |
| `rosetta/core/normalize.py` | New `check_prefix_collision`, `_stamp_source_format`, `_stamp_slot_paths` |
| `rosetta/cli/ingest.py` | Wires collision check + annotation stamping after `normalize_schema`, before file write |
| `rosetta/tests/test_models.py` | +1 test (composite-fields round-trip) |
| `rosetta/tests/test_suggest.py` | Header test renamed (11→15) + positional-order assertion |
| `rosetta/tests/test_accredit.py` | +4 tests (composite round-trip, 9/11-col backcompat, migration on 9-col, no-op on current) |
| `rosetta/tests/test_ingest.py` | +7 tests (4 collision + 3 source-format) |
| `README.md` | 15-col suggest table, 13-col audit log table, composite-mappings subsection, ingest collision + annotation paragraphs |

## Quality gates (all 8)

| Gate | Result |
|------|--------|
| ruff format | pass |
| ruff check | pass |
| basedpyright | pass (37 pre-existing errors in unmodified test files) |
| pytest -m "not slow" | 266/266 pass |
| radon cc rosetta/core/ -n C -s | pass (initially 2 grade-C functions in accredit.py introduced by T3/T3b — refactored to drop below grade C) |
| vulture --min-confidence 80 | pass |
| bandit -r rosetta/ -x rosetta/tests -ll | clean (0 issues) |
| refurb rosetta/ | pass (initially 2 FURB184 errors in T3 + T6 code — fixed inline) |

## Cross-phase contracts (locked for 16-01 consumption)

- `annotations.rosetta_source_format` — written as plain string (`"json"`, `"csv"`, `"xml"`) on every data-source LinkML schema; RDFS-sourced schemas skip the stamp. `rosetta-yarrrml-gen` reads this from `data["annotations"]["rosetta_source_format"]`.
- Per-slot path annotations: `rosetta_jsonpath`, `rosetta_xpath`, `rosetta_csv_column` stamped per slot based on input format.
- Audit log column count is now 13. `_parse_sssom_row` tolerates 9/11/13 via `.get()` defaults.
- `AUDIT_LOG_COLUMNS` is the single source of truth — `append_log` and `_parse_sssom_row` both reference it (the SYNC comment flags the maintenance invariant).

## Issues encountered

- **Pre-commit blocked twice during commit:**
  1. FURB184 (refurb): two assignment-statement-should-be-chained errors in T3 (`accredit.py:141`) and T6 (`test_ingest.py:192`). Inlined `text = path.read_text(); lines = text.splitlines()` to single chain; inlined `data1 = yaml.safe_load(); ...get(...)` to single chain.
  2. Radon C-grade complexity: `_parse_sssom_row` (CC=14) and `_migrate_audit_log_if_needed` (CC=13) were grade C. Extracted `_OPTIONAL_STR_FIELDS` constant + `_parse_mapping_date` helper for the former; extracted `_write_migrated_audit_log` from the latter. Both back to grade B.

  Both classes of failure were the build's own code, not pre-existing. The T4 subagent's claim that refurb was pre-existing was confused — it was failing due to the build's new code.

- **Pre-existing tree noise NOT in commit:** `pyproject.toml`, `uv.lock`, `.planning/STATE.md`, `.planning/ROADMAP.md`, deletions in `store/`, `rosetta/store/.gitkeep` — all left in working tree, unrelated to 16-00.

- **New untracked appeared during build:** `.planning/phases/17-unit-detect/` showed up — external (not from this build), flag for user awareness.

## Concerns for downstream

- **SSSOMRow lacks `extra="forbid"`** (flagged by T1 subagent). Means TSV reads with unexpected columns silently drop. Worth fixing in a future small task — would catch column-name typos. Not blocking 16-01.
- **TOCTOU race in `append_log` header check** (`path.stat().st_size == 0`) — known limitation per CONCERNS.md. Migration helper has the same race. No file lock added per plan instructions. Single-writer pipelines are safe.
- **Forward-compat note in README**: implementation uses prose `"composed entity expression"` for `subject_type`/`object_type` rather than spec CURIE `sssom:CompositeEntity`. Migration to the CURIE form is a deferred decision.

## Next

Plan 16-01 (`rosetta-yarrrml-gen`) — SSSOM → linkml-map TransformSpec builder. Prerequisites now satisfied: `SSSOMRow` has the four composite fields, `rosetta-ingest` stamps source-format and per-slot path annotations, and the audit log auto-migrates from 9 to 13 columns on first append.
