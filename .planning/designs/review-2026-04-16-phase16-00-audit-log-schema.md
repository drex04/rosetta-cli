---
review_date: 2026-04-16
plan: 16-00
plan_title: "SSSOM audit-log schema extension (composite-entity support)"
mode: HOLD + add migration
gate: PASS_WITH_CHANGES
reviewers: fh:code-reviewer (business + engineering, parallel)
---

# Plan 16-00 — Plan Review Summary

Human-reference audit trail. Findings persisted as `[review]` truths in `.planning/phases/16-rml-gen-v2/16-00-PLAN.md`; cross-phase decisions in `CONTEXT.md`.

## Mode selected
**HOLD + add migration task.** Plan is a well-scoped prerequisite for 16-01. System audit surfaced a migration gap (live `store/audit-log.sssom.tsv` is 9-col; `append_log` doesn't re-write headers on append) — user elected to add an auto-migration path rather than detection-only or accepting risk.

## Completion summary

| Dimension | Result |
|-----------|--------|
| Mode | HOLD + add migration |
| System audit | Live 9-col audit log will silently corrupt on first 16-00 append — migration mandatory |
| Step 0 | HOLD locked; migration atomicity + writer-refactor decisions accepted |
| Section 1 (Scope) | OK — 4 fields unblock 16-01; 16-01 filter by `startswith("nor_radar:")` achievable |
| Section 2 (Errors) | 6 methods registered; 2 silent paths surfaced → fixed via stderr warn + migration atomicity |
| Section 3 (Security) | 0 High; yaml.safe_load already used (bandit clean) |
| Section 4 (Data/UX) | Live-log migration was the critical gap; resolved by Task 3b |
| Section 5 (Tests) | Test diagram produced; 1 CRITICAL + 3 WARNING gaps → all now have named tests |
| Section 6 (Future) | Reversibility: 4/5 (atomic migration + append-only log); debt items: 1 (prose-string → CURIE migration deferred) |
| Section 7 (Eng Arch) | Writer-list refactor adopted; `_parse_sssom_row` SYNC comment added |
| Section 8 (Code Qual) | 0 DRY violations; 1 parallel-list source of drift eliminated |
| Section 9 (Eng Test) | Migration round-trip + no-migration-on-current-shape both specified |
| Section 10 (Perf) | 0 High severity — CLI-scale glob + yaml.safe_load acceptable |
| PLAN.md updated | 6 `[review]` truths added, 1 artifact annotation expanded |
| CONTEXT.md updated | 5 decisions locked under "From plan-review (2026-04-16)"; 2 items deferred |
| Error/rescue registry | 6 methods; 0 remaining CRITICAL GAPs |
| Failure modes | Live-file corruption was the only CRITICAL — closed |
| Diagrams | Test coverage + error/rescue tables |

## Key decisions

1. **Migration strategy:** tmp + os.replace (atomic on POSIX). `_migrate_audit_log_if_needed(path)` runs as first step in `append_log`; reads comment lines + existing header + data rows; rewrites `<path>.tmp` with new header + padded rows; `os.replace(tmp, path)`. Test `test_accredit_append_log_migrates_9col_file` guards it.

2. **Writer refactoring:** `append_log`'s `writer.writerow([...])` positional literal replaced by `[_row_value_for_column(row, col, mapping_date, record_id) for col in AUDIT_LOG_COLUMNS]`. Header + body can no longer silently diverge.

3. **Prefix-collision hardening:** `parent.is_dir()` guard (vs `exists()`); stderr warning on unreadable siblings (vs silent `continue`). New tests for `id`-field clash and malformed-sibling warn.

4. **README SSSOM CURIE note:** forward-compat note added in Task 5.3 documenting that `"composed entity expression"` prose string is used in lieu of `sssom:CompositeEntity` CURIE; migration deferred.

5. **Scope creep adopted here (from 16-01 review):** `rosetta-ingest` gains Task 7 — stamps `annotations.rosetta_source_format` schema-wide and per-slot path annotations (`rosetta_jsonpath`, `rosetta_xpath`, `rosetta_csv_column`). Unblocks GA4 hybrid resolution and locks the 16-02 cross-phase contract.

## What already exists that partially solved this

- `rosetta/core/accredit.py::parse_sssom_tsv` already tolerates short/long rows via `DictReader` + `.get()` defaults — Task 4b leans on this. Only the write-path needed the migration guard.
- Phase 14 established the 9-column audit-log contract + its write-once header behaviour; 16-00 extends the column set without reinventing the append protocol.

## Dream-state delta

Relative to a 12-month ideal where the audit log is a SSSOM-validated artifact with full schema versioning + machine-actionable migration: 16-00 closes two gaps (composite-entity support, explicit backward-compat with migration) but leaves the `subject_type`/`object_type` prose-string choice as a known deviation from the canonical SSSOM CURIE pattern. Acceptable; flagged in README.

## Unresolved decisions

None. All three AskUserQuestion answers received; no silent defaults.
