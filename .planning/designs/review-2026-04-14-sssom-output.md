# Plan Review — 2026-04-14 — Phase 13-01: linkml upgrade + SSSOM output

## Mode Selected: HOLD SCOPE

---

## Completion Summary

```
+====================================================================+
|            PLAN REVIEW — COMPLETION SUMMARY                        |
+====================================================================+
| Mode selected        | HOLD SCOPE                                  |
| System Audit         | No FLOWS/ERD; ARCHITECTURE+STRUCTURE present|
| Step 0               | HOLD SCOPE confirmed                        |
| Section 1  (Scope)   | 2 issues: anomaly gap, curie_map missing    |
| Section 2  (Errors)  | 4 error paths mapped, 2 GAPS resolved       |
| Section 3  (CLI/UX)  | 2 issues: output file test, label source    |
| Section 4  (Risks)   | 2 CRITICAL gaps resolved + 1 warning        |
| Section 5  (Deps)    | 3 issues: anomaly leak, Phase 14, URI/CURIE |
| Section 6  (Correct) | 2 CRITICAL: test_models.py gap; SSSOMRow    |
+--------------------------------------------------------------------+
| Section 7  (Eng Arch)| 4 issues: anomaly dead return, boost design |
| Section 8  (Tests)   | 4 gaps: accredit migration, anomaly orphans |
| Section 9  (Perf)    | 1 issue: SSSOM row accumulation (low risk)  |
| Section 10 (Security)| 3 issues: missing-file error, label source  |
+--------------------------------------------------------------------+
| PLAN.md updated      | 10 truths added, 4 artifacts added           |
| CONTEXT.md created   | 7 decisions locked, 3 items deferred        |
| Error/rescue registry| 5 paths mapped, 2 CRITICAL GAPS → PLAN.md  |
| Failure modes        | 6 total, 0 remaining CRITICAL GAPS          |
| Delight opps         | N/A (HOLD SCOPE)                            |
| Diagrams produced    | test coverage diagram (below)               |
| Unresolved decisions | 0                                           |
+====================================================================+
```

---

## Key Design Decision: Dual-Intent SSSOM File for Revocation

The original plan had no revocation mechanism. After discussion, the design uses a single
`--approved-mappings` file with predicate-based intent:

```
predicate_id == owl:differentFrom  →  derank (penalty - 0.2, floor 0.0; row kept in SSSOM)
predicate_id == skos:exactMatch    →  boost  (+ 0.1, cap 1.0)
subject_id has any differentFrom  →  soft breadth penalty (× 0.25) on all other candidates
```

This is SSSOM-native (uses standard predicates), keeps rejected mappings visible to downstream
consumers, and discourages similar future selections without removing them from the mapping set.

---

## Scope Extension: rosetta-embed label field

Phase 13 now also touches `rosetta-embed`:
- `EmbeddingVectors.label: str = ""` added to model (backward-compatible)
- `rosetta/cli/embed.py` writes label as URI fragment (last segment after `#` or `/`)
- `test_embed.py` gains label assertions
- README rosetta-embed section updated

This was chosen over empty-string labels or a separate label lookup because:
- Phase 14 human reviewers need readable labels in the SSSOM output
- URI fragment parsing is 3 lines, zero dependencies
- `label = ""` default means all existing `.embed.json` files still load without error

---

## Test Coverage Diagram

```
apply_sssom_feedback()
  ├── boost match (approved, non-differentFrom)     [test_approve_boost — rewrite]
  ├── derank match (owl:differentFrom)              [test_derank_revoked — NEW]
  ├── subject-breadth soft penalty                  [test_derank_revoked — verify]
  ├── no match passthrough                          [test_no_ledger_match — rename]
  ├── additive cap at 1.0                           [test_boost_cap_at_1 — rewrite]
  └── empty candidates                              [test_empty_candidates — rename]

SSSOM TSV output (CLI)
  ├── curie_map header block                        [test_suggest_cli_basic — rewrite]
  ├── required columns present (subject_id etc)    [test_suggest_cli_basic — rewrite]
  ├── subject_label / object_label populated       [test_suggest_cli_basic — rewrite]
  ├── --approved-mappings boosts score             [test_suggest_cli_approved_mappings — NEW]
  ├── --approved-mappings deranks revoked          [test_suggest_cli_derank_revoked — NEW]
  ├── --approved-mappings missing file → exit 1    [test_suggest_cli_missing_approved — NEW]
  └── --output writes to file                      [test_suggest_cli_output_file — NEW]

rank_suggestions() anomaly path
  ├── anomaly_true                                  [DELETED — anomaly removed]
  ├── anomaly_false                                 [DELETED — anomaly removed]
  └── anomaly_pre_filter                            [DELETED — anomaly removed]

EmbeddingVectors.label
  ├── label from URI fragment                       [test_embed — new assertion]
  └── label fallback (no # or /)                   [test_embed — new assertion]
```

---

## Error & Rescue Registry

| Codepath | Failure Mode | Rescued? | Test? | User Sees |
|---|---|---|---|---|
| `--approved-mappings` file missing | FileNotFoundError | Yes (after fix) | Yes (new test) | exit 1 + path |
| SSSOM parse via library | Invalid TSV / wrong API | Yes — hand-rolled fallback | Partially | exit 1 + error |
| `apply_sssom_feedback` URI/CURIE mismatch | Zero boosts silently | No (documented in README) | No | Silent wrong output |
| `subject_label` / `object_label` missing from embed | KeyError | Yes — `.get("label", "")` | Via embed test | Empty columns |
| `rank_suggestions` dim mismatch | ValueError | Yes — existing test | Yes (existing) | exit 1 + message |

---

## Failure Modes Registry

| CODEPATH | FAILURE MODE | RESCUED? | TEST? | USER SEES | LOGGED? |
|---|---|---|---|---|---|
| --approved-mappings missing file | FileNotFoundError | Y (planned) | Y (new) | exit 1 + path | stderr |
| hand-rolled TSV, tab in object_id | Corrupted TSV | N | N | Malformed output | N |
| apply_sssom_feedback, CURIE vs URI | Zero matches | N (documented) | N | Silent | N |
| embed label, URI with no # or / | Empty label | Y (fallback "") | Y | Empty column | N |
| sssom library API change | ImportError/AttributeError | Y (fallback) | N | Hand-rolled output | N |
| rank_suggestions dim mismatch | ValueError | Y | Y | exit 1 | stderr |

---

## What Already Exists

- `apply_ledger_feedback` in `similarity.py` has the exact boost/cap/index pattern needed —
  `apply_sssom_feedback` is a direct extension of this design.
- `open_output` context manager in `rosetta/core/io.py` handles stdout/file switching — no change needed.
- `EmbeddingReport`/`EmbeddingVectors` Pydantic models already in place — just add `label` field.
- `test_accredit_integration.py` has 7 well-structured behavioral tests — most translate
  directly to SSSOM equivalents.

---

## Dream State Delta

After Phase 13-01:
- `rosetta-suggest` emits spec-compliant SSSOM TSV (curie_map, all columns, labels)
- Accreditation authority can signal approval AND deranking via a single SSSOM file
- Phase 14 (human review) receives SSSOM with readable labels — ready to build approve/reject UI

Remaining gap toward 12-month ideal:
- `predicate_id` is always `skos:relatedMatch` for auto-generated candidates — Phase 14 refines this
- URI/CURIE mismatch in `--approved-mappings` is silent — a future lint pass could warn
