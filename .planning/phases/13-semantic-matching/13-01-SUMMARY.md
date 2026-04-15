---
phase: 13
plan: "01"
title: "linkml upgrade + SSSOM output"
status: complete
commit: 9d63eb8
completed: "2026-04-14"
tests_passing: 166
tests_total: 166
---

# Summary: Plan 13-01

## What was built

- **linkml 1.10.0 upgrade**: Added `linkml>=1.10.0` as direct dependency; removed the Format.JSON monkey-patch from `normalize.py` (no longer needed after upgrade).
- **SSSOMRow model**: Added to `models.py`; removed `Suggestion`, `FieldSuggestions`, `SuggestionReport` (now unused).
- **EmbeddingVectors.label**: Changed from `str | None = None` to `str = ""` for type correctness; `extract_text_inputs_linkml` return type annotation fixed to `tuple[str, str, str]`.
- **apply_sssom_feedback**: Replaced `apply_ledger_feedback` in `similarity.py` — dual boost+penalty paths with soft breadth deranking for `owl:differentFrom` rows.
- **anomaly removed**: `anomaly_threshold` param and `"anomaly"` key removed from `rank_suggestions()`.
- **rosetta-suggest rewritten**: SSSOM TSV output with curie_map header; `--ledger` → `--approved-mappings`; positional source/master args.
- **Tests updated**: All suggest/accredit/model tests migrated to SSSOM API; 10 new tests added; 4 deleted.
- **README updated**: rosetta-embed label field documented; rosetta-suggest SSSOM output documented.

## Test metrics

- 166/166 passing
- New tests: `test_suggest_cli_approved_mappings`, `test_suggest_cli_derank_revoked`, `test_suggest_cli_missing_approved_mappings`, `test_suggest_cli_output_file`, `test_sssom_row_round_trip`, SSSOM accredit tests
- Deleted: `test_rank_suggestions_anomaly_*` (3), `test_suggestion_report_root_model_serialisation`, `test_pending_no_effect`

## Issues Encountered

- Prior commit (d143292) had partial Phase 13 work: `EmbeddingVectors.label` added as `str | None = None`, embed CLI updated to 3-tuple format, sssom dependency added. Plan 01 built on this foundation.
- Task 4 subagent left dead `--ledger` code path and `--source`/`--master` flags; fixed inline before commit.

## Remaining Phase 13 scope

- Structural feature extraction (class hierarchy, slot co-occurrence, cardinality) — not in Plan 01, needs Plan 02.
