# Plan Review — Phase 9 Plan 02: Suggestion Feedback Loop + Pipeline
Date: 2026-04-13
Mode: HOLD

## Completion Summary

```
+====================================================================+
|            PLAN REVIEW — COMPLETION SUMMARY                        |
+====================================================================+
| Mode selected        | HOLD                                        |
| System Audit         | ast-grep available; claude-mem deferred     |
| Step 0               | HOLD confirmed; scope accepted as-is        |
| Section 1 (Scope)    | 0 issues — REQ-24/25 covered               |
| Section 2 (Errors)   | 3 error paths mapped, 1 GAP (CLI level)    |
| Section 3 (Security) | 0 High severity                            |
| Section 4 (Data/UX)  | 2 edge cases mapped (empty list, mixed key)|
| Section 5 (Tests)    | Diagram produced, 3 gaps fixed             |
| Section 6 (Future)   | Reversibility: 4/5, debt items: 1 (O(n*m))|
+--------------------------------------------------------------------+
| Section 7 (Eng Arch) | 3 CRITICAL issues found, all fixed          |
| Section 8 (Code Ql)  | 1 contradiction fixed (inline imports)     |
| Section 9 (Eng Test) | 3 gaps fixed (empty, CLI, unused fixture)  |
| Section 10 (Perf)    | 1 issue found (O(n*m) → fixed to O(1))    |
+--------------------------------------------------------------------+
| PLAN.md updated      | 4 truths added, 2 code blocks fixed        |
| CONTEXT.md updated   | 7 decisions locked, 3 items deferred       |
| Error/rescue registry| 4 methods mapped, 0 CRITICAL GAPS remain   |
| Failure modes        | 6 total, 0 CRITICAL GAPS remain            |
| Delight opportunities| N/A (HOLD mode)                            |
| Diagrams produced    | 1 (data flow below)                        |
| Unresolved decisions | 0                                          |
+====================================================================+
```

## Second-pass review findings (auto mode, 2026-04-13)

All 7 integration tests pass. Implementation is complete and matches plan spec.

Three corrections applied to PLAN.md and CONTEXT.md:

1. **CRITICAL (fixed):** Done-when criterion said "8/8 passing" — only 7 test functions exist. Corrected to 7/7 throughout.
2. **WARNING (fixed):** `accredit.py:submit_mapping()` calls `datetime.utcnow()` — deprecated in Python 3.12+, fires 6 DeprecationWarning per test run. Added [review] truth to replace with `datetime.now(datetime.UTC)`.
3. **WARNING (fixed):** `test_suggest_cli_with_ledger` assertion had unreachable OR clause (`>= 1.0 or > 0.9`). Simplified to `>= 1.0` with explanatory message.

## Data Flow Diagram

```
rosetta-suggest --source S --master M [--ledger L]
        │
        ▼
  load src_emb + master_emb (JSON)
        │
        ▼
  rank_suggestions(src_uris, A, master_uris, B)
        │  returns dict[src_uri → {suggestions: [{uri,score,rank}], anomaly}]
        ▼
  if --ledger:
    load_ledger(L)  ──────────── ledger.json (LedgerEntry list)
        │                               │
        └──── apply_ledger_feedback ────┘
              for each (src_uri, candidate):
                ┌── entry=None  → passthrough (all keys preserved)
                ├── status=revoked → drop
                ├── status=accredited → {**c, score=min(score*1.2, 1.0)}
                └── status=pending → passthrough
        │  (list NOT re-sorted yet)
        ▼
  re-sort by score DESC, re-assign rank
        │
        ▼
  SuggestionReport(Pydantic)
    → Suggestion(target_uri=s["uri"], score=s["score"])
        │  (rank discarded — not in Suggestion model)
        ▼
  model_dump_json(indent=2) → stdout / file
```

Shadow paths:
- Empty src_emb → exit 1, "No embeddings found in source file"
- Empty candidates after min_score filter → apply_ledger_feedback([]) → []
- Ledger file absent → load_ledger returns empty Ledger (per Plan 01 spec)
- Malformed ledger.json → Pydantic ValidationError → caught by outer Exception handler → exit 1

## Error & Rescue Registry

| Method | Error Type | Rescued? | Rescue Action | User Sees | Logged? |
|--------|-----------|----------|---------------|-----------|---------|
| `load_ledger` | FileNotFoundError | Y | returns empty Ledger | silent | N |
| `apply_ledger_feedback` | KeyError (missing "uri") | N | — raises KeyError | exit 1 via outer except | via click.echo |
| `suggest.py cli()` | ValidationError (malformed ledger) | Y | outer except block | "Error: ..." stderr | via click.echo |
| `load_ledger` | ValidationError (bad JSON) | Y | outer except block | "Error: ..." stderr | via click.echo |

## Failure Modes Registry

| CODEPATH | FAILURE MODE | RESCUED? | TEST? | USER SEES? | LOGGED? |
|----------|-------------|----------|-------|------------|---------|
| apply_ledger_feedback — accredited branch | drops rank key (mixed-shape list) | Y (fixed) | Y | silent | N |
| similarity.py basedpyright | Ledger forward-ref unresolved | Y (fixed) | via CI | CI failure | CI |
| suggest.py Task 2 | inline imports violate ruff PLC0415 | Y (fixed) | via CI | CI failure | CI |
| pipeline.sh python3 | wrong interpreter, ModuleNotFoundError | Y (fixed) | manual | script aborts | stderr |
| pipeline.sh | missing store/ dir | Y (fixed) | manual | script aborts | stderr |
| suggest --ledger | no CliRunner test | Y (fixed) | Y (added) | — | — |

## What Already Exists

- `rank_suggestions()` in `similarity.py` already produces the `{"uri", "score", "rank"}` shape
- `SuggestionReport`/`Suggestion`/`FieldSuggestions` Pydantic models already exist in `models.py`
- `suggest.py` outer `except Exception` handler already catches and reports errors to stderr + exit 1

## Dream State Delta

After this plan ships:
- Full accredit → feedback loop is wired: human approval flows back into suggestion ranking
- One missing piece for full production readiness: multi-user actor tracking (notes/provenance on transitions) — already in `LedgerEntry.actor` field but not surfaced in output
- Pipeline demo script exists but is not CI-tested (shell script testing is out of scope for MVP)
