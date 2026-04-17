---
phase: 14
plan: "01"
title: "audit-log accreditation pipeline"
status: complete
commit: aac4500
completed: "2026-04-15"
test_metrics:
  total: 209
  passing: 209
  new_tests: 32
---

# Summary: Plan 14-01 — Audit-Log Accreditation Pipeline

## Outcome

All 6 tasks completed across 3 waves. 209/209 tests passing. All CI checks pass (ruff, basedpyright, pytest).

## What Was Built

**Wave 1 — Foundation**
- `rosetta/core/models.py`: `SSSOMRow` gains `mapping_date: datetime | None` and `record_id: str | None`; `LedgerEntry`/`Ledger` removed; `StatusEntry` model added for accredit status output
- `rosetta/core/accredit.py`: Full rewrite — `parse_sssom_tsv`, `load_log`, `append_log` (9-column, mkdir-safe, timestamp-stamps), `current_state_for_pair`, `query_pending`, `check_ingest_row` with exact constant matching
- `rosetta/core/similarity.py`: `apply_ledger_feedback` deleted; `Ledger` import removed

**Wave 2 — CLI Integration**
- `rosetta/cli/accredit.py`: Replaced `submit/approve/revoke/--ledger` with `ingest/review/status/dump/--log`; ingest pre-scans for in-file duplicate MMC pairs; all-or-nothing writes; stderr count reporting
- `rosetta/cli/suggest.py`: `--approved-mappings` removed; auto log-reading from `[accredit].log`; existing-pair merge (log justification/predicate preserved, fresh confidence); 9-column SSSOM output
- `rosetta/cli/lint.py`: `--sssom FILE` mode added — `MaxOneMmcPerPair`, `NoHumanCurationReproposal`, `ValidPredicate` checks
- `rosetta.toml`: `[accredit]` section added

**Wave 3 — Tests + Docs**
- `conftest.py`: `tmp_rosetta_toml` fixture (scope=function)
- `test_accredit.py`: 31 tests (15 core function + 16 CLI)
- `test_accredit_integration.py`: 4 E2E flow tests (approve boosts, reject deranks, correction overrides, existing-pair merge)
- `test_suggest.py`: 3 old `--approved-mappings` tests removed; 4 log-based tests added
- `test_lint.py`: 6 SSSOM proposals lint tests added
- `test_models.py`: `test_sssom_row_round_trip` updated for new fields
- `README.md`: `rosetta-accredit` section replaced; suggest/lint sections updated; config example updated
- `STATE.md`: Phase 14 marked complete, all 14 phases done

## Key Decisions Implemented

- 9-column SSSOM format everywhere (`mapping_date` + `record_id` for audit rows, empty strings for suggest output)
- `parse_sssom_tsv` is the shared parser (in `core/accredit.py`); suggest imports it rather than duplicating
- `check_ingest_row` uses exact constants (`semapv:ManualMappingCuration`, `semapv:HumanCuration`) — no `endswith`
- `dump` is exclusively HumanCuration output; `review` is exclusively pending ManualMappingCuration

## Bug Fixed During Build

- `suggest.py` existing-pair merge used `cand["object_id"]` — field is actually `cand["uri"]` in rank_suggestions output. Fixed by Task 5 agent.

## Issues Encountered

None. All must_haves verified by test suite.
