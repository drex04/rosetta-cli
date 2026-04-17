# Plan Review: Phase 14-01 Audit-Log Accreditation Pipeline
Date: 2026-04-15 | Mode: HOLD | Reviewer: fh:plan-review

## Mode Selected
HOLD — focused refactoring of accreditation module; scope and locked decisions accepted as-is.

## Completion Summary

```
+====================================================================+
|            PLAN REVIEW — COMPLETION SUMMARY                        |
+====================================================================+
| Mode selected        | HOLD                                        |
| System Audit         | Breaking import in similarity.py confirmed  |
| Step 0               | HOLD — scope correct, decisions locked      |
| Section 1  (Scope)   | 1 issue found (silent skip UX)             |
| Section 2  (Stories) | 1 issue found (status schema undefined)     |
| Section 3  (UX)      | 1 issue found (review format unspecified)  |
| Section 4  (Risk)    | 2 issues found (migration, concurrent write)|
| Section 5  (Deps)    | 1 CRITICAL: 3 test files import deleted syms|
| Section 6  (Correct) | 2 CRITICALs: similarity.py, in-file dup MMC|
+--------------------------------------------------------------------+
| Section 7  (Eng Arch)| 2 CRITICALs: column set + parser mismatch  |
| Section 8  (Tests)   | 1 CRITICAL: missing tmp_rosetta_toml fixture|
| Section 9  (Perf)    | 2 WARNINGs: O(n) load, O(n²) query_pending |
| Section 10 (Security)| 2 CRITICALs: mkdir-p, malformed row crash  |
+--------------------------------------------------------------------+
| PLAN.md updated      | 13 truths added, 2 artifacts added          |
| CONTEXT.md updated   | 8 decisions locked                          |
| Error/rescue registry| 12 methods, 7 CRITICAL GAPS → PLAN.md truths|
| Failure modes        | 12 total, 7 CRITICAL GAPS → PLAN.md truths  |
| Delight opps         | N/A (HOLD mode)                             |
| Diagrams produced    | 1 (test coverage), 1 (error/rescue map)     |
| Unresolved decisions | 0                                           |
+====================================================================+
```

## Key Decisions Made

1. **Delete `apply_ledger_feedback`** from `similarity.py` entirely (not convert)
2. **9-column SSSOM format everywhere** — `mapping_date` + `record_id` in `_SSSOM_COLUMNS`; blank for non-audit rows
3. **In-file duplicate MMC pre-scan** in `ingest` before calling `check_ingest_row`
4. **`dump` omits MMC-only pairs** silently
5. **`StatusEntry(BaseModel)`** in `models.py` for typed `status` JSON output
6. **Exact constant matching** in `check_ingest_row` (not `endswith`)
7. **`tmp_rosetta_toml` conftest fixture** required for all integration tests
8. **`review` outputs valid SSSOM TSV** (pipeable back to `ingest`)

## Critical Gaps Found and Resolved in PLAN.md

| # | Gap | Resolution |
|---|-----|-----------|
| C1 | `similarity.py:7` imports `Ledger`; `apply_ledger_feedback` uses it → `ImportError` | Task 1 now explicitly deletes function + updates import |
| C2 | `parse_sssom_tsv` silently drops `mapping_date`/`record_id` → all dates `None` | `_SSSOM_COLUMNS` expanded to 9; parser reads all columns |
| C3 | `append_log` column set unspecified → implementer writes 7-col log, losing timestamps | `_AUDIT_LOG_COLUMNS` = 9 columns; `append_log` uses it |
| C4 | Task 3 pseudocode: `apply_sssom_feedback(result, hc_rows)` — wrong signature | Fixed to per-field iteration with correct 3-arg call |
| C5 | No `tmp_rosetta_toml` fixture → integration tests silently pass with wrong log | Added to Task 5 + conftest.py artifact |
| C6 | `append_log` missing `mkdir -p` → `FileNotFoundError` on new parent dir | Specified in Task 1 log format section |
| C7 | Malformed log row raises uncaught exception → entire tool suite unusable | `parse_sssom_tsv` skips bad rows with stderr warning |
| C8 | Batch-internal duplicate MMC both pass validation → `MaxOneMmcPerPair` violated | Pre-scan added to Task 2 `ingest` spec |

## Test Coverage Diagram

```
core/accredit.py
├── load_log()              → test_load_log_empty [PLANNED]
│   ├── file absent → []    → test_load_log_missing [PLANNED]
│   └── malformed row       → COVERED by parse_sssom_tsv skip
├── append_log()
│   ├── creates file+header → test_append_log_creates [PLANNED]
│   ├── appends rows        → test_append_log_appends [PLANNED]
│   ├── stamps date/uuid    → test_append_log_stamps [PLANNED]
│   └── parent dir absent   → [review] mkdir-p specified
├── current_state_for_pair()
│   ├── absent → None       → test_current_state_none [PLANNED]
│   └── multiple → latest   → test_current_state_latest [PLANNED]
├── query_pending()
│   ├── no MMC → []         → test_query_pending_empty [PLANNED]
│   └── MMC+HC → cleared    → test_query_pending_cleared [PLANNED]
└── check_ingest_row()
    ├── MMC blocked by HC   → test_check_ingest_blocked [PLANNED]
    ├── HC blocked w/o MMC  → PLANNED
    └── HC over HC (corr.)  → test_accredit_ingest_hc_correction [ADDED]

cli/accredit.py
├── ingest
│   ├── happy path          → PLANNED
│   ├── blocked transition  → PLANNED
│   ├── in-file dup MMC     → test_ingest_rejects_duplicate_mmc [ADDED]
│   └── count to stderr     → test_ingest_prints_count [ADDED]
├── review
│   ├── pending rows        → PLANNED
│   ├── log absent → empty  → test_review_empty_when_log_absent [ADDED]
│   └── valid SSSOM TSV     → test_review_valid_sssom_tsv [ADDED]
├── dump
│   ├── latest HC per pair  → PLANNED
│   └── MMC-only omitted    → test_dump_omits_mmc_only [ADDED]
└── status
    ├── JSON output          → PLANNED
    └── log absent → []     → test_status_empty_when_log_absent [ADDED]

integration
├── approve → boost         → PLANNED
├── reject → derank         → PLANNED
├── correction override     → PLANNED
├── existing-pair merge     → PLANNED
└── no log → passthrough    → PLANNED
    (all via tmp_rosetta_toml fixture)
```

## Error/Rescue Map

| CODEPATH | ERROR TYPE | RESCUED? | RESCUE ACTION | USER SEES |
|---|---|---|---|---|
| `load_log` — file missing | `FileNotFoundError` | YES | return `[]` | nothing |
| `load_log` — malformed row | `ValueError`/`csv.Error` | YES (added) | skip row + stderr warn | warning msg |
| `load_log` — invalid mapping_date | `ValueError` | YES (via parse skip) | treat as `None` | nothing |
| `append_log` — parent dir missing | `FileNotFoundError` | YES (added) | `mkdir -p` first | nothing |
| `append_log` — disk full mid-write | `OSError` | NO (MVP scope) | propagates | crash |
| `check_ingest_row` — blocked | `ValueError` | YES | CLI catches, exit 1 | error msg |
| `ingest` — in-file dup MMC | pre-scan | YES (added) | collect error, exit 1 | error msg |
| `status` — log absent | `FileNotFoundError` | YES (added) | output `[]`, exit 0 | empty array |
| `review` — log absent | `FileNotFoundError` | YES (added) | header-only TSV, exit 0 | header only |

## What Already Exists

- `apply_sssom_feedback` in `similarity.py` — correct implementation, just wrong pseudocode in plan
- `_parse_sssom_tsv` in `suggest.py` — will be promoted to `core/accredit.py`
- `apply_ledger_feedback` in `similarity.py` — dead after Task 1, must be deleted
- `Ledger`/`LedgerEntry` in `models.py` — will be deleted
- All ledger-based tests — will be replaced

## Dream State Delta

This plan completes the audit-trail layer. After it ships:
- Single source of truth for all accreditation decisions (no dual-path)
- Full proposal → review → approval workflow in SSSOM format
- `rosetta-suggest` output auto-improves from human decisions
- Remaining gap: unit/datatype compatibility in `--sssom` lint mode (deferred to Phase 15)
